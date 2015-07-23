#!/usr/local/bin/python

import sys, os, time, traceback
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../switch')))

from pyomo.environ import *
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition

import switch_mod.utilities as utilities
from switch_mod.utilities import define_AbstractModel

import util
import demand_response

opt = SolverFactory("cplex", solver_io="nl")
# tell cplex to find an irreducible infeasible set (and report it)
#opt.options['iisfind'] = 1

# relax the integrality constraints, to allow commitment constraints to match up with 
# number of units available
opt.options['mipgap'] = 0.001

def iterate():
    global switch_model, switch_instance, results
    # NOTE: some evil magic in demand_response 
    # turns on bid adjusting behavior if "adj_bad_bids" is in the tag
    # or bid dropping behavior if "drop_bad_bids" is in the tag
    tag = 'accel_rps_fixed_ce_25'
    for i in range(25):
        # solve the model repeatedly, iterating with a new demand function
        solve_once()

        # if i <= 24 or i % 5 == 0:
        #     # save time by only writing results every 5 iterations
        #     write_results(tag=tag+'_'+str(i))
        write_results(tag=tag+'_'+str(i))
        
        #import pdb; pdb.set_trace()
        
        print "attaching new demand bid to model"
        demand_response.update_demand(switch_instance, tag)
        switch_instance.preprocess()

