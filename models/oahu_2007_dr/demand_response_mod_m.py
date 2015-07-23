"""
# cancel out the basic system load and replace it with a convex combination of bids
"""

import os, pprint
from pyomo.environ import *
import switch_mod.utilities as utilities
import electricityDoubleCES as ces



def define_components(mod):
    """

    """
    ###################
    # Unserved load, with a penalty.
    # to ensure the model is always feasible, no matter what demand bids we get
    ##################
    
    # cost per MWh for unserved load (high)
    mod.dr_unserved_load_penalty_per_mwh = Param(initialize=10000)
    # amount of unserved load during each timepoint
    mod.DRUnservedLoad = Var(mod.LOAD_ZONES, mod.TIMEPOINTS, within=NonNegativeReals)
    # total cost for unserved load
    mod.DR_Unserved_Load_Penalty = Expression(mod.TIMEPOINTS, initialize=lambda m, tp:
        sum(m.DRUnservedLoad[lz, tp] * m.dr_unserved_load_penalty_per_mwh for lz in m.LOAD_ZONES)
    )
    # add the unserved load to the model's energy balance
    #mod.LZ_Energy_Balance_components.append('DRUnservedLoad')
    # add the unserved load penalty to the model's objective function
    mod.cost_components_tp.append('DR_Unserved_Load_Penalty')

    ###################
    # Price Responsive Demand bids
    ##################
    
    # list of all bids that have been received from the demand system
    mod.DR_BID_LIST = Set(initialize = [])

    # data for the individual bids; each load_zone gets one bid for each timeseries,
    # and each bid covers all the timepoints in that timeseries. So we just record 
    # the bid for each timepoint for each load_zone.
    mod.dr_bid = Param(mod.DR_BID_LIST, mod.LOAD_ZONES, mod.TIMEPOINTS, mutable=True)

    # the private benefit of serving each bid
    mod.dr_bid_benefit = Param(mod.DR_BID_LIST, mod.LOAD_ZONES, mod.TIMESERIES, mutable=True)

    # weights to assign to the bids for each timeseries when constructing an optimal demand profile
    mod.DRBidWeight = Var(mod.DR_BID_LIST, mod.LOAD_ZONES, mod.TIMESERIES, within=NonNegativeReals)
    
    # def DR_Convex_Bid_Weight_rule(m, lz, ts):
    #     if len(m.DR_BID_LIST) == 0:
    #         print "no items in mod.DR_BID_LIST, skipping DR_Convex_Bid_Weight constraint"
    #         return Constraint.Skip
    #     else:
    #         print "constructing DR_Convex_Bid_Weight constraint"
    #         return (sum(m.DRBidWeight[b, lz, ts] for b in m.DR_BID_LIST) == 1)
    # 
    # choose a convex combination of bids for each zone and timeseries
    mod.DR_Convex_Bid_Weight = Constraint(mod.LOAD_ZONES, mod.TIMESERIES, rule=lambda m, lz, ts: 
        Constraint.Skip if len(m.DR_BID_LIST) == 0 else (sum(m.DRBidWeight[b, lz, ts] for b in m.DR_BID_LIST) == 1)
    )
    
    # Optimal level of demand, calculated from available bids (negative, indicating consumption)
    mod.FlexibleDemand = Expression(mod.LOAD_ZONES, mod.TIMEPOINTS, 
        rule=lambda m, lz, tp:
            - sum(m.DRBidWeight[b, lz, m.tp_ts[tp]] * m.dr_bid[b, lz, tp] for b in m.DR_BID_LIST)
    )

    # # FlexibleDemand reported as an adjustment (negative equals more demand)
    # # We have to do it this way because there's no way to remove the lz_demand_mw from the model
    # # without changing the core code.
    # mod.DemandPriceResponse = Expression(mod.LOAD_ZONES, mod.TIMEPOINTS, 
    #     rule=lambda m, lz, tp: m.lz_demand_mw[lz, tp] - m.FlexibleDemand[lz, tp]
    # )
    
    # effect of the electricity consumption on welfare (i.e., willingness to pay for the current electricity supply)
    # reported as negative cost, i.e., positive benefit
    mod.DR_Welfare_Cost = Expression(mod.TIMEPOINTS, initialize=lambda m, tp:
        - sum(m.DRBidWeight[b, lz, m.tp_ts[tp]] * m.dr_bid_benefit[b, lz, m.tp_ts[tp]] 
                for b in m.DR_BID_LIST for lz in m.LOAD_ZONES)
    )

    # add the welfare costs to the model's objective function
    mod.cost_components_tp.append('DR_Welfare_Cost')

