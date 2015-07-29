#!/usr/local/bin/python

import sys, os, time, traceback

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
from util import tic, toc, log

add_relative_path('.') # components for this particular study

opt = SolverFactory("cplex", solver_io="nl")
# tell cplex to find an irreducible infeasible set (and report it)
#opt.options['iisfind'] = 1

# relax the integrality constraints, to allow commitment constraints to match up with 
# number of units available
opt.options['mipgap'] = 0.001
# display more information during solve
opt.options['display'] = 1
opt.options['bardisplay'] = 1

# define global variables for convenient access in interactive session
switch_model = None
switch_instance = None
results = None

def solve(
    inputs='inputs', 
    rps=True, demand_response=True, renewables=True, ev=True, pumped_hydro=True, 
    tag=None
    ):
    global switch_model, switch_instance, results

    modules = ['switch_mod', 'fuel_cost', 'project.no_commit', 'switch_patch', 'batteries']
    if rps:
        modules.append('rps')
    if not renewables:
        modules.append('no_renewables')
    if demand_response:
        modules.append('simple_dr')
    if ev:
        modules.append('ev')
    else:
        modules.append('no_ev')
    if pumped_hydro:
        modules.append('pumped_hydro')
        
    log('using modules: {m}\n'.format(m=modules))

    log("defining model... "); tic()
    switch_model = define_AbstractModel(*modules)
    switch_model.iis = Suffix(direction=Suffix.IMPORT)
    switch_model.dual = Suffix(direction=Suffix.IMPORT)

    # # force re-building wind in 2045, and see if that makes the model infeasible or prevents earlier building
    # switch_model.Force_Wind = Constraint(rule=lambda m:
    #     m.BuildProj["Oahu_Wind_503_na", 2045] == 117.5
    # )

    toc()   # done defining model

    log("loading model data from {} dir... ".format(inputs)); tic()
    switch_instance = switch_model.load_inputs(inputs_dir=inputs)
    toc()

    log("solving model...\n"); tic()
    results = opt.solve(switch_instance, keepfiles=False, tee=True, 
        symbolic_solver_labels=True, suffixes=['dual', 'iis'])
    log("Solver finished; "); toc()

    # results.write()
    log("loading solution... "); tic()
    switch_instance.solutions.load_from(results)
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
        
    write_results(switch_instance, tag=tag)


def write_results(m, tag=None):
    # format the tag to append to file names (if any)
    if tag is not None:
        t = "_"+str(tag)
    else:
        t = ""
        
    # make sure there's a valid output directory
    output_dir = "outputs"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)        
    if not os.path.isdir(output_dir):
        raise RuntimeError("Unable to create output directory {dir}.".format(dir=output_dir))
    
    # write out results
    util.write_table(m, m.TIMEPOINTS,
        output_file=os.path.join(output_dir, "dispatch{t}.txt".format(t=t)), 
        headings=("timepoint_label",)+tuple(m.PROJECTS),
        values=lambda m, t: (m.tp_timestamp[t],) + tuple(
            m.DispatchProj_AllTimePoints[p, t] 
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
                sum(m.DispatchProj_AllTimePoints[p, t] for p in m.PROJECTS_BY_FUEL[f])
                for f in m.FUELS
            )
            +tuple(
                sum(m.DispatchProj_AllTimePoints[p, t] for p in m.PROJECTS_BY_NON_FUEL_ENERGY_SOURCE[s])
                for s in m.NON_FUEL_ENERGY_SOURCES
            )
            +tuple(
                sum(
                    m.DispatchUpperLimit_AllTimePoints[p, t] - m.DispatchProj_AllTimePoints[p, t] 
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
    

    # import pprint
    # b=[(pr, pe, value(m.BuildProj[pr, pe]), m.proj_gen_tech[pr], m.proj_overnight_cost[pr, pe]) for (pr, pe) in m.BuildProj if value(m.BuildProj[pr, pe]) > 0]
    # bt=set(x[3] for x in b) # technologies
    # pprint([(t, sum(x[2] for x in b if x[3]==t), sum(x[4] for x in b if x[3]==t)/sum(1.0 for x in b if x[3]==t)) for t in bt])


###############
    
if __name__ == '__main__':
    args={}
    for arg in sys.argv[1:]:
        if arg.startswith('no_'):
            args[arg[3:]] = False
        elif arg.startswith('tag='):
            args['tag'] = arg[4:]   # label to attach to results files
        elif arg.startswith('inputs='):
            args['inputs'] = arg[7:]   # directory to read inputs from
        else:
            args[arg] = True
    # catch errors so the user can continue with a solved model
    try:
        solve(**args)
    except Exception, e:
        traceback.print_exc()
        print "ERROR:", e
    