def write_results(tag=None):
    if tag is not None:
        t = "_"+str(tag)
    else:
        t = ""
    # write out results
    util.write_table(switch_instance, switch_instance.TIMEPOINTS,
        output_file=os.path.join("outputs", "dispatch{t}.txt".format(t=t)), 
        headings=("timepoint_label",)+tuple(switch_instance.PROJECTS),
        values=lambda m, t: (m.tp_timestamp[t],) + tuple(
            m.DispatchProj_AllTimePoints[p, t] 
            for p in m.PROJECTS
        )
    )
    util.write_table(switch_instance, switch_instance.TIMEPOINTS, 
        output_file=os.path.join("outputs", "load_balance{t}.txt".format(t=t)), 
        headings=
            ("timepoint_label",)
            +tuple(switch_instance.LZ_Energy_Components_Produce)
            +tuple(switch_instance.LZ_Energy_Components_Consume)
            +("marginal_cost",),
        values=lambda m, t: 
            (m.tp_timestamp[t],) 
            +tuple(sum(getattr(m, component)[lz, t] for lz in m.LOAD_ZONES)
                    for component in m.LZ_Energy_Components_Produce)
            +tuple(sum(getattr(m, component)[lz, t] for lz in m.LOAD_ZONES)
                    for component in m.LZ_Energy_Components_Consume)
            +(sum(m.dual[m.Energy_Balance[lz, t]]/m.bring_timepoint_costs_to_base_year[t] for lz in m.LOAD_ZONES)
                /len(m.LOAD_ZONES),)
    )    
    
    # note: the queries below could be sped up slightly by defining an indexed set 
    # of projects that use each particular energy source
    util.write_table(
        switch_instance, switch_instance.LOAD_ZONES, switch_instance.TIMEPOINTS, 
        output_file=os.path.join("outputs", "energy_sources{t}.txt".format(t=t)), 
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
    util.write_table(switch_instance, switch_instance.LOAD_ZONES, switch_instance.TIMEPOINTS, 
        output_file=os.path.join("outputs", "marginal_cost{t}.txt".format(t=t)), 
        headings=("timepoint_label", "load_zone", "marginal_cost"),
        values=lambda m, lz, tp: 
            (m.tp_timestamp[tp], lz, m.dual[m.Energy_Balance[lz, tp]]/m.bring_timepoint_costs_to_base_year[tp])
    )
    # import pprint
    # b=[(pr, pe, value(m.BuildProj[pr, pe]), m.proj_gen_tech[pr], m.proj_overnight_cost[pr, pe]) for (pr, pe) in m.BuildProj if value(m.BuildProj[pr, pe]) > 0]
    # bt=set(x[3] for x in b) # technologies
    # pprint([(t, sum(x[2] for x in b if x[3]==t), sum(x[4] for x in b if x[3]==t)/sum(1.0 for x in b if x[3]==t)) for t in bt])

    
def solve_once():
    global switch_model, switch_instance, results

    print "solving model..."
    start = time.time()
    results = opt.solve(switch_instance, keepfiles=False, tee=True, 
        symbolic_solver_labels=True, suffixes=['dual'])
    print "Total time in solver: {t}s".format(t=time.time()-start)

    # results.write()
    switch_instance.solutions.load_from(results)
    # if not: raise RuntimeError("Unable to load solver results. Problem may be infeasible.")

    if results.solver.termination_condition == TerminationCondition.infeasible:
        print "Model was infeasible; Irreducible Infeasible Set (IIS) returned by solver:"
        #print "\n".join(c.cname() for c in switch_instance.iis)
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
    print "marginal costs (first day):"
    print [switch_instance.dual[switch_instance.Energy_Balance[lz, tp]] \
                /switch_instance.bring_timepoint_costs_to_base_year[tp] 
            for lz in switch_instance.LOAD_ZONES
            for tp in switch_instance.TS_TPS[switch_instance.TIMESERIES[1]]]
    print "marginal costs (second day):"
    print [switch_instance.dual[switch_instance.Energy_Balance[lz, tp]] \
                /switch_instance.bring_timepoint_costs_to_base_year[tp] 
            for lz in switch_instance.LOAD_ZONES
            for tp in switch_instance.TS_TPS[switch_instance.TIMESERIES[2]]]
        
def patch_switch(switch_model):
    """Make various changes to the model to facilitate reporting and avoid unwanted behavior"""
    
    # def get_proj_dispatch_val(component, p, t, default=0.0):
    #     # return the value of a dispatch-related component for project p at timepoint t.
    #     # use the default value if the timepoint is invalid for this project.
    #     # note: this is slow, but not as slow as filtering the whole when doing sums, like this:
    #     # [sum(
    #     #     m.DispatchProj[p, t]
    #     #     for p, t_ in m.PROJ_DISPATCH_POINTS
    #     #     if t_ == t and p in m.FUEL_BASED_PROJECTS and m.proj_fuel[p] == f
    #     # ) for f in m.FUELS for t in m.TIMEPOINTS]
    #     return component[p, t] if (p, t) in component.index_set() else default
    
    # define parallel dispatch-related components with values for all timepoints. 
    # (This requires more memory than using a function, but may be faster for repeated 
    # evaluation; e.g., it only checks the index set once, at initialization time, and 
    # it may allow loops to run in C instead of Python code.)
    switch_model.DispatchProj_AllTimePoints = Expression(
        switch_model.PROJECTS, switch_model.TIMEPOINTS, 
        rule=lambda m, p, t:
            m.DispatchProj[p, t] if (p, t) in m.PROJ_DISPATCH_POINTS
                else 0.0
    )
    switch_model.DispatchUpperLimit_AllTimePoints = Expression(
        switch_model.PROJECTS, switch_model.TIMEPOINTS, 
        rule=lambda m, p, t:
            m.DispatchUpperLimit[p, t] if (p, t) in m.PROJ_DISPATCH_POINTS
                else 0.0
    )

    # create lists of projects by energy source
    switch_model.PROJECTS_BY_FUEL = Set(switch_model.FUELS, initialize=lambda m, f:
        # we sort this to help with display, but that may not actually have any effect
        sorted([p for p in m.FUEL_BASED_PROJECTS if m.proj_fuel[p] == f])
    )
    switch_model.PROJECTS_BY_NON_FUEL_ENERGY_SOURCE = Set(switch_model.NON_FUEL_ENERGY_SOURCES, initialize=lambda m, s:
        # we sort this to help with display, but that may not actually have any effect
        sorted([p for p in m.NON_FUEL_BASED_PROJECTS if m.proj_non_fuel_energy_source[p] == s])
    )

    # constrain DumpPower to zero, so we can track curtailment better
    switch_model.No_Dump_Power = Constraint(switch_model.LOAD_ZONES, switch_model.TIMEPOINTS,
        rule=lambda m, z, t: m.DumpPower[z, t] == 0.0
    )


####################
# Main execution code

print "loading model..."

# tell pyomo to make all parameters mutable by default
# (I only need to change lz_demand_mw, but this is currently the only way to make
# any parameter mutable without changing the core code.)
# NOTE: this causes errors like "TypeError: unhashable type: '_ParamData'" 
# when any parameters are used as indexes into a set (e.g., m.ts_scale_to_period[ts])
# This may be a pyomo bug, but it's hard to work around in the short term.
# Param.DefaultMutable = True

switch_model = define_AbstractModel(
    'switch_mod', 'fuel_cost', 'project.no_commit', #'project.unitcommit', 'project.unitcommit.discrete', 
    'demand_response', 'rps'
)
#switch_model.iis = Suffix(direction=Suffix.IMPORT)
switch_model.dual = Suffix(direction=Suffix.IMPORT)

patch_switch(switch_model)

switch_instance = switch_model.load_inputs(inputs_dir="inputs")

results = None

###############
    
if __name__ == '__main__':
    # catch errors so the user can continue with a solved model
    try:
        iterate()
    except Exception, e:
        traceback.print_exc()
        print "ERROR:", e
    