#!/usr/bin/env python

import sys, os, time, traceback, fcntl

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
import util
from util import tic, toc, log, get

add_relative_path('.') # components for this particular study

add_relative_path('..', 'pumped_hydro') # components reused from the pumped_hydro study

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
    scenarios=[
        ['rps', 'demand_response', 'pumped_hydro', 'no_wind', 'ph_year=2037', 'ph_mw=150', 'tag=rps_no_wind_ph2037_150'],
        ['no_rps', 'no_renewables', 'no_demand_response', 'no_pumped_hydro', 'tag=no_renewables'],
        ['no_rps', 'demand_response', 'pumped_hydro', 'tag=free'],
        ['rps', 'demand_response', 'pumped_hydro', 'tag=rps'],
        ['rps', 'demand_response', 'pumped_hydro', 'no_wind', 'tag=rps_no_wind'],
    ]

    # catch errors so the user can continue with a solved model
    # try:
    for scenario in scenarios:
        scenarios_to_do = list()
        args=dict() # have to create a new dict, not just assign an empty one, which would get reused
        for arg in sys.argv[1:] + scenario: # evaluate command line arguments, then scenario arguments
            if '=' in arg:   # e.g., tag=base
                (label, val) = arg.split('=', 1)
                for t in [int, float, str]:  # try to convert the value to these types, in order
                    try:
                        # convert the value to the specified type
                        val=t(val)
                        break
                    except ValueError:
                        # ignore value errors, move on to the next
                        pass
                if label == 'tag' and 'tag' in args:
                    # concatenate tags, otherwise override previous values
                    val = args['tag'] + '_' + val
                if label == 'scenario':
                    # they can specify several, but each separately: scenario=a scenario=b
                    scenarios_to_do.append(val)
                    continue    # don't pass scenario as an argument to solve()
                args[label] = val
            elif arg.startswith('no_'):     # e.g., no_pumped_hydro
                args[arg[3:]] = False
            else:                           # e.g., ev
                args[arg] = True
        # if they list scenario name(s) on the command line, only run those
        if len(scenarios_to_do) == 0: 
            if scenario_already_run(args["tag"]):
                print 'scenario {t} already completed; skipping.'.format(t=args["tag"])
                continue
        else:
            if args['tag'] in scenarios_to_do:
                # always run the scenario if specified on command line
                scenario_already_run(args["tag"])      # flag that the scenario is running
            else:
                # there's a list of scenarios and this isn't in it
                continue
        print 'running scenario {t}'.format(t=args["tag"])
        print 'arguments: {}'.format(args)
        solve(**args)


# except Exception, e:
#     traceback.print_exc()
#     print "ERROR:", e

def solve(
    inputs='inputs', outputs='outputs', 
    rps=True, renewables=True, wind=None,
    demand_response=True,
    ev=None, 
    pumped_hydro=True, ph_year=None, ph_mw=None,
    tag=None,
    thread=None, nthreads=3
    ):
    # load and solve the model, using specified configuration
    # NOTE: this version solves repeatedly with different DR targets
    global switch_model, switch_instance, results, output_dir

    modules = ['switch_mod', 'fuel_markets', 'fuel_markets_expansion', 'project.no_commit', 'switch_patch', 'batteries']
    if rps:
        modules.append('rps')
    if not renewables:
        modules.append('no_renewables')
    elif wind is False:
        modules.append('no_wind')
    if demand_response:
        modules.append('simple_dr')
        # repeat with a range of DR shares
        all_dr_shares = [0.20]
        if thread is None:
            dr_shares = all_dr_shares
        else:
            # take every nth element from all_dr_shares, starting with element i, where i=thread (1-based) and n=nthreads
            dr_shares = [all_dr_shares[x] for x in range(thread-1, len(all_dr_shares), nthreads)]
    else:   # no_demand_response
        dr_shares = [0.00]
    if ev:
        # user asked for ev
        modules.append('ev')
    if ev is False:
        # user asked for no_ev (count transport emissions but don't allow EVs)
        modules.append('no_ev')
    if pumped_hydro:
        modules.append('pumped_hydro')
        
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
            switch_model.LOAD_ZONES, switch_model.PERIODS, 
            rule=lambda m, z, p:
                m.BuildPumpedHydroMW[z, p] == 0 if p != ph_year else Constraint.Skip
        )

    toc()   # done defining model

    log("loading model data from {} dir... ".format(inputs)); tic()
    switch_instance = switch_model.load_inputs(inputs_dir=inputs)
    toc()

    output_dir = outputs
    setup_results_dir()
    create_batch_results_file(switch_instance, tag=tag)
        
    log("dr_shares = " + str(dr_shares) + "\n")
    for dr_share in dr_shares:
        if demand_response:
            switch_instance.demand_response_max_share = dr_share
            switch_instance.preprocess()
            
        tic()
        log("solving model with max DR={dr}...\n".format(dr=dr_share))
        results = opt.solve(switch_instance, keepfiles=False, tee=True,
            symbolic_solver_labels=True, suffixes=['dual', 'iis'])
        log("Solver finished; "); toc()

        # results.write()
        log("loading solution... "); tic()
        # Pyomo changed their interface for loading results somewhere 
        # between 4.0.x and 4.1.x in a way that was not backwards compatible.
        # Make the code accept either version
        if hasattr(switch_instance, 'solutions'):
            # Works in Pyomo version 4.1.x
            switch_instance.solutions.load_from(results)
        else:
            # Works in Pyomo version 4.0.9682
            switch_instance.load(results)
        toc()
    
        if results.solver.termination_condition == TerminationCondition.infeasible:
            print "Model was infeasible; Irreducible Infeasible Set (IIS) returned by solver:"
            print "\n".join(c.cname() for c in switch_instance.iis)
            if util.interactive_session:
                print "Unsolved model is available as switch_instance."
            raise RuntimeError("Infeasible model")


        if util.interactive_session:
            print "Model solved successfully."
            print "Solved model is available as switch_instance."
    
        print "\n\n======================================================="
        print "Solved model"
        print "======================================================="
        print "Total cost: ${v:,.0f}".format(v=value(switch_instance.Minimize_System_Cost))
    
        if pumped_hydro:
            switch_instance.BuildPumpedHydroMW.pprint()

        append_batch_results(switch_instance, tag=tag)
        t = "" if tag is None else str(tag) + "_"
        write_results(switch_instance, tag=t+'dr_share_'+str(dr_share))


