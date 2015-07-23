import random

# based on http://stackoverflow.com/questions/15419740/calling-custom-functions-from-python-using-rpy2
# and http://rpy.sourceforge.net/rpy2/doc-dev/html/robjects_rpackages.html#importing-arbitrary-r-code-as-a-package

import rpy2.robjects.packages.SignatureTranslatedAnonymousPackage as STAP

with open('electricityDoubleCES.R', 'r') as f:
    string = ''.join(f.readlines())

ces = STAP(string, "ces")

p1 = [30] * 24
p2 = [random.gauss(mu=30, sigma=5) for x in range(24)]

Theta = dict( theta = -0.075,
              alpha =  0.2,
              sigma =  50,
              gamma = 0.01
)
loads =  range(600, 950+1, 50) + [1000] * 5 + range(1100, 800-1, -100) + [750] +  [700] * 3 + [650, 650, 600]


print ces.double.ces(p1, Theta, loads, 30)  # should return baseline loads
print ces.double.ces(p2, Theta, loads, 30)  # example with random prices

print ces.cs(1000, p2, Theta, loads, 30) - cs(1000, p1, Theta, loads, 30)  # change in welfare from p1 to p2






