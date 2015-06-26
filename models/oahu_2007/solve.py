#!/usr/local/bin/python

import sys, os, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../switch')))

import util

from pyomo.environ import *
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition

import switch_mod.utilities as utilities

print "loading model..."

switch_modules = (
    'switch_mod', 'project.unitcommit', 'project.unitcommit.discrete', 'fuel_cost'
)
utilities.load_modules(switch_modules)
switch_model = utilities.define_AbstractModel(switch_modules)
switch_model.iis = Suffix(direction=Suffix.IMPORT)

inputs_dir = 'inputs'
switch_data = utilities.load_data(switch_model, inputs_dir, switch_modules)
switch_instance = switch_model.create(switch_data)

opt = SolverFactory("cplex", tee=True, solver_io="nl")
# tell cplex to find an irreducible infeasible set (and report it)
opt.options['iisfind'] = 1

# relax the integrality constraints, to allow commitment constraints to match up with 
# number of units available
opt.options['mipgap'] = 0.001

print "solving model..."
start = time.time()
results = opt.solve(switch_instance, keepfiles=False, tee=True, symbolic_solver_labels=True)
print "Total time in solver: {t}s".format(t=time.time()-start)

# results.write()
if switch_instance.load(results):
    if results.solver.termination_condition == TerminationCondition.infeasible:
        print "Model was infeasible; no results will be stored."
        print "Irreducible Infeasible Set (IIS) returned by solver:"
        print "\n".join(c.cname() for c in switch_instance.iis)
        if util.interactive_session:
            print "Unsolved model is available as switch_instance."
    else:
        # something other than infeasible...
        if util.interactive_session:
            print "Model solved successfully."

        # write out results
        try:
            util.write_table(switch_instance, switch_instance.TIMEPOINTS,
                output_file=os.path.join("outputs", "dispatch.txt"), 
                headings=("timepoint_label",)+tuple(switch_instance.PROJECTS),
                values=lambda m, t: (m.tp_timestamp[t],) + tuple(
                    m.DispatchProj[p, t] if (p, t) in m.PROJ_DISPATCH_POINTS else 0.0 
                    for p in m.PROJECTS
                )
            )
            util.write_table(switch_instance, switch_instance.TIMEPOINTS, 
                output_file=os.path.join("outputs", "load_balance.txt"), 
                headings=("timepoint_label",)+tuple(switch_instance.LZ_Energy_Balance_components),
                values=lambda m, t: (m.tp_timestamp[t],) + tuple(
                    sum(getattr(m, component)[lz, t] for lz in m.LOAD_ZONES)
                    for component in m.LZ_Energy_Balance_components
                )
            )
        except Exception, e:
            print "An error occurred while writing results:"
            print "ERROR:", e
        if util.interactive_session:
            print "Solved model is available as switch_instance."
else:
    print "ERROR: unable to load solver results. Problem may be infeasible."
