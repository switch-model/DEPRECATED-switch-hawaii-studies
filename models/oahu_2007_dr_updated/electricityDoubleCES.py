import numpy as np

######################################################################
# A DOUBLE CES DEMAND FUNCTION FOR ELECTRICITY
######################################################################
#
#  This code includes three functions:
#    1.   ces(p, Theta):  standard CES demand system.
#                     p:  price vector
#                 Theta:  a list w/ $alpha: vector consumption shares, same length as p, sum to 1
#                                   $sigma: elasticity of substitution
#                                   $M:     income
#
#
#
#    2.   double.ces(p, Theta, baseLoad, basePrice):   A new demand system 
#           designed for modelling electricity systems with inter-hourly substitution. The
#           demand system combines an aggregate constant elasticity of demand for electricity
#           with between-hour subsitution modeled as the sum of two CES demand systems,
#           with a share alpha allocatd to the first and (1-alpha) allocated to the second.
#           baseLoad and basePrice are vectors of baseLoads and a constant price used to 
#           calibrate other parameters in the demand system.
#
#   3.   cs(N, p, Theta, baseLoad, basePrice): approximates the consumers' surplus using N partitions
######################################################################
######################################################################

def ces(p,Theta): # Standard CES
    # Theta is a list:  Theta$alpha = vector share coefficient, sum to 1
    #                   Theta$sigma = elasticity of substitution ( 0 < sigma < 1 )
    #                   Theta$M     = scalar income
    # p is price vector
    # returns x,  vector of demands
    fact = Theta["M"] /sum( (Theta["alpha"]**Theta["sigma"]) * p**(1-Theta["sigma"]) )
    x    =  fact*( Theta["alpha"]/p )**Theta["sigma"]
    return( x )


####################################################
#   Main Double CES function.  
####################################################
def double_ces(p, Theta, baseLoad, basePrice):
    theta   = Theta["theta"]      #  overall demand elasticity--should be negative
    alpha   = Theta["alpha"]      #  over share of elastic demand
    sigma   = Theta["sigma"]      #  elastic elasticity of substitution
    gamma   = Theta["gamma"]      #  inelastic elasticity of substitution

    # import pdb; pdb.set_trace()

    # convert inputs to numpy arrays, to allow easy element-wise math
    p = np.array(p)
    baseLoad = np.array(baseLoad)
    basePrice = np.array(basePrice)

    p_mean  = np.mean(p)
    if p_mean == 0:                 # MF divided by mean instead of p[0] to make it robust against $0 prices
        pstar = p
    else:
        pstar = p/p_mean           #  calculate relative prices from price vector
    # pstar = p/p[0]

    L = len(p)
    theta1 = dict( alpha = np.repeat(1.0/L, L), sigma=sigma, M=1 )
    theta2 = dict( alpha = np.repeat(1.0/L, L), sigma=gamma, M=1 )
    n   = ( alpha*ces(pstar, theta1)  +  (1-alpha)*ces(pstar, theta2) )
    s   = n /sum(n)
    ds  = L*(s - 1.0/L)
    x1  = (1+ds)*baseLoad # reallocated totals, without aggregate response
    P   = sum(s*p)        # aggregate price
    A   = sum(baseLoad) / ( basePrice**theta )  # calibrate A to baseLoad and basePrice
    X   = A*P**theta       # aggregate quantity

    demand = x1 * X/sum(x1)   # adjust hourly totals to aggregate response
    # print "prices: "
    # print p
    # print "demand: "
    # print demand
    return demand


# Find consumers' surplus
def cs(N, p, Theta, baseLoad, basePrice):
    p = np.array(p)   # enable element-wise math
    slices = np.zeros((N, 24))
    for i in range(N):  # note: python arrays and ranges start at 0; R starts at 1, so we add 1 in the line below
        slices[i,:] = double_ces(p*N/(i+1), Theta, baseLoad, basePrice)
    # note: python uses 0 to count down, 1 to count across; R uses 2 and 1 respectively.
    x = np.mean(slices, 0) * p  # MF added p to convert quantity to value
    return( sum(x) )

