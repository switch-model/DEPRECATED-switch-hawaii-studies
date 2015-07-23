import numpy as np

def bid(prices, baseLoad, basePrice):
    """Accept a vector of current prices, base load level and base (flat) price.
    Return a tuple showing hourly load levels and willingness to pay for those loads
    (relative to the loads achieved at the basePrice). (note: basePrice will not generally result 
    in baseLoad, but the resulting load vector will have the same total quantity and WTP as the baseLoad.)
    This version assumes that 70% of load is price elastic with constant elasticity of 1.5%,
    and no substitution between hours, and 30% of load is inelastic in total volume, but schedules
    itself to the cheapest hour."""

    elasticity = 0.015
    shiftable_share = 0.3

    p = np.array(prices, float)
    bl = np.array(baseLoad, float)
    bp = float(basePrice)

    min_h = np.argmin(p)
    shiftable_load = np.zeros(len(p))
    shiftable_load[min_h] = shiftable_share * np.sum(bl)
    # the shiftable load is inelastic, so wtp is the same high number, regardless of when the load is served
    # so _relative_ wtp is always zero
    shiftable_load_wtp = 0  
    
    elastic_base_load = (1.0 - shiftable_share) * bl
    elastic_load =  elastic_base_load * (p/bp) ** (-elasticity)
    # _relative_ consumer surplus for the elastic load is the integral 
    # of the load (quantity) function from p to basePrice; note: the hours are independent
    # if p < bp, consumer surplus decreases as we move from p to bp, so cs_p - cs_p0 
    # (given by this integral) is positive
    elastic_load_cs_diff = np.sum((1 - (p/bp)**(1-elasticity)) * bp * elastic_base_load / (1-elasticity))
    # _relative_ amount actually paid for elastic load under current price vs base price
    base_elastic_load_paid = np.sum(bp * elastic_base_load)
    elastic_load_paid = np.sum(p * elastic_load)
    elastic_load_paid_diff = elastic_load_paid - base_elastic_load_paid
    
    return (shiftable_load+elastic_load, shiftable_load_wtp+elastic_load_cs_diff+elastic_load_paid_diff)
#    return (shiftable_load+elastic_base_load, shiftable_load_wtp)
