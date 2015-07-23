"""
# cancel out the basic system load and replace it with a convex combination of bids
"""

import os
from pprint import pprint
from pyomo.environ import *
import switch_mod.utilities as utilities
import doubleCES2 as ces
import constant_elasticity as ce
import util

def define_components(m):
    """

    """
    ###################
    # Unserved load, with a penalty.
    # to ensure the model is always feasible, no matter what demand bids we get
    ##################
    
    # cost per MWh for unserved load (high)
    m.dr_unserved_load_penalty_per_mwh = Param(initialize=10000)
    # amount of unserved load during each timepoint
    m.DRUnservedLoad = Var(m.LOAD_ZONES, m.TIMEPOINTS, within=NonNegativeReals)
    # total cost for unserved load
    m.DR_Unserved_Load_Penalty = Expression(m.TIMEPOINTS, rule=lambda m, tp:
        sum(m.DRUnservedLoad[lz, tp] * m.dr_unserved_load_penalty_per_mwh for lz in m.LOAD_ZONES)
    )
    # add the unserved load to the model's energy balance
    m.LZ_Energy_Components_Produce.append('DRUnservedLoad')
    # add the unserved load penalty to the model's objective function
    m.cost_components_tp.append('DR_Unserved_Load_Penalty')

    ###################
    # Price Responsive Demand bids
    ##################
    
    # list of all bids that have been received from the demand system
    m.DR_BID_LIST = Set(initialize = [])
    # we need an explicit indexing set for everything that depends on DR_BID_LIST
    # so we can reconstruct it (and them) each time we add an element to DR_BID_LIST
    # (not needed, and actually doesn't work -- reconstruct() fails for sets)
    # m.DR_BIDS_LZ_TP = Set(initialize = lambda m: m.DR_BID_LIST * m.LOAD_ZONES * m.TIMEPOINTS)
    # m.DR_BIDS_LZ_TS = Set(initialize = lambda m: m.DR_BID_LIST * m.LOAD_ZONES * m.TIMESERIES)
    
    # data for the individual bids; each load_zone gets one bid for each timeseries,
    # and each bid covers all the timepoints in that timeseries. So we just record 
    # the bid for each timepoint for each load_zone.
    m.dr_bid = Param(m.DR_BID_LIST, m.LOAD_ZONES, m.TIMEPOINTS, mutable=True)

    # the private benefit of serving each bid
    m.dr_bid_benefit = Param(m.DR_BID_LIST, m.LOAD_ZONES, m.TIMESERIES, mutable=True)

    # weights to assign to the bids for each timeseries when constructing an optimal demand profile
    m.DRBidWeight = Var(m.DR_BID_LIST, m.LOAD_ZONES, m.TIMESERIES, within=NonNegativeReals)
    
    # def DR_Convex_Bid_Weight_rule(m, lz, ts):
    #     if len(m.DR_BID_LIST) == 0:
    #         print "no items in m.DR_BID_LIST, skipping DR_Convex_Bid_Weight constraint"
    #         return Constraint.Skip
    #     else:
    #         print "constructing DR_Convex_Bid_Weight constraint"
    #         return (sum(m.DRBidWeight[b, lz, ts] for b in m.DR_BID_LIST) == 1)
    # 
    # choose a convex combination of bids for each zone and timeseries
    m.DR_Convex_Bid_Weight = Constraint(m.LOAD_ZONES, m.TIMESERIES, rule=lambda m, lz, ts: 
        Constraint.Skip if len(m.DR_BID_LIST) == 0 else (sum(m.DRBidWeight[b, lz, ts] for b in m.DR_BID_LIST) == 1)
    )
    
    # Optimal level of demand, calculated from available bids (negative, indicating consumption)
    m.FlexibleDemand = Expression(m.LOAD_ZONES, m.TIMEPOINTS, 
        rule=lambda m, lz, tp:
            sum(m.DRBidWeight[b, lz, m.tp_ts[tp]] * m.dr_bid[b, lz, tp] for b in m.DR_BID_LIST)
    )

    # # FlexibleDemand reported as an adjustment (negative equals more demand)
    # # We have to do it this way because there's no way to remove the lz_demand_mw from the model
    # # without changing the core code.
    # m.DemandPriceResponse = Expression(m.LOAD_ZONES, m.TIMEPOINTS, 
    #     rule=lambda m, lz, tp: m.lz_demand_mw[lz, tp] - m.FlexibleDemand[lz, tp]
    # )
    
    # private benefit of the electricity consumption 
    # (i.e., willingness to pay for the current electricity supply)
    # reported as negative cost, i.e., positive benefit
    # also divide by 24 to convert from a daily cost to a cost per timepoint.
    m.DR_Welfare_Cost = Expression(m.TIMEPOINTS, rule=lambda m, tp:
        (-1.0) 
        * sum(m.DRBidWeight[b, lz, m.tp_ts[tp]] * m.dr_bid_benefit[b, lz, m.tp_ts[tp]] 
            for b in m.DR_BID_LIST for lz in m.LOAD_ZONES) 
        * m.tp_duration_hrs[tp] / 24.0
    )

    # add the private benefit to the model's objective function
    m.cost_components_tp.append('DR_Welfare_Cost')

