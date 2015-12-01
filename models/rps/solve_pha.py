#!/usr/bin/env python

from mpi4py import MPI
mpi_comm = MPI.COMM_WORLD
mpi_rank = mpi_comm.Get_rank()

import sys, os, time, fcntl
import pdb, traceback

from pyomo.environ import *
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition

def add_relative_path(*parts):
    """ Adds a new path to sys.path.
    The path should be specified relative to the current module, 
    and specified as a list of directories to traverse to reach the
    final destination."""
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), *parts)))
    
# note: switch and switch-hawaii should normally be cloned 
# into the directory for each scenario, and then during active 
# developmnet they should be refreshed periodically and the scenario 
# files should also be updated to address any changes. This way, 
# when a scenario is archived, it retains the appropriate versions 
# of switch and switch-hawaii, so it can be re-run if needed.

add_relative_path('switch')   # standard switch model
import switch_mod.utilities as utilities
from switch_mod.utilities import define_AbstractModel

add_relative_path('switch-hawaii-core') # common components of switch-hawaii
import util, scenarios
from util import tic, toc, log, get
from scenarios import parser

add_relative_path('.') # components for this particular study

# add_relative_path('..', 'pumped_hydro') # components reused from the pumped_hydro study

opt = SolverFactory("cplex", solver_io="nl")
# tell cplex to find an irreducible infeasible set (and report it)
opt.options['iisfind'] = 1

# relax the integrality constraints, to allow commitment constraints to match up with 
# number of units available
opt.options['mipgap'] = 0.001
# display more information during solve
opt.options['display'] = 1
opt.options['bardisplay'] = 1
opt.options['mipdisplay'] = 2
opt.options['primalopt'] = ""   # this is how you specify single-word arguments
opt.options['advance'] = 2
#opt.options['threads'] = 1

# define global variables for convenient access in interactive session
switch_model = None
switch_instance = None
results = None

# global variable for location of results files
output_dir = None

def main():
    # only called if solve.py is executed from a command line
    # (not called by 'import solve')

    parser.add_argument('--tag', type=str)
    parser.add_argument('--ph_year', type=int)
    parser.add_argument('--ph_mw', type=float)
    parser.add_argument('--biofuel_limit', type=float)
    parser.add_argument('--dr_shares', nargs='+', type=float)
    
    cmd_line_args = scenarios.cmd_line_args()

    required_scenarios = scenarios.get_required_scenario_names()

    if len(required_scenarios) > 0:
        # user specified some specific scenarios to run
        for s in required_scenarios:
            # flag that the scenario is running/completed
            scenarios.report_completed_scenario(s)
            # get the scenario definition, including any changes specified on the command line
            args = scenarios.get_scenario_args(s)
            # solve the model
            print "\n\n======================================================================="
            print 'running scenario {s}'.format(s=append_tag(s, args["tag"]))
            print 'arguments: {}'.format(args)
            print "======================================================================="
            solve(**args)
    else:
        # they want to run the standard scenarios, possibly with some command-line modifications
        while True:
            s = scenarios.start_next_standard_scenario()
            if s is None:
                break
            else:
                # solve the model
                print 'running scenario {s}'.format(s=append_tag(s["scenario_name"], s["tag"]))
                print 'arguments: {}'.format(s)
                solve(**s)

