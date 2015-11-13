# we are defining an augmented production cost model mode for switch, which must be run iteratively.
# In this mode, you solve a main model, then call a power flow model which gives back a list of
# congested lines to consider and PTDFs for those lines under the particular contingency where
# they become congested. 
# (Since the network doesn't change in this model, the power flow module could cache the PTDFs.) 

# Note: it doesn't matter too much what we use for the slack bus for the PTDFs, because all 
# injections will be balanced by withdrawals, so there will be no net transfer to the slack bus(es)
# or only a small amount, which will be modeled correctly.
# i.e., the net flow to the slack bus(es) will always be the same as is assumed by the PTDFs.
# i.e., it will be the same as if we wheeled all the power to the slack bus(es) and then back
# to wherever it will actually be used.

# For now this is not an expansion model; if we wanted it to be, we could somehow include the 
# effect of each candidate transmission expansion on the PTDFs? and then return PTDFs for the 
# currently selected plan? Note: if a new transmission line is active, then the effect on PTDFs
# from deactivating it would be the same as the PTDFs when it is inactivated as a contingency...

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

import sys, os
from pyomo.environ import *

add_relative_path('switch', 'switch-hawaii-core')   # standard switch model
from switch_mod.utilities import define_AbstractModel
import switch_mod.utilities

import trans_branch_flow

#opt = switch_mod.utilities.default_solver()
opt = SolverFactory("cplex", solver_io="nl")
# tell cplex to find an irreducible infeasible set (and report it)
opt.options['iisfind'] = 1

# # relax the integrality constraints, to allow commitment constraints to match up with
# # number of units available
# opt.options['mipgap'] = 0.001
# # display more information during solve
# opt.options['display'] = 1
# opt.options['bardisplay'] = 1
# opt.options['mipdisplay'] = 2
# opt.options['primalopt'] = ""   # this is how you specify single-word arguments
# opt.options['advance'] = 2
# #opt.options['threads'] = 1


def _solve(m):
    """Solve instance of switch model, using the specified objective, then load the results"""
    results = opt.solve(m, keepfiles=False, tee=True,
        symbolic_solver_labels=True, suffixes=['dual', 'iis'])

    # results.write()
    # Pyomo changed their interface for loading results somewhere 
    # between 4.0.x and 4.1.x in a way that was not backwards compatible.
    # Make the code accept either version
    if hasattr(m, 'solutions'):
        # Works in Pyomo version 4.1.x
        m.solutions.load_from(results)
    else:
        # Works in Pyomo version 4.0.9682
        m.load(results)

    if results.solver.termination_condition == pyomo.opt.TerminationCondition.infeasible:
        print "Model was infeasible; Irreducible Infeasible Set (IIS) returned by solver:"
        print "\n".join(c.cname() for c in i.iis)
        print "Model instance is available as 'i'."
        import pdb; pdb.set_trace()
    
    return results


# converge(m, [trans_branch_flow])

def converge(m, modules):
    """Call iterate() on each specified module until convergence is reached 
    (all iterate() functions return True). 
    Iterations will be nested from the first module (outer loop) to the last 
    (inner loop, iterated until convergence before each step of the earlier modules).
    If an entry in the modules list is a tuple or list of modules, then all of those
    will be iterated in the same loop until all of them converge."""
    current_modules = modules[0]
    j = 0
    converged = False
    if not hasattr(current_modules, '__iter__'):
        current_modules = [current_modules]
    while not converged:
        # converge the lower-priority modules, if any (inner loop)
        if len(modules) > 1:
            converge(m, modules[1:])
        # take one step in the current module (outer loop)
        converged = True
        j += 1
        for module in current_modules:
            # How does this work? iterate() needs to setup the model,
            # then we solve it from here, then iterate gets the results 
            # and tests for convergence. Also, will there be any solution 
            # before this gets called?
            print "iteration {j} for module {mod}".format(j=j, mod=module)
            if hasattr(module, 'pre_iterate'): 
                module.pre_iterate(m, j)
            _solve(m)
            print "objective value:", value(m.Minimize_System_Cost)
            # print "cost_components_tp:", m.cost_components_tp
            print "\ncosts by period and component:"
            costs = [
                (p, tp_cost, value(sum(getattr(m, tp_cost)[t] * m.tp_weight_in_year[t] for t in m.PERIOD_TPS[p])))
                    for p in m.PERIODS for tp_cost in m.cost_components_tp
            ]
            print costs
                        
            
            converged = module.post_iterate(m, j) and converged
            #import pdb; pdb.set_trace()
    # one more solve to get results with final post-iteration adjustments and valid duals
    # (otherwise duals tend to get clobbered by post-iteration adjustments)
    return _solve(m)
    
m = define_AbstractModel(
    'switch_mod', 'project.no_commit', 'fuel_cost', 'trans_branch_flow'
)
m.iis = Suffix(direction=Suffix.IMPORT)
m.dual = Suffix(direction=Suffix.IMPORT)
i = m.load_inputs(inputs_dir="inputs")
# results = _solve(i)
results = converge(i, [trans_branch_flow])
#import pdb; pdb.set_trace()
results.write()
i.pprint()

