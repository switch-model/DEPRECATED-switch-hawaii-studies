#!/usr/bin/env python
"""Generate a model for use with the progressive hedging algorithm.

If loaded as a module by runph, this creates a "model" object which can be
used to define the model.

If called as a script, this creates ReferenceModel.dat in the inputs directory,
with all the data needed to instantiate the model.

This can also be loaded interactively to experiment with instantiating from the
ReferenceModel.dat file ("import ReferenceModel; ReferenceModel.load_dat_inputs()")
"""

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
from util import get

add_relative_path('.') # components for this particular study

print "loading model..."

inputs_dir = "inputs_tiny"

model = define_AbstractModel(
    'switch_mod', 
    'fuel_markets', 'fuel_markets_expansion',
    'project.no_commit', 
    'switch_patch',
    'rps', 'emission_rules',
    'demand_response_simple', 
    'ev',
    'pumped_hydro',
    'hydrogen', 
    'batteries'
)
# add dummy expressions to keep runph happy
# note: we may need to delve into the objective expression
# and apportion its elements between these based on whether
# they are in the build_variables list or not
model.BuildCost = Expression(rule=lambda m: 0.0)
model.OperateCost = Expression(rule=lambda m: m.Minimize_System_Cost.expr)
# define upper and lower reduced costs to use when setting rho
# model.iis = Suffix(direction=Suffix.IMPORT)
model.dual = Suffix(direction=Suffix.IMPORT)
model.urc = Suffix(direction=Suffix.IMPORT)
model.lrc = Suffix(direction=Suffix.IMPORT)
model.rc = Suffix(direction=Suffix.IMPORT)

instance = None

# if loaded as ReferenceModel.py, just yield the model
# if loaded directly with an output file argument, write the dat file

def load_inputs():
    global instance
    print "loading inputs..."
    instance = model.load_inputs(inputs_dir=inputs_dir)

def load_dat_inputs():
    global instance
    # TODO: this needs to load from RootNode.dat and also a scenario file
    instance = model.create_instance(dat_file_name())
    
def dat_file_dir():
    return os.path.join(inputs_dir, "pha")

def dat_file_name():
     return os.path.join(dat_file_dir(), "RootNode.dat")
    
def save_dat_files():
    dat_file = dat_file_name()
    print "saving {}...".format(dat_file)
    utilities.save_inputs_as_dat(
        model, instance, save_path=dat_file,
        exclude=["rfm_supply_tier_cost", "rfm_supply_tier_limit", "rfm_supply_tier_fixed_cost"])

    # identify scenarios, leaves and shared variables
    n_scenarios = 4
    n_digits = 4
    scenarios = [str(i).zfill(n_digits) for i in range(n_scenarios)]
    
    dat_file = os.path.join(dat_file_dir(), "ScenarioStructure.dat")
    print "saving {}...".format(dat_file)
    with open(dat_file, "w") as f:
        # use show only the changed data in the dat files for each scenario
        f.write("param ScenarioBasedData := False ;\n\n")
        
        f.write("set Stages := Build Operate ;\n\n")

        f.write("set Nodes := RootNode \n")
        for s in scenarios:
            f.write("    fuel_supply_curves_{}\n".format(s))
        f.write(";\n\n")

        f.write("param NodeStage := RootNode Build\n")
        for s in scenarios:
            f.write("    fuel_supply_curves_{} Operate\n".format(s))
        f.write(";\n\n")
        
        f.write("set Children[RootNode] := \n")
        for s in scenarios:
            f.write("    fuel_supply_curves_{}\n".format(s))
        f.write(";\n\n")
    
        f.write("param ConditionalProbability := RootNode 1.0\n")
        probs = [1.0/n_scenarios] * (n_scenarios - 1) # evenly spread among all scenarios
        probs.append(1.0 - sum(probs))  # lump the remainder into the last scenario
        for (s, p) in zip(scenarios, probs):
            f.write("    fuel_supply_curves_{s} {p}\n".format(s=s, p=p))
        f.write(";\n\n")

        f.write("set Scenarios :=  \n")
        for s in scenarios:
            f.write("    Scenario_{}\n".format(s))
        f.write(";\n\n")

        f.write("param ScenarioLeafNode := \n")
        for s in scenarios:
            f.write("    Scenario_{s} fuel_supply_curves_{s}\n".format(s=s, p=p))
        f.write(";\n\n")

        def write_var_name(f, cname):
            if hasattr(instance, cname):
                dimen = getattr(instance, cname).index_set().dimen
                indexing = "" if dimen == 0 else (",".join(["*"]*dimen))
                f.write("    {cn}[{dim}]\n".format(cn=cname, dim=indexing))

        # all build variables (and fuel market expansion) go in the Build stage
        build_vars = [
            "BuildProj", "BuildBattery", 
            "BuildPumpedHydroMW", "BuildAnyPumpedHydro",
            "RFMSupplyTierActivate",
            "BuildElectrolyzerMW", "BuildLiquifierKgPerHour", "BuildLiquidHydrogenTankKg",
            "BuildFuelCellMW"
        ]
        f.write("set StageVariables[Build] := \n")
        for cn in build_vars:
            write_var_name(f, cn)
        f.write(";\n\n")
        
        # all other variables go in the Operate stage
        operate_vars = [
            c.cname() for c in instance.component_objects() 
                if isinstance(c, pyomo.core.base.var.Var) and c.cname() not in build_vars
        ]
        f.write("set StageVariables[Operate] := \n")
        for cn in operate_vars:
            write_var_name(f, cn)
        f.write(";\n\n")

        f.write("param StageCostVariable := \n")
        f.write("    Build BuildCost\n")
        f.write("    Operate OperateCost\n")
        f.write(";\n\n")
        # note: this uses dummy variables for now; if real values are needed,
        # it may be possible to construct them by extracting all objective terms that 
        # involve the Build variables.
        
def solve():
    # can be accessed from interactive prompt via import ReferenceModel; ReferenceModel.solve()
    print "solving model..."
    opt = SolverFactory("cplex", solver_io="nl")
    # tell cplex to find an irreducible infeasible set (and report it)
    # opt.options['iisfind'] = 1

    # relax the integrality constraints, to allow commitment constraints to match up with 
    # number of units available
    opt.options['mipgap'] = 0.001
    # display more information during solve
    # opt.options['display'] = 1
    # opt.options['bardisplay'] = 1
    # opt.options['mipdisplay'] = 2
    opt.options['primalopt'] = ""   # this is how you specify single-word arguments
    opt.options['advance'] = 2
    opt.options['threads'] = 1

    start = time.time()
    results = opt.solve(instance, keepfiles=False, tee=True, 
        symbolic_solver_labels=True, suffixes=['urc', 'lrc', 'rc', 'dual'])
    print "Total time in solver: {t}s".format(t=time.time()-start)

    instance.solutions.load_from(results)

    if results.solver.termination_condition == TerminationCondition.infeasible:
        print "Model was infeasible; Irreducible Infeasible Set (IIS) returned by solver:"
        print "\n".join(c.cname() for c in instance.iis)
        raise RuntimeError("Infeasible model")

    print "\n\n======================================================="
    print "Solved model"
    print "======================================================="
    print "Total cost: ${v:,.0f}".format(v=value(instance.Minimize_System_Cost))
        
###############
    
if __name__ == '__main__':
    # called directly from command line; save data and exit
    load_inputs()
    save_dat_files()