def solve(
    inputs_dir='inputs', inputs_subdir='', outputs_dir='outputs', 
    rps=True, renewables=True, wind=None, central_pv=None,
    demand_response=True, dr_shares=[0.3],
    ev=True, 
    pumped_hydro=True, ph_year=None, ph_mw=None,
    fed_subsidies=False,
    biofuel_limit=0.05,
    scenario_name=None, tag=None
    ):
    # load and solve the model, using specified configuration
    # NOTE: this version solves repeatedly with different DR targets
    global switch_model, switch_instance, results, output_dir

    # quick fix to use scenario name and (optional) tag
    tag = None if scenario_name is None else append_tag(scenario_name, tag)
    
    # quick fix for inputs_dir / inputs_subdir
    inputs_dir = os.path.join(inputs_dir, inputs_subdir)

    modules = ['switch_mod', 'fuel_markets', 'fuel_markets_expansion', 'project.no_commit', 
        'switch_patch', 'batteries', 'rps']
    modules.append('emission_rules')    # no burning LSFO after 2017 except in cogen plants
    for m in ['ev', 'pumped_hydro', 'fed_subsidies', 'demand_response']:
        if locals()[m] is True:
            modules.append(m)
    if demand_response is not True:
        dr_shares = [0.00]
    dr_share = dr_shares[0] # no loop in this version
    # TODO: treat the 'no_*' modules as standard scenario names 
    # (i.e., include no_renewables, etc. instead of excluding renewables, etc.)
    if renewables is False:
        modules.append('no_renewables')
    if wind is False:
        modules.append('no_wind')
    if central_pv is False:
        modules.append('no_central_pv')
    if ev is False:
        # user asked for no_ev (count transport emissions but don't allow EVs)
        modules.append('no_ev')
        
    log('using modules: {m}\n'.format(m=modules))

    log("defining model... "); tic()
    switch_model = define_AbstractModel(*modules)
    switch_model.iis = Suffix(direction=Suffix.IMPORT)
    switch_model.dual = Suffix(direction=Suffix.IMPORT)
    
    # force construction of a fixed amount of pumped hydro
    if ph_mw is not None:
        print "Forcing construction of {m} MW of pumped hydro.".format(m=ph_mw)
        switch_model.Build_Pumped_Hydro_MW = Constraint(switch_model.LOAD_ZONES, rule=lambda m, z:
            m.Pumped_Hydro_Capacity_MW[z, m.PERIODS.last()] == ph_mw
        )
    # force construction of pumped hydro only in a certain period
    if ph_year is not None:
        print "Allowing construction of pumped hydro only in {p}.".format(p=ph_year)
        switch_model.Build_Pumped_Hydro_Year = Constraint(
            switch_model.PH_PROJECTS, switch_model.PERIODS, 
            rule=lambda m, pr, pe:
                m.BuildPumpedHydroMW[pr, pe] == 0 if pe != ph_year else Constraint.Skip
        )

    if biofuel_limit is not None:
        print "Limiting (bio)fuels to {l}% of electricity production.".format(l=biofuel_limit*100.0)
        switch_model.rps_fuel_limit = biofuel_limit

    # add an alternative objective function that smoothes out various non-cost variables
    def Smooth_Free_Variables_obj_rule(m):
        # minimize production (i.e., maximize curtailment / minimize losses)
        obj = sum(
            getattr(m, component)[lz, t] 
                for lz in m.LOAD_ZONES 
                    for t in m.TIMEPOINTS 
                        for component in m.LZ_Energy_Components_Produce)
        # also minimize the magnitude of demand adjustments
        if hasattr(m, "DemandResponse"):
            print "Will smoothe DemandResponse."
            obj = obj + sum(m.DemandResponse[z, t]*m.DemandResponse[z, t] for z in m.LOAD_ZONES for t in m.TIMEPOINTS)
        # also minimize the magnitude of EV charging
        if hasattr(m, "ChargeEVs"):
            print "Will smoothe EV charging."
            obj = obj + sum(m.ChargeEVs[z, t]*m.ChargeEVs[z, t] for z in m.LOAD_ZONES for t in m.TIMEPOINTS)
        return obj
        
    switch_model.Smooth_Free_Variables = Objective(rule=Smooth_Free_Variables_obj_rule)
    
    toc()   # done defining model

    log("loading model data from {} dir... ".format(inputs_dir)); tic()
    switch_instance = switch_model.load_inputs(inputs_dir=inputs_dir)
    toc()

    if rps is False:
        # deactivate the main RPS constraint
        # (we do this instead of omitting the whole RPS module, 
        # so we can report RPS-qualified power even if the RPS is not in effect)
        # NOTE: for now, there's no easy way to pass solver flags into individual modules
        # which would probably be a cleaner solution
        switch_instance.RPS_Enforce.deactivate()
        switch_instance.preprocess()

    if demand_response:
        switch_instance.demand_response_max_share = dr_share
        switch_instance.preprocess()

    # investigate the cost_components_annual elements
    import pdb; pdb.set_trace()

    output_dir = outputs_dir    # assign to global variable with slightly different name (ugh)
    setup_results_dir()
    create_batch_results_file(switch_instance, scenario=tag)
        
    
    while True
    
        # make sure the minimum-cost objective is in effect
        switch_instance.Smooth_Free_Variables.deactivate()
        switch_instance.Minimize_System_Cost.activate()
        results = _solve(switch_instance)

        log("Solver finished; "); toc()

        if results.solver.termination_condition == TerminationCondition.infeasible:
            print "Model was infeasible; Irreducible Infeasible Set (IIS) returned by solver:"
            print "\n".join(c.cname() for c in switch_instance.iis)
            if util.interactive_session:
                print "Unsolved model is available as switch_instance."
            raise RuntimeError("Infeasible model")

        # Freeze all direct-cost variables, and then solve the model against a smoothing objective instead of a cost objective.
        old_duals = [
            (z, t, switch_instance.dual[switch_instance.Energy_Balance[z, t]]) 
                for z in switch_instance.LOAD_ZONES
                    for t in switch_instance.TIMEPOINTS]
        fix_obj_expression(switch_instance.Minimize_System_Cost)
        switch_instance.Minimize_System_Cost.deactivate()
        switch_instance.Smooth_Free_Variables.activate()
        switch_instance.preprocess()
        log("smoothing free variables...\n"); tic()
        results = _solve(switch_instance)    
        # restore hourly duals from the original solution
        for (z, t, d) in old_duals:
            switch_instance.dual[switch_instance.Energy_Balance[z, t]] = d
        # unfix the variables
        fix_obj_expression(switch_instance.Minimize_System_Cost, False)
        log("finished smoothing free variables; "); toc()

        if util.interactive_session:
            print "Model solved successfully."
            print "Solved model is available as switch_instance."
    
        print "\n\n======================================================="
        print "Solved model"
        print "======================================================="
        print "Total cost: ${v:,.0f}".format(v=value(switch_instance.Minimize_System_Cost))
    
        # if pumped_hydro:
        #     switch_instance.BuildPumpedHydroMW.pprint()

        append_batch_results(switch_instance, scenario=tag)
        
        if len(dr_shares) > 1:
            t = ("" if tag is None else str(tag) + '_') + 'dr_share_' + str(dr_share)
        else:
            t = tag
        write_results(switch_instance, tag=t)

        # take a look at the biofuel limit
        #import pdb; pdb.set_trace()


