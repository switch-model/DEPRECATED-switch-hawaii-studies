#!/usr/local/bin/python

import sys, os, time
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../switch')))

from pyomo.environ import *
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition

opt = SolverFactory("cplex", tee=True, solver_io="nl")
# tell cplex to find an irreducible infeasible set (and report it)
opt.options['iisfind'] = 1

# relax the integrality constraints, to allow commitment constraints to match up with 
# number of units available
opt.options['mipgap'] = 0.001

import switch_mod.utilities as utilities
import util
import demand_response

print "loading model..."

# tell pyomo to make all parameters mutable by default
# (I only need to change lz_demand_mw, but this is currently the only way to make
# any parameter mutable without changing the core code.)
# NOTE: this causes errors like "TypeError: unhashable type: '_ParamData'" 
# when any parameters are used as indexes into a set (e.g., m.ts_scale_to_period[ts])
# This may be a pyomo bug, but it's hard to work around in the short term.
# Param.DefaultMutable = True

switch_modules = (
    'switch_mod', 'project.unitcommit', 'project.unitcommit.discrete', 'fuel_cost'
)

# patch utilities module to load my module
if not hasattr(utilities, 'orig_define_components'):
    # don't save the function again if it's already been saved (e.g., when reloading solve.py)
    utilities.orig_define_components = utilities._define_components
def my_define_components(module_list, model):
    utilities.orig_define_components(module_list, model)
    if 'fuel_cost' in module_list:
        # only run this when we're working on the main list, 
        # not when recursing through sub-modules
        demand_response.define_components(model)
utilities._define_components = my_define_components

utilities.load_modules(switch_modules)
switch_model = utilities.define_AbstractModel(switch_modules)

switch_model.iis = Suffix(direction=Suffix.IMPORT)
switch_model.dual = Suffix(direction=Suffix.IMPORT)

inputs_dir = 'inputs'

switch_data = utilities.load_data(switch_model, inputs_dir, switch_modules)


switch_instance = switch_model.create(switch_data)

results = None

def iterate():
    global switch_model, switch_data, switch_instance, results
    for i in range(5):
        # solve the model repeatedly, iterating with a new demand function

        print "solving model..."
        start = time.time()
        results = opt.solve(switch_instance, keepfiles=False, tee=True, symbolic_solver_labels=True, suffixes=['dual', 'iis'])
        print "Total time in solver: {t}s".format(t=time.time()-start)

        # results.write()
        if not switch_instance.load(results):
            raise RuntimeError("Unable to load solver results. Problem may be infeasible.")

        if results.solver.termination_condition == TerminationCondition.infeasible:
            print "Model was infeasible; Irreducible Infeasible Set (IIS) returned by solver:"
            print "\n".join(c.cname() for c in switch_instance.iis)
            if util.interactive_session:
                print "Unsolved model is available as switch_instance."
            raise RuntimeError("Infeasible model")


        if util.interactive_session:
            print "Model solved successfully."
            print "Solved model is available as switch_instance."

        # write out results
        util.write_table(switch_instance, switch_instance.TIMEPOINTS,
            output_file=os.path.join("outputs", "dispatch_{b}.txt".format(b=i)), 
            headings=("timepoint_label",)+tuple(switch_instance.PROJECTS),
            values=lambda m, t: (m.tp_timestamp[t],) + tuple(
                m.DispatchProj[p, t] if (p, t) in m.PROJ_DISPATCH_POINTS else 0.0 
                for p in m.PROJECTS
            )
        )
        util.write_table(switch_instance, switch_instance.TIMEPOINTS, 
            output_file=os.path.join("outputs", "load_balance_{b}.txt".format(b=i)), 
            headings=("timepoint_label",)+tuple(switch_instance.LZ_Energy_Balance_components),
            values=lambda m, t: (m.tp_timestamp[t],) + tuple(
                sum(getattr(m, component)[lz, t] for lz in m.LOAD_ZONES)
                for component in m.LZ_Energy_Balance_components
            )
        )
        
        import pdb; pdb.set_trace()
        
        print "attaching new demand bid to model"
        demand_response.update_demand(switch_instance)
        switch_instance.preprocess()

if __name__ == '__main__':
    # catch errors so the user can continue with a solved model
    try:
        iterate()
    except Exception, e:
        print "ERROR:", e
    