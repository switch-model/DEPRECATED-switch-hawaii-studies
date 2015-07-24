import sys, os
path_to_core = os.path.abspath(os.path.join(os.path.dirname(__file__), 'switch-hawaii-core'))
sys.path.append(path_to_core)

import scenario_data

###########################
# Scenario Definition

# particular settings chosen for this case
# (these will be passed as arguments when the queries are run)
scenario_data.write_tables(
    load_scen_id = "med",        # "hist"=pseudo-historical, "med"="Moved by Passion"
    fuel_scen_id = 3,            # 1=low, 2=high, 3=reference
    time_sample = "rps_test",       # could be '2007', '2016test', 'rps_test' or 'main'
    load_zones = ('Oahu',),       # subset of load zones to model
    enable_must_run = 0,     # should the must_run flag be converted to set minimum commitment for existing plants?
    # TODO: integrate the connect length into switch financial calculations,
    # rather than assigning a cost per MW-km here.
    connect_cost_per_mw_km = 1000000,
    base_financial_year = 2015,
    interest_rate = 0.06,
    discount_rate = 0.03
)