def append_tag(text, tag):
    return text if tag is None or tag == "" else text + "_" + str(tag)

def _solve(m):
    """Solve instance of switch model, using the specified objective, then load the results"""
    results = opt.solve(m, keepfiles=False, tee=True,
        symbolic_solver_labels=True, suffixes=['dual', 'iis'])

    # results.write()
    log("loading solution... "); tic()
    # Pyomo changed their interface for loading results somewhere 
    # between 4.0.x and 4.1.x in a way that was not backwards compatible.
    # Make the code accept either version
    if hasattr(m, 'solutions'):
        # Works in Pyomo version 4.1.x
        m.solutions.load_from(results)
    else:
        # Works in Pyomo version 4.0.9682
        m.load(results)
    toc()
    
    return results
    
def progressive_hedging_adjust(m):
    """Communicate between different sub-models and adjust the target values."""
    # see http://www.orsnz.org.nz/conf33/papers/p84.pdf
    # and http://www.optimization-online.org/DB_FILE/2008/09/2089.pdf
    # and http://www.math.washington.edu/~rtr/papers/rtr120-ScenariosAggregation.pdf
    
    build_quantities=dict()
    for cn in ["BuildProj", "BuildBattery", "BuildPumpedHydroMW"]:
        # These are all coincidentally indexed over two elements (project or zone, period)
        c = getattr(m, cn)
        for (i, j) in c:
            build_quantities[(cn, i, j)] = value(c[i, j])

    # collect or send build_quantities
    data = comm.gather(build_quantities, root=0)
    n = len(data)   # should also equal mpi_comm.Get_size()
    
    if data is None:
        build_quantities_avg = None
    else:
        # this is the root node
        # calculate build_quantities_avg (target to converge on)
        build_quantities_avg = {k: sum(d[k] for d in data)/n for k in data[0]}
        
    # send or receive build_quantities_avg
    build_quantities_avg = comm.bcast(build_quantities_avg, root=0)
    
    # update the model
    if not hasattr(m, "PHA_VARS")
        # add the convergence target to the objective function
        # initial weights for x deviations can be zero
        # r can be constant (not clear what its magnitude should be)
        # after each step, weights = weights + r (X - X_hat) (using the new X values)
        m.PHA_VARS = Set(initialize=build_quantities_avg.keys())
        m.PHA_weight = Param(m.PHA_VARS, default=0.0, mutable=True)
        m.PHA_penalty_factor = Param(initialize=10)
        m.PHA_target = Param(m.PHA_VARS, default=0.0, mutable=True)
        # penalty value for deviations from the target; this is indexed
        # over all periods just to make it easy to add to the model; only
        # the first period actually matters
        m.PHA_Penalty = Expression(m.PERIODS, rule=lambda m, p:
            sum(
                m.PHA_weight[cn, i, j] * getattr(m, cn)[i, j] - 
                    for cn, i, j in m.PHA_VARS
            ) if p = m.PERIODS.first() else 0.0
        )
        
    for cn, i, j in m.PHA_VARS:
        m.PHA_weight[cn, i, j] = ...
        m.PHA_target[cn, i, j] = build_quantities_avg[cn, i, j]

    m.PHA_Penalty.reconstruct()
    m.Minimize_System_Cost.reconstruct()
    # Check for convergence
    


