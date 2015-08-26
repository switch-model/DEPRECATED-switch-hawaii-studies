import sys, os
path_to_core = os.path.abspath(os.path.join(os.path.dirname(__file__), 'switch-hawaii-core'))
sys.path.append(path_to_core)

import scenario_data

###########################
# Scenario Definition

# battery data from Dropbox/kauai/OPL/Storage/power_plan.xlsx
# and http://www.energystoragenews.com/NGK%20Insulators%20Sodium%20Sulfur%20Batteries%20for%20Large%20Scale%20Grid%20Energy%20Storage.html

# particular settings chosen for this case
# (these will be passed as arguments when the queries are run)
args = dict(
    time_sample = "rps",       # could be '2007', '2016test', 'rps_test_45', 'rps' or 'main'
    load_zones = ('Oahu',),       # subset of load zones to model
    load_scen_id = "flat",        # "hist"=pseudo-historical, "med"="Moved by Passion", "flat"=2015 levels
    fuel_scen_id = 3,            # 1=low, 2=high, 3=reference
    ev_scen_id = None,              # 1=low, 2=high, 3=reference (omitted or None=none)
    enable_must_run = 0,     # should the must_run flag be converted to set minimum commitment for existing plants?
    # TODO: integrate the connect length into switch financial calculations,
    # rather than assigning a cost per MW-km here.
    connect_cost_per_mw_km = 1000,
    base_financial_year = 2015,
    interest_rate = 0.06,
    discount_rate = 0.03,
    inflation_rate = 0.025,  # used to convert nominal costs in the tables to real costs
)

args.update(
    battery_capital_cost_per_mwh_capacity=363636.3636,
    battery_n_cycles=4500,
    battery_max_discharge=0.9,
    battery_min_discharge_time=6,
    battery_efficiency=0.75,
)

args.update(
    pumped_hydro_capital_cost_per_mw=2800*1000+35e6/150,
    pumped_hydro_project_life=50,
    pumped_hydro_fixed_om_percent=0.015,    # use the low-end O&M, because it always builds the big version
    pumped_hydro_efficiency=0.8,
    pumped_hydro_inflow_mw=10,
    pumped_hydro_max_capacity_mw=1000,
)

if "skip_cf" in sys.argv:
    print "Skipping variable capacity factors..."
    args["skip_cf"] = True

scenario_data.write_tables(**args)
