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

add_relative_path('.') # components for this particular study

opt = SolverFactory("cplex", solver_io="nl")
# tell cplex to find an irreducible infeasible set (and report it)
#opt.options['iisfind'] = 1

# relax the integrality constraints, to allow commitment constraints to match up with 
# number of units available
opt.options['mipgap'] = 0.001

# label to attach to results files
tag = None

print "loading model..."

# tell pyomo to make all parameters mutable by default
# (I only need to change lz_demand_mw, but this is currently the only way to make
# any parameter mutable without changing the core code.)
# NOTE: this causes errors like "TypeError: unhashable type: '_ParamData'" 
# when any parameters are used as indexes into a set (e.g., m.ts_scale_to_period[ts])
# This may be a pyomo bug, but it's hard to work around in the short term.
# Param.DefaultMutable = True

switch_model = define_AbstractModel(
    'switch_mod', 'fuel_cost', 'project.no_commit', 
    'switch_patch',
    'rps', 'batteries' #, 'demand_response'
)
switch_model.iis = Suffix(direction=Suffix.IMPORT)
switch_model.dual = Suffix(direction=Suffix.IMPORT)

switch_instance = switch_model.load_inputs(inputs_dir="inputs")

results = None  # defined globally for convenient access in interactive session

def solve():
    global switch_model, switch_instance, results, tag

    print "solving model..."
    start = time.time()
    results = opt.solve(switch_instance, keepfiles=False, tee=True, 
        symbolic_solver_labels=True, suffixes=['dual', 'iis'])
    print "Total time in solver: {t}s".format(t=time.time()-start)

    # results.write()
    switch_instance.solutions.load_from(results)

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
        
    write_results(tag=tag)


def write_results(tag=None):
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
    util.write_table(switch_instance, switch_instance.TIMEPOINTS,
        output_file=os.path.join(output_dir, "dispatch{t}.txt".format(t=t)), 
        headings=("timepoint_label",)+tuple(switch_instance.PROJECTS),
        values=lambda m, t: (m.tp_timestamp[t],) + tuple(
            m.DispatchProj_AllTimePoints[p, t] 
            for p in m.PROJECTS
        )
    )
    util.write_table(
        switch_instance, switch_instance.LOAD_ZONES, switch_instance.TIMEPOINTS, 
        output_file=os.path.join(output_dir, "energy_sources{t}.txt".format(t=t)), 
        headings=
            ("load_zone", "timepoint_label")
            +tuple(switch_instance.FUELS)
            +tuple(switch_instance.NON_FUEL_ENERGY_SOURCES)
            +tuple("curtail_"+s for s in switch_instance.NON_FUEL_ENERGY_SOURCES)
            +tuple(switch_instance.LZ_Energy_Components_Produce)
            +tuple(switch_instance.LZ_Energy_Components_Consume)
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

    # import pprint
    # b=[(pr, pe, value(m.BuildProj[pr, pe]), m.proj_gen_tech[pr], m.proj_overnight_cost[pr, pe]) for (pr, pe) in m.BuildProj if value(m.BuildProj[pr, pe]) > 0]
    # bt=set(x[3] for x in b) # technologies
    # pprint([(t, sum(x[2] for x in b if x[3]==t), sum(x[4] for x in b if x[3]==t)/sum(1.0 for x in b if x[3]==t)) for t in bt])


###############
    
if __name__ == '__main__':
    # catch errors so the user can continue with a solved model
    try:
        solve()
    except Exception, e:
        traceback.print_exc()
        print "ERROR:", e
    