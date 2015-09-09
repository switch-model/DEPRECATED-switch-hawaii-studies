# NOTE: the code below is still slightly brittle -- if someone changes RFM_SUPPLY_TIERS
# and then calls RFM_ACTIVE_IN_PERIOD.reconstruct(), it won't imbibe the new data.
# It's probably better to write an automatic function generator, that can
# slice big datasets arbitrarily (maybe with lambdas or just column lists to identify the
# indices and tuples), using the build-dict/pop method.
# e.g., slice_set(m.BIG_SET, indices=(1, 2), values=lambda m, a, b, c: f(a, b, c)) 
# --> this returns a function that does the job later when needed.

# note: RFM_SUPPLY_TIERS is a small set, and it only gets filtered once for each period (~ 4 times),
# and it gets fully consumed eventually. So it wouldn't be too inefficient to just write
# the RFM_Fixed_Costs sum using a filter like (r, _p, st) in REGIONAL_FUEL_MARKET if _p==p.
# But the code below shows a way to quickly build an indexed set in one pass that allows 
# direct access to the slices needed for any list operation. Another option (in general)
# is to index over a close-fitting outer set (e.g., PROJ_WITH_FUEL x PERIOD_TPS[period]) 
# and then filter that for membership in the larger set (e.g., PROJ_DISPATCH_TIMEPOINTS)
# (you can also use the get() convenience function to supply default values for missing
# data)
rfm_by_period_dict = collections.defaultdict(list)
def rfm_by_period_dict_build_rule(m):
    for r, p, st in m.RFM_SUPPLY_TIERS:
        rfm_by_period_dict[p].append((r, st))   # note: could build other slices here too
m.RFM_ACTIVE_IN_PERIOD_build = BuildAction(rule=rfm_by_period_dict_build_rule)
m.RFM_ACTIVE_IN_PERIOD = Set(m.PERIODS, initialize=lambda m, p: rfm_by_period_dict[p])




    # NOTE: this (any expression that starts with a small group of projects and uses
    # "in mod.PROJ_DISPATCH_POINTS")
    # could be a little faster if we had a list of valid timepoints 
    # for each project (maybe called ACTIVE_TIMEPOINTS_FOR_PROJECT), analogous to
    # PROJECTS_ACTIVE_IN_TIMEPOINT. Then this could use a list comprehension like 
    # PROJ_FUEL_DISPATCH_POINTS, or even itertools.chain() to build the list directly
    # with no filter.

# we could build ACTIVE_TIMEPOINTS_FOR_PROJECT very neatly with something like this:



model=ConcreteModel()
model.B = Set(initialize=[2,3,4])
def M_init(model, z, i, j):
    print locals()
    if z > 5:
        return Set.End
    return i*j+z

model.M = Set(model.B,model.B, initialize=M_init)

S_dict = collections.defaultdict(list)
def S_init(model, i):
    if len(S_dict) == 0:
        for b in model.B:
            for j in range(4):
                S_dict[b].append(b+j)
    # note: popping elements out of the dictionary reduces memory requirements 
    # and ensures the dictionary is empty the next time the set is constructed (if ever)
    return S_dict.pop(i)

model.S = Set(model.B, initialize=S_init)



    # all timepoints when each project is active (indexed set)
    # note: this could be sped up by pre-creating indexed lists of build years for each project
    # or 

    def BUILDYEARS_FOR_PROJECT_init(m, proj):
        # make a quasi-static variable showing the active build years for each project
        # It's faster to build this once and then pull from it rather than 
        # filtering PROJECT_BUILDYEARS once for each project.
        if not hasattr(BUILDYEARS_FOR_PROJECT_init, 'buildyears'):
            BUILDYEARS_FOR_PROJECT_init.buildyears = defaultdict(list)
            for (p, y) in m.PROJECT_BUILDYEARS:
                BUILDYEARS_FOR_PROJECT_init.buildyears[p].append(y)
        
        active_periods = set(
            m.PROJECT_BUILDS_OPERATIONAL_PERIODS[proj, bld_yr]
            for (proj, bld_yr) in m.PROJECT_BUILDYEARS)
    mod.BUILDYEARS_FOR_PROJECT = Set(
        mod.PROJECTS, 
        initialize=lambda m, p:
        )

    @pre_calculate()
    def init_active_timepoints(m, proj):
        # make a quasi-static variable showing the active build years for each project
        if not hasattr(init_active_timepoints, 'buildyears_for_project'):
        
        active_periods = set(
            m.PROJECT_BUILDS_OPERATIONAL_PERIODS[proj, bld_yr]
            for (proj, bld_yr) in m.PROJECT_BUILDYEARS)
        
        
        dispatch_timepoints = set()
        for (proj, bld_yr) in m.PROJECT_BUILDYEARS:
            for period in m.PROJECT_BUILDS_OPERATIONAL_PERIODS[proj, bld_yr]:
                for t in m.PERIOD_TPS[period]:
                    dispatch_timepoints.add((proj, t))
        return dispatch_timepoints
    mod.PROJECT_ACTIVE_TIMEPOINTS = Set(
        mod.PROJECTS,
        within=mod.TIMEPOINTS,
        initialize=
        
        lambda m, proj: (
            t for (proj, bld_year)
                for period in m.PROJECT_BUILDS_OPERATIONAL_PERIODS[proj, bld_yr]:
                    for t in m.PERIOD_TPS[period]:
                        dispatch_timepoints.add((proj, t))
            
            t for (proj, bld_yr) in m.PROJECT_BUILDYEARS:
        ))


import collections
import itertools
import timeit

proj=range(1000)
by=range(5)
pby=[(p, y) for p in proj for y in by]

def filt(p):
    if not hasattr(filt, 'bys'):
        filt.bys = collections.defaultdict(list)
        for (p, y) in pby:
            filt.bys[p].append(y)
    return tuple(filt.bys[p])

def filt2(p):
    if not hasattr(filt, 'bys'):
        sf = lambda (p, y): p
        #filt2.bys = dict(itertools.groupby(sorted(pby, key=sf), sf))
        filt2.bys = {k: [v[1] for v in l] for (k, l) in itertools.groupby(sorted(pby, key=sf), sf)}
    return tuple(filt.bys[p])


by_for_p_direct = [(p, tuple(y for (_p, y) in pby if _p==p)) for p in proj]
by_for_p_pre_calc = [(p, filt(p)) for p in proj]
by_for_p_pre_calc2 = [(p, filt2(p)) for p in proj]
by_for_p_direct == by_for_p_pre_calc
by_for_p_direct == by_for_p_pre_calc2

timeit.timeit(stmt='by_for_p = [(p, tuple(y for (_p, y) in pby if _p==p)) for p in proj]', setup="from __main__ import proj, by, pby", number=10)

timeit.timeit(stmt='by_for_p = [(p, filt(p)) for p in proj]', setup="from __main__ import proj, by, pby, filt; delattr(filt, 'bys') if hasattr(filt, 'bys') else None", number=100)

timeit.timeit(stmt='by_for_p = [(p, filt2(p)) for p in proj]', setup="from __main__ import proj, by, pby, filt2; delattr(filt2, 'bys') if hasattr(filt2, 'bys') else None", number=100)


"from __main__ import foo"
