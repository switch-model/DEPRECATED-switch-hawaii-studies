import os, sys
path_to_core = os.path.abspath(os.path.join(os.path.dirname(__file__), 'switch-hawaii-core'))
sys.path.append(path_to_core)
from scenario_data import write_tab_file
import numpy as np

try:
    import openpyxl
except ImportError:
    print "This script requires the openpyxl module to access the data in Microsoft Excel files."
    print "Please execute 'sudo pip install openpyxl' or 'pip install openpyxl' (Windows)."
    raise

# get_scenario_data.py should already have been run, creating a folder "inputs/pha"
# with standard inputs
base_year = 2015
n_scenarios = 4
n_digits = 6 # len(str(n_scenarios-1))  # how many leading zeros to use for scenario names
data_dir = os.path.join("inputs", "pha")

with open(os.path.join(data_dir, "fuel_supply_curves.tab")) as f:
    standard_fuel_costs = [r.split("\t") for r in f.read().splitlines()]
# drop the "bulk" tier for the LNG market, and replace with 

headers = standard_fuel_costs.pop(0)
period_ind = headers.index("period")
periods = sorted(set(float(r[period_ind]) for r in standard_fuel_costs))


fuel_base_date = 2015+5.0/12    # 6/1/12

# fossil fuel base prices, $/mmbtu (oil includes delivery to Hawaii)
oil_base_price = 111.67/6.115  # from Ulupono spreadsheet, for lsfo-diesel blend delivered to HI
gas_base_price = 2.889   # from Ulupono spreadsheet, for Henry Hub gas

# properties of logistic distribution used for random price variations (from Ulupono spreadsheet)
# these use the version that is adjusted to 4.7%/year (nominal), which is 0.0038032/mo.
# (Ulupono's baseline change in oil prices is much higher, 0.011525/mo.)
# But there has also been 41% inflation between 2000 and 2016, which is 0.0018/mo. 
# so the actual average monthly change is 0.0020
oil_adj_mean, oil_adj_scale = 0.0020, 0.031785
gas_adj_mean, gas_adj_scale = 0.0020, 0.088589

# factors to calculate various fuel prices from base prices; each is a tuple of 
# (oil multiplier, gas multiplier, constant adder)
# factors come from "HECO fuel cost forecasts.xlsx" unless otherwise noted
price_factors = {}
price_factors["LSFO-Diesel-Blend", "base"] = (1.0, 0.0, 0.0)
price_factors["LSFO", "base"] = (13.35/13.90, 0.0, 0.0)
price_factors["Diesel", "base"] = (14.72/13.90, 0.0, 0.0)
price_factors["Biodiesel", "base"] = (14.72/13.90, 0.0, 9.217) # diesel price + delta
price_factors["LNG", "bulk"] = (0.0, 1.2, 6.0) # from Ulupono spreadsheet
price_factors["LNG", "container"] = (0.0, 1.0, 17.59)

# list of all months from the forecast start date till the start of the first period
months = np.arange(fuel_base_date, periods[-1]+1.0/12, 1.0/12)
# indices of the months that are closest to the start of each period.
# is there a cleaner way to do this?
period_starts = np.array([np.argmin(np.abs(months - p)) for p in periods])

# note: eventually this should generate bivariate or multivariate samples (monthly change 
# in oil and gas prices), with the correct rank correlation between oil and gas prices. 
# But Ulupono is using
# logistic marginal distributions for the oil and gas prices, and it's not clear how to map
# correlation as they measure it (from a presumably logistic distribution) to rank correlation.
# Options: (1) go back to their source data, and bootstrap from there, with the correct rank correlation
# (2) create a bunch of logistic distributions with various rank correlations (and variance ratios?),
# and calculate their sample correlations; use these to build a list of pairs showing this 
# relationship, then create a function that interpolates along the list to return a rank correlation
# for a specific sample correlation. (or can we just assume rank correlation = sample correlation 
# when the two marginal distributions are the same?)
# For now, it's probably good enough just to draw both with perfect rank correlation or some 
# arbitrary high correlation.

oil_rank_sample = np.random.uniform(low=0.0, high=1.0, size=(len(months), n_scenarios))
gas_rank_sample = oil_rank_sample   # perfect rank correlation for now

print "oil_rank_sample"
print oil_rank_sample

def multipliers(ranks, mean, scale):
    # Uses the specified series of rank samples to draw monthly percentage changes
    # from a logistic distribution with the specified mean and scale, truncated to fall
    # between -0.99 and +0.99.
    # Then converts these into a series of multipliers relative to the starting date.
    # (note: percentile p for a logistic distribution is given by mu + s * ln(p/(1-p)))
    return np.cumprod(
        1.0 + (mean + scale * np.log(ranks/(1-ranks))).clip(-0.99, 0.99),
        axis=0
    )

# define a random walk through the months
oil_multipliers = multipliers(oil_rank_sample, oil_adj_mean, oil_adj_scale)[period_starts, :]
gas_multipliers = multipliers(gas_rank_sample, gas_adj_mean, gas_adj_scale)[period_starts, :]

print "oil_multipliers"
print oil_multipliers
print "gas_multipliers"
print gas_multipliers

oil_prices = oil_base_price * oil_multipliers
gas_prices = gas_base_price * gas_multipliers

print "oil_prices"
print oil_prices
print "gas_prices"
print gas_prices

fuel_prices = {
    (f, t): om * oil_prices + gm * gas_prices + a 
        for (f, t), (om, gm, a) in price_factors.iteritems()
}

# write the data files for each scenario, using scenario-specific prices where available
for s in range(n_scenarios):
    fuel_data = []
    for row in standard_fuel_costs:
        # columns: 
        # regional_fuel_market, fuel, period, tier, unit_cost, max_avail_at_cost, fixed_cost
        r = list(row)   # copy the existing list before changing, or convert tuple to list
        if (r[1], r[3]) in fuel_prices:
            r[4] = fuel_prices[r[1], r[3]][periods.index(float(r[2])), s]
        fuel_data.append(r)
    write_tab_file(
        "fuel_supply_curves_{s}.tab".format(s=str(s).zfill(n_digits)), 
        headers, fuel_data,
        dict(inputs_dir=data_dir, inputs_subdir="")
    )
    
