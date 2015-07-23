
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

ces <- function(p,Theta) { # Standard CES
  # Theta is a list:  Theta$alpha = vector share coefficient, sum to 1
  #                   Theta$sigma = elasticity of substitution ( 0 < sigma < 1 )
  #                   Theta$M     = scalar income
  # p is price vector
  # returns x,  vector of demands
  fact = Theta$M /sum( (Theta$alpha^Theta$sigma) * p^(1-Theta$sigma) )
  x    =  fact*( Theta$alpha/p )^Theta$sigma
  return( x )
}

####################################################
#   Main Double CES function.  
####################################################
double.ces <- function(p, Theta, baseLoad, basePrice){
  theta   = Theta$theta      #  overall demand elasticity--should be negative
  alpha   = Theta$alpha      #  over share of elastic demand
  sigma   = Theta$sigma      #  elastic elasticity of substitution
  gamma   = Theta$gamma      #  inelastic elasticity of substitution
  pstar   = p/p[1]           #  calculate relative prices from price vector

  L = length(p)
  theta1 = list( alpha = rep(1/L, L), sigma=sigma, M=1 )
  theta2 = list( alpha = rep(1/L, L), sigma=gamma, M=1 )
  n   = ( alpha*ces(pstar, theta1)  +  (1-alpha)*ces(pstar, theta2) )
  s   = n /sum(n)
  ds  = L*(s - 1/L)
  x1  = (1+ds)*baseLoad # reallocated totals, without aggregate response
  P   = sum(s*p)        # aggregate price
  A   = sum(baseLoad) / ( basePrice^theta )  # calibrate A to baseLoad and basePrice
  X   = A*P^theta       # aggregate quantity
  return( x1 * X/sum(x1) )   # adjust hourly totals to aggregate response
}

# Find consumers' surplus
cs = function(N, p, Theta, baseLoad, basePrice){
  slices = matrix(0, ncol=24, nrow=N)
  for(i in 1:N) slices[i,] = double.ces(p*N/i, Theta, baseLoad, basePrice)
  x = apply(slices, 2, mean)
  return( sum(x) )
}

# example
p1 = rep(30, 24)
p2 = rnorm(24, mean=30, sd=5)

Theta = list( theta = -0.075,
              alpha =  0.2,
              sigma =  50,
              gamma = 0.01
)
loads =  c( seq(600, 950, by=50), rep(1000, 5), 
            seq(1100,800,by=-100), 750, rep(700,3),
            650, 650, 600 )


double.ces(p1, Theta, loads, 30)  # should return baseline loads
double.ces(p2, Theta, loads, 30)  # example with random prices

cs(1000, p2, Theta, loads, 30) - cs(1000, p1, Theta, loads, 30)  # change in welfare from p1 to p2