# global variable to store the baseline data
baseData = None
Theta = dict( theta = -0.075,
              alpha =  0.2,
              sigma =  50,
#              sigma =  0.0, # no substitution
              gamma = 0.01
)
N = 1000    # number of steps to use in calculating consumer surplus
def update_demand(m, tag):
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
        # baseData consists of a list of tuples showing (load_zone, timeseries, baseLoad (list) and basePrice)
        # note: the constructor below assumes list comprehensions will preserve the order of the underlying list
        # (which is guaranteed according to http://stackoverflow.com/questions/1286167/is-the-order-of-results-coming-from-a-list-comprehension-guaranteed)
        
        # calculate the average-cost price for the current study period
        # TODO: find basePrice for each period that corresponds to the assumptions 
        # used in the base-case load forecast
        # TODO: add in something for the fixed costs, to make marginal cost commensurate with the basePrice
        # for now, we just use a flat price roughly equal to backstop generation.
        #baseCosts = [m.dual[m.EnergyBalance[lz, tp]] for lz in m.LOAD_ZONES for tp in m.TIMEPOINTS]
        basePrice = 110  # average-cost price ($/MWh)
        baseData = [(
            lz, 
            ts, 
            [m.lz_demand_mw[lz, tp] for tp in m.TS_TPS[ts]],
            basePrice
        ) for lz in m.LOAD_ZONES for ts in m.TIMESERIES]

        util.create_table(
            output_file=os.path.join("outputs", "bid_weights_{t}.txt".format(t=tag)), 
            headings=("iteration", "load_zone", "timeseries", "bid_num", "weight")
        )

    else:
        # print "m.DRBidWeight (first day):"
        # print [(b, lz, ts, value(m.DRBidWeight[b, lz, ts])) 
        #     for b in m.DR_BID_LIST
        #     for lz in m.LOAD_ZONES
        #     for ts in m.TIMESERIES]
        print "m.DRBidWeight:"
        pprint([(lz, ts, [(b, value(m.DRBidWeight[b, lz, ts])) for b in m.DR_BID_LIST])
            for lz in m.LOAD_ZONES
            for ts in m.TIMESERIES])
        #print "DR_Convex_Bid_Weight:"
        #m.DR_Convex_Bid_Weight.pprint()

        # store the current bid weights for future reference
        # This should be done before adding the new bid.
        util.append_table(m, m.LOAD_ZONES, m.TIMESERIES, m.DR_BID_LIST, 
            output_file=os.path.join("outputs", "bid_weights_{t}.txt".format(t=tag)), 
            values=lambda m, lz, ts, b: (len(m.DR_BID_LIST), lz, ts, b, m.DRBidWeight[b, lz, ts])
        )


    # get new demand bids at the current marginal costs
    bids = []
    for i, (lz, ts, baseLoad, basePrice) in enumerate(baseData):
        # TODO: add in something for the fixed costs
        prices = [m.dual[m.Energy_Balance[lz, tp]]/m.bring_timepoint_costs_to_base_year[tp] for tp in m.TS_TPS[ts]]
        # set a floor on prices to avoid division-by-zero in the CES functions
        prices = [max(0.0001, p) for p in prices]
        # if i < 2:
        #     print "prices (day {i}): {p}".format(i=i, p=prices)
        #     print "weights: {w}".format(w=[m.bring_timepoint_costs_to_base_year[tp] for tp in m.TS_TPS[ts]])
        if '_ce_' in tag:
            (demand, wtp) = ce.bid(prices, baseLoad, basePrice)
        else:
            demand = ces.double_ces(prices, Theta, baseLoad, basePrice)
            wtp = ces.wtp(prices, Theta, baseLoad, basePrice)
        bids.append((lz, ts, prices, demand, wtp))

        # if i < 2:
        #     import pdb; pdb.set_trace()

    print "adding bids to model; first day="
    pprint(bids[0])
    # add the new bids to the model
    add_bids(m, bids, tag)
    print "m.dr_bid_benefit (first day):"
    pprint([(b, lz, ts, value(m.dr_bid_benefit[b, lz, ts])) 
        for b in m.DR_BID_LIST
        for lz in m.LOAD_ZONES
        for ts in [m.TIMESERIES.first()]])
    
    # print "m.dr_bid (first day):"
    # print [(b, lz, ts, value(m.dr_bid[b, lz, ts]))
    #     for b in m.DR_BID_LIST
    #     for lz in m.LOAD_ZONES 
    #     for ts in m.TS_TPS[m.TIMESERIES.first()]]
    
    if first_run:
        # replace lz_demand_mw with FlexibleDemand in the energy balance constraint
        # note: it is easiest to do this after retrieving the bids because this
        # destroys the dual values which are needed for calculating the bids
        # note: the first two lines are simpler than the method I use, but my approach
        # preserves the ordering of the list, which is nice for reporting.
        # m.LZ_Energy_Components_Consume.remove('lz_demand_mw')
        # m.LZ_Energy_Components_Consume.append('FlexibleDemand')
        ecc = m.LZ_Energy_Components_Consume
        ecc[ecc.index('lz_demand_mw')] = 'FlexibleDemand'
        m.Energy_Balance.reconstruct()

