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

import numpy as np
import random

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

 p       = np.array(p)      # convert to numpy arrays
 baseLoad = np.array(baseLoad)
 pstar   = p/p[0]           #  calculate relative prices from price vector

 L = len(p)
 theta1 = dict( alpha = np.repeat(1.0/L, L), sigma=sigma, M=1.0 )
 theta2 = dict( alpha = np.repeat(1.0/L, L), sigma=gamma, M=1.0 )
 n   = ( alpha*ces(pstar, theta1)  +  (1-alpha)*ces(pstar, theta2) )
 s   = n / sum(n)
 ds  = L*(s - 1.0/L)
 x1  = (1.0+ds)*baseLoad # reallocated totals, without aggregate response
 P   = np.sum(s*p)        # aggregate price
 A   = np.sum(baseLoad) / ( basePrice**theta )  # calibrate A to baseLoad and basePrice
 X   = A*P**theta       # aggregate quantity
 return( x1 * X/np.sum(x1) )   # adjust hourly totals to aggregate response


# Find consumers' willingness to pay

N = 100000
draws = np.zeros((N, 24))
#print "filling in draws."
for i in range(24):
  draws[:,i] = np.random.uniform(size=N)
# this could also just be draws = np.random.uniform(size=(N,24))

def wtp( p, Theta, baseLoad, basePrice, maxPrice=1000):
 p       = np.array(p)      # convert to numpy arrays
 baseLoad = np.array(baseLoad)

 pmat = p + draws*(maxPrice-p)
 for i in range(24):
   pmat[:,i] = p[i] + (maxPrice-p[i])*draws[:,i]
 slices = np.copy(draws)
 for i in range(N):
   slices[i,:] = double_ces(pmat[i,:], Theta, baseLoad, basePrice)
 
 # note: python uses 0 to count down, 1 to count across; R uses 2 and 1 respectively.
 cs = np.mean(slices, 0)*(maxPrice-p)
 paid = p*double_ces(p, Theta, baseLoad, basePrice)
 return( np.sum(cs) + np.sum(paid) )

def example():
    # example
    p1 = np.repeat(30, 24)
    p2 = np.random.normal(loc=30, scale=5, size=24)

    Theta = dict(theta=-0.075, alpha=0.2, sigma=50, gamma=0.01)
    
    loads = range(600, 950+1, 50) + [1000] * 5 + range(1100, 800-1, -100) + [750] +  [700] * 3 + [650, 650, 600]

    q1 = double_ces(p1, Theta, loads, 30)  # should return baseline loads
    q2 = double_ces(p2, Theta, loads, 30)  # example with random prices
    print "base price:", q1
    print "random prices:", q2

    w1 = wtp(p1, Theta, loads, 30) 
    w2 = wtp(p2, Theta, loads, 30)  # change in welfare from p1 to p2
    print "wtp at base price:", w1
    print "wtp at random price:", w2
    print "increase (decrease):", w2-w1