# This should work, but actually gives increasing surplus for increasing prices.
# I think that is because it probes larger price bands as prices increase,
# and demand doesn't drop off, so this brings in more apparent surplus.
# (This demand function doesn't drop off fast enough so it actually has 
# infinite consumer surplus.)
def cs_up1(N, p, Theta, baseLoad, basePrice):
    # calculate total welfare from power consumption at the given prices
    
    # note: this finds the integral of q(p*s) p ds from s=1 to s=infinity
    # by subsituting s=1/u and calculating the integral of 
    # q((1/u)*p)d(1/u) = q(p/u)p/u**2 du from u=0 to u=1 (using a midpoint sum)
    
    p = np.array(p)   # enable element-wise math
    slices = np.zeros((N, len(p)))

    for i in range(N):  # note: python arrays and ranges start at 0
        u = (float(i)+0.5) / N
        du = (1.0/N)
        slices[i,:] = (double_ces(p/u, Theta, baseLoad, basePrice) * p / u**2) * du
        
    # note: python uses 0 to count down, 1 to count across; R uses 2 and 1 respectively.
    x1 = np.sum(slices, 0)   # sum across all slices of the approximate integral
    # also include the amount paid for the quantity consumed at price p
    x2 = p * double_ces(p*(i+0.5)/N, Theta, baseLoad, basePrice)
    return( sum(x1) )

def willingness_to_pay(p, Theta, baseLoad, basePrice):
    # calculate willingness to pay for the electricity bundle that would be bought at price p
    # this is equal to (consumer surplus at price p) + p * (quantity bought at price p)

    # convert to numpy array to allow easier calculations
    p = np.array(p)

    # highest possible price for power, used as the upper limit for integration of surplus
    p_max = np.repeat(basePrice * 10000, len(p))

    # we want small price steps near p, and large steps near p_max (to get there reasonably quickly).
    # so we create a geometric series from a small number up to 1, and use it to mix p and p_max
    N = 500
    step = 0.05
    steps = np.array([0.0] + [(1.0+step)**(i) / ((1.0+step)**(N-1)) for i in range(N)])

    # prices to use for integration
    prices = np.array([(1.0-s)*p + s*p_max for s in steps])

    slices = np.zeros((len(steps), len(p)))

    for i in range(len(steps)):
        slices[i,:] = double_ces(prices[i], Theta, baseLoad, basePrice)

    # use a trapezoidal approximation to calculate total price * quantity within each slice
    surplus = np.zeros(len(p))
    for i in range(len(steps)-1):
        surplus += (prices[i+1]-prices[i]) * (slices[i]+slices[i+1]) / 2.0
    
    # also include the amount paid for the quantity consumed at price p
    direct = p * double_ces(p*(i+0.5)/N, Theta, baseLoad, basePrice)
    
    # print "price={p}, surplus={s}, direct={d}".format(p=np.mean(p), s=np.sum(surplus), d=np.sum(direct))
    
    return( sum(surplus+direct) )

def example():
    p1 = np.repeat(30, 24)
    p2 = np.random.normal(loc=30, scale=5, size=24)

    Theta = dict(theta=-0.075, alpha=0.2, sigma=50, gamma=0.01)
    
    loads = range(600, 950+1, 50) + [1000] * 5 + range(1100, 800-1, -100) + [750] +  [700] * 3 + [650, 650, 600]

    # should return baseline loads
    print "loads for p1: {vals}".format(vals=double_ces(p1, Theta, loads, 30))
    # example with random prices
    print "loads for p2: {vals}".format(vals=double_ces(p2, Theta, loads, 30))

    # change in welfare from p1 to p2
    print "change in welfare: {val}".format(
        val=cs(1000, p2, Theta, loads, 30) - cs(1000, p1, Theta, loads, 30)
    )
