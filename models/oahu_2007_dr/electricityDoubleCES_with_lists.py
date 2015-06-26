import random

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


#############################
# NOTE: THERE IS SOME KIND OF BUG IN THIS CODE
# IT DOES NOT PRODUCE THE SAME RESULTS AS THE NUMPY VERSION.
# THE NUMPY VERSION IS MORE LIKELY TO BE CORRECT, SINCE IT IS
# NEARLY IDENTICAL TO THE R VERSION.
############################


def ces(p,Theta):  # Standard CES
  # Theta is a list:  Theta$alpha = vector share coefficient, sum to 1
  #                   Theta$sigma = elasticity of substitution ( 0 < sigma < 1 )
  #                   Theta$M     = scalar income
  # p is price vector
  # returns x,  vector of demands
  T = range(len(p))
  fact = Theta["M"] / sum( (Theta["alpha"][t] ** Theta["sigma"]) * p[t] ** (1-Theta["sigma"]) for t in T)
  x    =  [fact * ( Theta["alpha"][t] / p[t] ) ** Theta["sigma"] for t in T]
  return x 


####################################################
#   Main Double CES function.  
####################################################
def double_ces(p, Theta, baseLoad, basePrice):
  theta   = Theta["theta"]      #  overall demand elasticity--should be negative
  alpha   = Theta["alpha"]      #  over share of elastic demand
  sigma   = Theta["sigma"]      #  elastic elasticity of substitution
  gamma   = Theta["gamma"]      #  inelastic elasticity of substitution

  L = len(p)
  T = range(len(p)) # time steps

  pstar   = [p[t]/p[0] for t in T] #  calculate relative prices from price vector

  theta1 = dict( alpha = [1.0/L] * L, sigma=sigma, M=1 )
  theta2 = dict( alpha = [1.0/L] * L, sigma=gamma, M=1 )
  ces1 = ces(pstar, theta1)
  ces2 = ces(pstar, theta2)
  n   = [alpha*ces1[t] +  (1-alpha)*ces2[t] for t in T]
  s   = [n[t] / sum(n) for t in T]
  ds  = [L*(s[t] - 1/L) for t in T]
  x1  = [(1+ds[t])*baseLoad[t] for t in T] # reallocated totals, without aggregate response
  P   = sum(s[t] * p[t] for t in T)        # aggregate price
  A   = sum(baseLoad) / ( basePrice**theta )  # calibrate A to baseLoad and basePrice
  X   = A*P**theta                             # aggregate quantity
  return [x1[t] * X/sum(x1) for t in T]   # adjust hourly totals to aggregate response


# Find consumers' surplus
def cs(N, p, Theta, baseLoad, basePrice):
    T = range(len(p))
    slices = [
        double_ces([p[t]*N/i for t in T], Theta, baseLoad, basePrice) 
        for i in range(1,N+1)
    ]
    # note: MF added p[t]* to this expression, because otherwise it just seems to give
    # the average quantity for prices from 0 up to p. Multiplying by p gives the value.
    x = [p[t] * sum(slices[t])/N for t in T]
    return sum(x)

def example():
    p1 = [30] * 24
    p2 = [random.gauss(mu=30, sigma=5) for x in range(24)]

    Theta = dict( theta = -0.075,
                  alpha =  0.2,
                  sigma =  50,
                  gamma = 0.01
    )
    loads =  range(600, 950+1, 50) + [1000] * 5 + range(1100, 800-1, -100) + [750] +  [700] * 3 + [650, 650, 600]

    # should return baseline loads
    print "loads for p1: {vals}".format(vals=double_ces(p1, Theta, loads, 30))
    # example with random prices
    print "loads for p2: {vals}".format(vals=double_ces(p2, Theta, loads, 30))

    # change in welfare from p1 to p2
    print "change in welfare: {val}".format(
        val=cs(1000, p2, Theta, loads, 30) - cs(1000, p1, Theta, loads, 30)
    )
        