from pyomo.environ import *
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition
opt = SolverFactory("cplex", solver_io="nl")

mod = AbstractModel()

mod.S = Set(initialize=[1, 2])

mod.X = Var(mod.S, within=NonNegativeReals)

mod.Limit = Constraint(mod.S, rule=lambda m, s: m.X[s] <= 7)

mod.ProfitExpr = Expression(rule=lambda m: sum(m.X[s]*s for s in m.S))

mod.Profit = Objective(rule=lambda m: m.ProfitExpr, sense=maximize)

mod.dual = Suffix(direction=Suffix.IMPORT)

instance = mod.create()

results = opt.solve(instance, keepfiles=False, tee=True, 
    symbolic_solver_labels=True, suffixes=['dual'])

if not instance.load(results):
    raise RuntimeError("Unable to load solver results. Problem may be infeasible.")

print "Dual values:"
print [instance.dual[instance.Limit[s]] for s in instance.S]
print "Profit: " + str(value(instance.Profit))

def expand():
    instance.S.add(max(instance.S)+1)
    instance.X.reconstruct()
    instance.Limit.reconstruct()
    instance.ProfitExpr.reconstruct()
    results = opt.solve(instance, keepfiles=False, tee=True, symbolic_solver_labels=True, suffixes=['dual'])
    if not instance.load(results):
        raise RuntimeError("Unable to load solver results. Problem may be infeasible.")
    print "Dual values:"
    print [instance.dual[instance.Limit[s]] for s in instance.S]
    print "Profit: " + str(value(instance.Profit))