def fix_obj_expression(e, status=True):
    """Recursively fix all variables included in an objective expression."""
    try:
        if hasattr(e, 'fixed'):
            e.fixed = status      # see p. 171 of the Pyomo book
        elif hasattr(e, '_numerator'):
            for e2 in e._numerator:
                fix_obj_expression(e2)
            for e2 in e._denominator:
                fix_obj_expression(e2)
        elif hasattr(e, '_args'):
            for e2 in e._args:
                fix_obj_expression(e2)
        elif hasattr(e, 'expr'):
            fix_obj_expression(e.expr)
        elif hasattr(e, 'is_constant') and e.is_constant():
            pass    # numeric constant
        else:
            raise ValueError('Expression {e} does not have an expr, fixed or _args property, so it cannot be fixed.'.format(e=e))
    except:
        import pdb
        pdb.set_trace()
        
def setup_results_dir():
    # make sure there's a valid output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)        
    if not os.path.isdir(output_dir):
        raise RuntimeError("Unable to create output directory {dir}.".format(dir=output_dir))


def summary_headers(m, scenario):
    return (
        ("scenario", "max_demand_response_share", "total_cost", "cost_per_kwh")
        +tuple('cost_per_kwh_'+str(p) for p in m.PERIODS)
        +((("renewable_share_all_years",) + tuple('renewable_share_'+str(p) for p in m.PERIODS))
            if hasattr(m, 'RPSEligiblePower') else tuple())
    )
    
def summary_values(m, scenario):
    demand_components = [c for c in ('lz_demand_mw', 'DemandResponse') if hasattr(m, c)]
    values = []
    
    # scenario name and looping variables
    values.extend([
        scenario,
        m.demand_response_max_share if hasattr(m, 'demand_response_max_share') else 0.0,
    ])
    
    # total cost (all periods)
    values.append(m.Minimize_System_Cost)

    # NPV of total cost / NPV of kWh generated (equivalent to spreading 
    # all costs uniformly over all generation)
    values.append(
        m.Minimize_System_Cost
        / sum(
            m.bring_timepoint_costs_to_base_year[t] * 1000.0 *
            sum(getattr(m, c)[lz, t] for c in demand_components for lz in m.LOAD_ZONES)
            for t in m.TIMEPOINTS 
        )
    )
            
    #  total cost / kWh generated in each period 
    # (both discounted to today, so the discounting cancels out)
    values.extend([
        m.SystemCostPerPeriod[p]
        / sum(
            m.bring_timepoint_costs_to_base_year[t] * 1000.0 *
            sum(getattr(m, c)[lz, t] for c in demand_components for lz in m.LOAD_ZONES)
            for t in m.PERIOD_TPS[p]
        )
        for p in m.PERIODS
    ])

    if hasattr(m, 'RPSEligiblePower'):
        # total renewable share over all periods
        values.append(
            sum(m.RPSEligiblePower[p] for p in m.PERIODS)
            /sum(m.RPSTotalPower[p] for p in m.PERIODS)
        )
        # renewable share during each period
        values.extend([m.RPSEligiblePower[p]/m.RPSTotalPower[p] for p in m.PERIODS])

    return values
    