def sum_product(vector1, vector2):
    return sum(v1*v2 for (v1, v2) in zip(vector1, vector2))

def add_bids(m, bids, tag):
    """ 
    accept a list of bids written as tuples like
    (lz, ts, prices, demand, wtp)
    where lz is the load zone, ts is the timeseries, 
    demand is a list of demand levels for the timepoints during that series, 
    and wtp is the private benefit from consuming the amount of power in that bid.
    Then add that set of bids to the model
    """
    # create a bid ID and add it to the list of bids
    if len(m.DR_BID_LIST) == 0:
        b = 1
    else:
        b = max(m.DR_BID_LIST) + 1

    # sometimes the demand side reports a strangely high willingness to pay for a particular bundle.
    # then, when prices change, it chooses other bundles, but reports a lower willingness to pay
    # for them than for the earlier bundle. This suggests that wtp for the earlier bundle is 
    # overstated. So here we go back and reduce wtp for some earlier bundles based on the fact that
    # they were not selected at the current prices (so they must actually have a lower wtp than the
    # current bundle). This has the effect of gradually forgetting older bids that aren't re-offered
    # as the model converges toward final prices.
    # for (lz, ts, prices, demand, wtp) in bids:
    #     cs_new = wtp - sum_product(prices, demand)
    #     for bid in m.DR_BID_LIST:
    #         cs_old = value(m.dr_bid_benefit[bid, lz, ts]) \
    #                     - sum_product(prices, [value(m.dr_bid[bid, lz, tp]) for tp in m.TS_TPS[ts]])
    #         if cs_old > cs_new:
    #             # the old bid is reported to have higher consumer surplus at the current prices
    #             # than the new bid.
    #             # this shouldn't happen, but it does.
    #             # reduce implied consumer surplus for the old bid so it is no more than the cs for the new bid
    #             # at the current prices.
    #             if 'drop_bad_bids' in tag:
    #                 print "dropping bid {b} from model because wtp is too high.".format(b=(bid, lz, ts))
    #                 m.dr_bid_benefit[bid, lz, ts] -= (cs_old - cs_new + 1e7)
    #             if 'adj_bad_bids' in tag:
    #                 print "reducing wtp for bid {b} by ${adj}".format(b=(bid, lz, ts), adj=cs_old-cs_new)
    #                 m.dr_bid_benefit[bid, lz, ts] -= (cs_old - cs_new)


    m.DR_BID_LIST.add(b)
    # m.DR_BIDS_LZ_TP.reconstruct()
    # m.DR_BIDS_LZ_TS.reconstruct()
    # add the bids for each load zone and timepoint to the dr_bid list
    for (lz, ts, prices, demand, wtp) in bids:
        # record the private benefit
        m.dr_bid_benefit[b, lz, ts] = wtp
        # record the level of demand for each timepoint
        timepoints = m.TS_TPS[ts]
        # print "ts: "+str(ts)
        # print "demand: " + str(demand)
        # print "timepoints: " + str([t for t in timepoints])
        for i, d in enumerate(demand):
            # print "i+1: "+str(i+1)
            # print "d: "+str(d)
            # print "timepoints[i+1]: "+str(timepoints[i+1])
            # note: demand is a python list or array, which uses 0-based indexing, but
            # timepoints is a pyomo set, which uses 1-based indexing, so we have to shift the index by 1.
            m.dr_bid[b, lz, timepoints[i+1]] = d

    print "len(m.DR_BID_LIST): {l}".format(l=len(m.DR_BID_LIST))
    print "m.DR_BID_LIST: {b}".format(b=[x for x in m.DR_BID_LIST])

    # store bid information for later reference
    # this has to be done after the model is updated and
    # before DRBidWeight is reconstructed (which destroys the duals)
    if b == 1:
        util.create_table(
            output_file=os.path.join("outputs", "bid_{t}.txt".format(t=tag)), 
            headings=("bid_num", "load_zone", "timepoint_label", "marginal_cost", "bid", "wtp")
        )
    util.append_table(m, m.LOAD_ZONES, m.TIMEPOINTS,
        output_file=os.path.join("outputs", "bid_{t}.txt".format(t=tag)), 
        values=lambda m, lz, tp: (
            b,
            lz,
            m.tp_timestamp[tp],
            m.dual[m.Energy_Balance[lz, tp]]/m.bring_timepoint_costs_to_base_year[tp],
            m.dr_bid[max(m.DR_BID_LIST), lz, tp],
            m.dr_bid_benefit[b, lz, m.tp_ts[tp]]
        )
    )

    # reconstruct the components that depend on m.DR_BID_LIST, m.dr_bid_benefit and m.dr_bid
    m.DRBidWeight.reconstruct()
    m.DR_Convex_Bid_Weight.reconstruct()
    m.FlexibleDemand.reconstruct()
    m.DR_Welfare_Cost.reconstruct()
    # it seems like we have to reconstruct the higher-level components that depend on these 
    # ones (even though these are Expressions), because otherwise they refer to objects that
    # used to be returned by the Expression but aren't any more (e.g., versions of DRBidWeight 
    # that no longer exist in the model).
    # (i.e., Energy_Balance refers to the items returned by FlexibleDemand instead of referring 
    # to FlexibleDemand itself)
    m.Energy_Balance.reconstruct()
    m.SystemCostPerPeriod.reconstruct()
    m.Minimize_System_Cost.reconstruct()    # may not be needed, since it seems to store the rule
                                            # rather than the result of the rule