def scenario_already_run(scenario):
    """Add the specified scenario to the list in completed_scenarios.txt. Return False if it wasn't there already."""
    with open('completed_scenarios.txt', 'a+') as f:
        # wait for exclusive access to the list (to avoid writing the same scenario twice in a race condition)
        fcntl.flock(f, fcntl.LOCK_EX)
        # file starts with pointer at end; move to start
        f.seek(0, 0)                    
        if scenario + '\n' in f:
            already_run = True
        else:
            already_run = False
            # append name to the list (will always go at end, because file was opened in 'a' mode)
            f.write(scenario + '\n')
        fcntl.flock(f, fcntl.LOCK_UN)
    return already_run


def setup_results_dir():
    # make sure there's a valid output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)        
    if not os.path.isdir(output_dir):
        raise RuntimeError("Unable to create output directory {dir}.".format(dir=output_dir))

def create_batch_results_file(m, tag=None):
    # create a file to hold batch results, but only if it doesn't already exist
    # (if it exists, we keep it, so multiple threads can write to it as needed)

    # format the tag to append to file names (if any)
    if tag is not None:
        t = "_"+str(tag)
    else:
        t = ""
    output_file = os.path.join(output_dir, "summary{t}.txt".format(t=t))
    if not os.path.isfile(output_file):
        util.create_table(
            output_file=output_file,
            headings=
                ("max_demand_response_share", "total_cost", "cost_per_kwh")
                +tuple('cost_per_kwh_'+str(p) for p in m.PERIODS)
        )
    
def append_batch_results(m, tag=None):
    if tag is not None:
        t = "_"+str(tag)
    else:
        t = ""
    # append results to the batch results file
    demand_components = [c for c in ('lz_demand_mw', 'DemandResponse') if hasattr(m, c)]
    util.append_table(m, 
        output_file=os.path.join(output_dir, "summary{t}.txt".format(t=t)), 
        values=lambda m: (
            m.demand_response_max_share if hasattr(m, 'demand_response_max_share') else 0.0,
            m.Minimize_System_Cost,
            # next expression calculates NPV of total cost / NPV of kWh generated
            m.Minimize_System_Cost
                / sum(
                    m.bring_timepoint_costs_to_base_year[t] * 1000.0 *
                    sum(getattr(m, c)[lz, t] for c in demand_components for lz in m.LOAD_ZONES)
                    for t in m.TIMEPOINTS 
                )
        ) + tuple(
            # next expression calculates NPV of total cost / NPV of kWh generated in each period
            m.SystemCostPerPeriod[p]
                / sum(
                    m.bring_timepoint_costs_to_base_year[t] * 1000.0 *
                    sum(getattr(m, c)[lz, t] for c in demand_components for lz in m.LOAD_ZONES)
                    for t in m.PERIOD_TPS[p]
                )
            for p in m.PERIODS
        )
    )

def write_results(m, tag=None):
    # format the tag to append to file names (if any)
    if tag is not None:
        t = "_"+str(tag)
    else:
        t = ""
        
    # write out results
    util.write_table(m, m.TIMEPOINTS,
        output_file=os.path.join(output_dir, "dispatch{t}.txt".format(t=t)), 
        headings=("timepoint_label",)+tuple(m.PROJECTS),
        values=lambda m, t: (m.tp_timestamp[t],) + tuple(
            get(m.DispatchProj, (p, t), 0.0)
            for p in m.PROJECTS
        )
    )
    util.write_table(
        m, m.LOAD_ZONES, m.TIMEPOINTS, 
        output_file=os.path.join(output_dir, "energy_sources{t}.txt".format(t=t)), 
        headings=
            ("load_zone", "timepoint_label")
            +tuple(m.FUELS)
            +tuple(m.NON_FUEL_ENERGY_SOURCES)
            +tuple("curtail_"+s for s in m.NON_FUEL_ENERGY_SOURCES)
            +tuple(m.LZ_Energy_Components_Produce)
            +tuple(m.LZ_Energy_Components_Consume)
            +("marginal_cost",),
        values=lambda m, z, t: 
            (z, m.tp_timestamp[t]) 
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
            +(m.dual[m.Energy_Balance[z, t]]/m.bring_timepoint_costs_to_base_year[t],)
    )
    
    built_proj = tuple(set(
        pr for pe in m.PERIODS for pr in m.PROJECTS if value(m.ProjCapacity[pr, pe]) > 0.001
    ))
    util.write_table(m, m.PERIODS,
        output_file=os.path.join(output_dir, "capacity{t}.txt".format(t=t)), 
        headings=("period",)+built_proj,
        values=lambda m, pe: (pe,) + tuple(m.ProjCapacity[pr, pe] for pr in built_proj)
    )
    if hasattr(m, 'RFMSupplyTierActivate'):
        util.write_table(m, m.RFM_SUPPLY_TIERS,
            output_file=os.path.join(output_dir, "rfm_activate{t}.txt".format(t=t)), 
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