def create_batch_results_file(m, scenario=None):
    # create a file to hold batch results, but only if it doesn't already exist
    # (if it exists, we keep it, so multiple threads can write to it as needed)

    output_file = os.path.join(output_dir, "summary_all_scenarios.tsv")
    if not os.path.isfile(output_file):
        util.create_table(
            output_file=output_file,
            headings=summary_headers(m, scenario)
        )

def append_batch_results(m, scenario=None):
    # append results to the batch results file
    util.append_table(m, 
        output_file=os.path.join(output_dir, "summary_all_scenarios.tsv"), 
        values=lambda m: summary_values(m, scenario)
    )

def write_results(m, tag=None):
    scenario = tag
    # format the tag to append to file names (if any)
    if tag is not None and tag != "":
        tag = "_"+str(tag)
    else:
        tag = ""
        
    util.write_table(m, 
        output_file=os.path.join(output_dir, "summary{t}.tsv".format(t=tag)), 
        headings=summary_headers(m, scenario),
        values=lambda m: summary_values(m, scenario)
    )
    
    # # write out results
    # util.write_table(m, m.TIMEPOINTS,
    #     output_file=os.path.join(output_dir, "dispatch{t}.tsv".format(t=tag)),
    #     headings=("timepoint_label",)+tuple(m.PROJECTS),
    #     values=lambda m, t: (m.tp_timestamp[t],) + tuple(
    #         get(m.DispatchProj, (p, t), 0.0)
    #         for p in m.PROJECTS
    #     )
    # )
    avg_ts_scale = float(sum(m.ts_scale_to_year[ts] for ts in m.TIMESERIES))/len(m.TIMESERIES)
    util.write_table(
        m, m.LOAD_ZONES, m.TIMEPOINTS,
        output_file=os.path.join(output_dir, "energy_sources{t}.tsv".format(t=tag)), 
        headings=
            ("load_zone", "period", "timepoint_label")
            +tuple(m.FUELS)
            +tuple(m.NON_FUEL_ENERGY_SOURCES)
            +tuple("curtail_"+s for s in m.NON_FUEL_ENERGY_SOURCES)
            +tuple(m.LZ_Energy_Components_Produce)
            +tuple(m.LZ_Energy_Components_Consume)
            +("marginal_cost","peak_day"),
        values=lambda m, z, t: 
            (z, m.tp_period[t], m.tp_timestamp[t]) 
            +tuple(
                sum(get(m.DispatchProjByFuel, (p, t, f), 0.0) for p in m.PROJECTS_BY_FUEL[f])
                for f in m.FUELS
            )
            +tuple(
                sum(get(m.DispatchProj, (p, t), 0.0) for p in m.PROJECTS_BY_NON_FUEL_ENERGY_SOURCE[s])
                for s in m.NON_FUEL_ENERGY_SOURCES
            )
            +tuple(
                sum(
                    get(m.DispatchUpperLimit, (p, t), 0.0) - get(m.DispatchProj, (p, t), 0.0) 
                    for p in m.PROJECTS_BY_NON_FUEL_ENERGY_SOURCE[s]
                )
                for s in m.NON_FUEL_ENERGY_SOURCES
            )
            +tuple(sum(getattr(m, component)[lz, t] for lz in m.LOAD_ZONES)
                    for component in m.LZ_Energy_Components_Produce)
            +tuple(sum(getattr(m, component)[lz, t] for lz in m.LOAD_ZONES)
                    for component in m.LZ_Energy_Components_Consume)
            +(m.dual[m.Energy_Balance[z, t]]/m.bring_timepoint_costs_to_base_year[t],
            'peak' if m.ts_scale_to_year[m.tp_ts[t]] < avg_ts_scale else 'typical')
    )
    
    # installed capacity information
    g_energy_source = lambda t: '/'.join(sorted(m.G_FUELS[t])) if m.g_uses_fuel[t] else m.g_energy_source[t]
    built_proj = tuple(set(
        pr for pe in m.PERIODS for pr in m.PROJECTS if value(m.ProjCapacity[pr, pe]) > 0.001
    ))
    built_tech = tuple(set(m.proj_gen_tech[p] for p in built_proj))
    built_energy_source = tuple(set(g_energy_source(t) for t in built_tech))
    # print "missing energy_source: "+str([t for t in built_tech if g_energy_source(t)==''])

    battery_capacity_mw = lambda m, z, pe: (
        (m.Battery_Capacity[z, pe] * m.battery_max_discharge / m.battery_min_discharge_time)
            if hasattr(m, "Battery_Capacity") else 0.0
    )
    
    util.write_table(m, m.LOAD_ZONES, m.PERIODS, 
        output_file=os.path.join(output_dir, "capacity_by_technology{t}.tsv".format(t=tag)),
        headings=("load_zone", "period") + built_tech + ("hydro", "batteries"),
        values=lambda m, z, pe: (z, pe,) + tuple(
            sum(m.ProjCapacity[pr, pe] for pr in built_proj 
                if m.proj_gen_tech[pr] == t and m.proj_load_zone[pr] == z)
            for t in built_tech
        ) + (
            m.Pumped_Hydro_Capacity_MW[z, pe] if hasattr(m, "Pumped_Hydro_Capacity_MW") else 0,
            battery_capacity_mw(m, z, pe) 
        )
    )
    util.write_table(m, m.LOAD_ZONES, m.PERIODS, 
        output_file=os.path.join(output_dir, "capacity_by_energy_source{t}.tsv".format(t=tag)),
        headings=("load_zone", "period") + built_energy_source + ("hydro", "batteries"),
        values=lambda m, z, pe: (z, pe,) + tuple(
            sum(m.ProjCapacity[pr, pe] for pr in built_proj 
                if g_energy_source(m.proj_gen_tech[pr]) == s and m.proj_load_zone[pr] == z)
            for s in built_energy_source
        ) + (
            m.Pumped_Hydro_Capacity_MW[z, pe] if hasattr(m, "Pumped_Hydro_Capacity_MW") else 0,
            battery_capacity_mw(m, z, pe)
        )
    )
    # util.write_table(m, m.PERIODS,
    #     output_file=os.path.join(output_dir, "capacity{t}.tsv".format(t=t)),
    #     headings=("period",)+built_proj,
    #     values=lambda m, pe: (pe,) + tuple(m.ProjCapacity[pr, pe] for pr in built_proj)
    # )


    if hasattr(m, 'RFMSupplyTierActivate'):
        util.write_table(m, m.RFM_SUPPLY_TIERS,
            output_file=os.path.join(output_dir, "rfm_activate{t}.tsv".format(t=tag)), 
            headings=("market", "period", "tier", "activate"),
            values=lambda m, r, p, st: (r, p, st, m.RFMSupplyTierActivate[r, p, st])
        )
    

    # import pprint
    # b=[(pr, pe, value(m.BuildProj[pr, pe]), m.proj_gen_tech[pr], m.proj_overnight_cost[pr, pe]) for (pr, pe) in m.BuildProj if value(m.BuildProj[pr, pe]) > 0]
    # bt=set(x[3] for x in b) # technologies
    # pprint([(t, sum(x[2] for x in b if x[3]==t), sum(x[4] for x in b if x[3]==t)/sum(1.0 for x in b if x[3]==t)) for t in bt])


###############
    
if __name__ == '__main__':
    main()