# global variable to store the baseline data
baseData = None
Theta = dict( theta = -0.075,
              alpha =  0.2,
              sigma =  50,
              gamma = 0.01
)
N = 1000    # number of steps to use in calculating consumer surplus
def update_demand(mod):
    """
    This should be called after solving the model, in order to calculate new bids
    to include in future runs. The first time through, it also uses the fixed demand
    and marginal costs to calibrate the demand system, and then replaces the fixed
    demand with the flexible demand system.
    """
    global baseData
    first_run = (baseData is None)

    if first_run:
        # first time through, calibrate the demand system and add it to the model
        # baseData consists of a list of tuples showing (load_zone, timeseries, baseLoad (list) and basePrice (list))
        # note: the constructor below assumes list comprehensions will preserve the order of the underlying list
        # (which is guaranteed according to http://stackoverflow.com/questions/1286167/is-the-order-of-results-coming-from-a-list-comprehension-guaranteed)
        
        # calculate the average-cost price for the current study period
        # TODO: calculate this from the duals (using appropriate weights)
        # TODO: add in something for the fixed costs
        # for now, we just use a flat price of $0.30/kWh
        #baseCosts = [mod.dual[mod.EnergyBalance[lz, tp]] for lz in mod.LOAD_ZONES for tp in mod.TIMEPOINTS]
        basePrice = 0.30  # average-cost price
        baseData = [(
            lz, 
            ts, 
            [mod.lz_demand_mw[lz, tp] for tp in mod.TS_TPS[ts]],
            [basePrice for tp in mod.TS_TPS[ts]]
        ) for lz in mod.LOAD_ZONES for ts in mod.TIMESERIES]
    else:
        print "mod.DRBidWeight (first day):"
        print [(b, lz, ts, value(mod.DRBidWeight[b, lz, ts])) 
            for b in mod.DR_BID_LIST
            for lz in mod.LOAD_ZONES
            for ts in [mod.TIMESERIES.first()]]
        print "DR_Convex_Bid_Weight:"
        mod.DR_Convex_Bid_Weight.pprint()

    # get new demand bids at the current marginal costs
    bids = []
    for i, (lz, ts, baseLoad, basePrice) in enumerate(baseData):
        # TODO: add in something for the fixed costs
        prices = [mod.dual[mod.Energy_Balance[lz, tp]]/mod.tp_weight[tp] for tp in mod.TS_TPS[ts]]
        if i < 2:
            print "prices (day {i}): {p}".format(i=i, p=prices)
            print "weights: {w}".format(w=[mod.tp_weight[tp] for tp in mod.TS_TPS[ts]])
        demand = ces.double_ces(prices, Theta, baseLoad, basePrice)
        welfare = ces.cs(N, prices, Theta, baseLoad, basePrice)
        bids.append((lz, ts, demand, welfare))

    print "adding bids to model; first day="
    pprint.pprint(bids[0])
    # add the new bids to the model
    add_bids(mod, bids)
    print "mod.dr_bid_benefit (first day):"
    print [(b, lz, ts, value(mod.dr_bid_benefit[b, lz, ts])) 
        for b in mod.DR_BID_LIST
        for lz in mod.LOAD_ZONES
        for ts in [mod.TIMESERIES.first()]]
    print "mod.dr_bid (first day):"
    print [(b, lz, ts, value(mod.dr_bid[b, lz, ts]))
        for b in mod.DR_BID_LIST
        for lz in mod.LOAD_ZONES 
        for ts in mod.TS_TPS[mod.TIMESERIES.first()]]
    
    if first_run:
        # add FlexibleDemand to the energy balance constraint and remove lz_demand_mw_as_consumption
        # note: it is easiest to do this after retrieving the bids because this
        # destroys the dual values which are needed for calculating the bids
        mod.LZ_Energy_Balance_components.remove('lz_demand_mw_as_consumption')
        mod.LZ_Energy_Balance_components.append('FlexibleDemand')
        mod.Energy_Balance.reconstruct()


                
def add_bids(mod, bids):
    """ 
    accept a list of bids written as tuples like
    (lz, ts, demand, welfare)
    where lz is the load zone, ts is the timeseries, 
    demand is a list of demand levels for the timepoints during that series, 
    and welfare is the private benefit from that bid.
    Then add that set of bids to the model
    """
    # create a bid ID and add it to the list of bids
    if len(mod.DR_BID_LIST) == 0:
        b = 1
    else:
        b = max(mod.DR_BID_LIST) + 1
    mod.DR_BID_LIST.add(b)
    # add the bids for each load zone and timepoint to the dr_bid list
    for (lz, ts, demand, welfare) in bids:
        # record the welfare benefit
        mod.dr_bid_benefit[b, lz, ts] = welfare
        # record the level of demand for each timepoint
        timepoints = mod.TS_TPS[ts]
        for i, d in enumerate(demand):
            mod.dr_bid[b, lz, timepoints[i]] = d

    # reconstruct the components that depend on mod.DR_BID_LIST, mod.dr_bid_benefit and mod.dr_bid
    print "len(mod.DR_BID_LIST): {l}".format(l=len(mod.DR_BID_LIST))
    print "mod.DR_BID_LIST: {b}".format(b=[x for x in mod.DR_BID_LIST])
    mod.DRBidWeight.reconstruct()
    mod.DR_Convex_Bid_Weight.reconstruct()
    mod.FlexibleDemand.reconstruct()
    mod.DR_Welfare_Cost.reconstruct()
