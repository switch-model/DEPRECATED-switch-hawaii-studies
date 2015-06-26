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

    # convert inputs to numpy arrays, to allow easy element-wise math
    p = np.array(p)
    baseLoad = np.array(baseLoad)
    basePrice = np.array(basePrice)

    pstar   = p/p[1]           #  calculate relative prices from price vector

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
    return( x1 * X/sum(x1) )   # adjust hourly totals to aggregate response


# Find consumers' surplus
def cs(N, p, Theta, baseLoad, basePrice):
    p = np.array(p)   # enable element-wise math
    slices = np.zeros((N, 24))
    for i in range(N):  # note: python arrays and ranges start at 0; R starts at 1, so we add 1 in the line below
        slices[i,:] = double_ces(p*N/(i+1), Theta, baseLoad, basePrice)
    # note: python uses 0 to count down, 1 to count across; R uses 2 and 1 respectively.
    x = np.mean(slices, 0) * p  # MF added p to convert quantity to value
    return( sum(x) )



def example():
    p1 = np.repeat(30, 24)
    p2 = np.random.normal(loc=30, scale=5, size=24)

    Theta = dict( theta = -0.075,
                  alpha =  0.2,
                  sigma =  50,
                  gamma = 0.01
    )
    loads = range(600, 950+1, 50) + [1000] * 5 + range(1100, 800-1, -100) + [750] +  [700] * 3 + [650, 650, 600]

    # should return baseline loads
    print "loads for p1: {vals}".format(vals=double_ces(p1, Theta, loads, 30))
    # example with random prices
    print "loads for p2: {vals}".format(vals=double_ces(p2, Theta, loads, 30))

    # change in welfare from p1 to p2
    print "change in welfare: {val}".format(
        val=cs(1000, p2, Theta, loads, 30) - cs(1000, p1, Theta, loads, 30)
    )
