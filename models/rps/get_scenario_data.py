#!/usr/bin/env python 

import sys, os
from textwrap import dedent

path_to_core = os.path.abspath(os.path.join(os.path.dirname(__file__), 'switch-hawaii-core'))
sys.path.append(path_to_core)

import scenario_data, scenarios

###########################
# Scenario Definitions

# definitions of standard scenarios (may also specify inputs_subdir to read in alternative data)
scenario_list = [
    '--scenario_name rps_base',
    '--scenario_name rps_low_oil_price --inputs_subdir low_oil_price',
    '--scenario_name rps_high_oil_price --inputs_subdir high_oil_price',
    '--scenario_name rps_lng_oil_peg --inputs_subdir lng_oil_peg',
    '--scenario_name rps_high_oil_and_lng_price --inputs_subdir high_lng_oil_peg',

    '--scenario_name rps_fast --inputs_subdir rps_fast --dr_shares 0.3', #' -y ev',
    '--scenario_name rps_2030 --inputs_subdir rps_2030 --dr_shares 0.3', #' -y ev',

    '--scenario_name x_base -n rps -n renewables -n demand_response -n pumped_hydro',
    '--scenario_name x_low_oil_price -n rps -n renewables -n demand_response -n pumped_hydro --inputs_subdir low_oil_price',
    '--scenario_name x_high_oil_price -n rps -n renewables -n demand_response -n pumped_hydro --inputs_subdir high_oil_price',
    '--scenario_name x_lng_oil_peg -n rps -n renewables -n demand_response -n pumped_hydro --inputs_subdir lng_oil_peg',
    '--scenario_name x_high_oil_and_lng_price -n rps -n renewables -n demand_response -n pumped_hydro --inputs_subdir high_lng_oil_peg',

    '--scenario_name rps_re_cost_trend --inputs_subdir re_cost_trend',
    '--scenario_name rps_no_wind -n wind',
    '--scenario_name rps_no_wind_no_central_pv -n wind -n central_pv',
    '--scenario_name rps_no_ph -n pumped_hydro',
    '--scenario_name rps_triple_ph --inputs_subdir triple_ph',
    '--scenario_name rps_fed_subsidies -y fed_subsidies',
    '--scenario_name rps_no_dr --dr_shares 0.0',
    '--scenario_name rps_more_dr --dr_shares 0.4',
    '--scenario_name rps_re_cost_trend_more_dr --dr_shares 0.4 --inputs_subdir re_cost_trend',
    # '--scenario_name rps_no_wind_ph2037_150 --ph_year=2037 --ph_mw=150 -n wind',
]

with open('scenarios_to_run.txt', 'w') as f:
    f.writelines(s + '\n' for s in scenario_list)

# battery data from Dropbox/kauai/OPL/Storage/power_plan.xlsx
# and http://www.energystoragenews.com/NGK%20Insulators%20Sodium%20Sulfur%20Batteries%20for%20Large%20Scale%20Grid%20Energy%20Storage.html

scenarios.parser.add_argument('--skip_cf', action='store_true')
scenarios.parser.add_argument('--time_sample')
cmd_line_args = scenarios.cmd_line_args()

# particular settings chosen for this case
# (these will be passed as arguments when the queries are run)
args = dict(
    inputs_dir = cmd_line_args.get('inputs_dir', 'inputs'),     # directory to store data in
    skip_cf = cmd_line_args['skip_cf'],     # skip writing capacity factors file if specified (for speed)
    
    time_sample = cmd_line_args.get('time_sample', "rps_mini"),       # could be 'tiny', 'rps', 'rps_mini' or possibly 
                                # '2007', '2016test', 'rps_test_45', or 'main'
    load_zones = ('Oahu',),       # subset of load zones to model
    load_scen_id = "med",        # "hist"=pseudo-historical, "med"="Moved by Passion", "flat"=2015 levels
    fuel_scen_id = 'EIA_ref',      # '1'=low, '2'=high, '3'=reference, 'EIA_ref'=EIA-derived reference level
    ev_scen_id = None,              # 1=low, 2=high, 3=reference (omitted or None=none)
    enable_must_run = 0,     # should the must_run flag be converted to 
                             # set minimum commitment for existing plants?
    exclude_technologies = ('CentralPV', 'DistPV_flat'),     # list of technologies to exclude
    # TODO: integrate the connect length into switch financial calculations,
    # rather than assigning a cost per MW-km here.
    connect_cost_per_mw_km = 1000,
    bulk_lng_fixed_cost = 1.75,     # fixed cost per MMBtu/year of capacity developed
    bulk_lng_limit = 43446735.1,    # limit on bulk LNG capacity (MMBtu/year)
    base_financial_year = 2015,
    interest_rate = 0.06,
    discount_rate = 0.03,
    inflation_rate = 0.025,  # used to convert nominal costs in the tables to real costs
)

# annual change in capital cost of new renewable projects
args.update(
    wind_capital_cost_escalator=0.0,
    pv_capital_cost_escalator=0.0
)

args.update(
    battery_capital_cost_per_mwh_capacity=363636.3636,
    battery_n_cycles=4500,
    battery_max_discharge=0.9,
    battery_min_discharge_time=6,
    battery_efficiency=0.75,
)

args.update(
    # pumped_hydro_headers=[
    #     'ph_project_id', 'ph_load_zone', 'ph_capital_cost_per_mw', 'ph_project_life', 'ph_fixed_om_percent',
    #     'ph_efficiency', 'ph_inflow_mw', 'ph_max_capacity_mw']
    # pumped_hydro_projects=[
    #     ['Lake Wilson', 'Oahu', 2800*1000+35e6/150, 50, 0.015, 0.77, 10, 150],
    # ]
    pumped_hydro_project_id='Lake Wilson',
    pumped_hydro_capital_cost_per_mw=2800*1000+35e6/150,
    pumped_hydro_project_life=50,
    pumped_hydro_fixed_om_percent=0.015,    # use the low-end O&M, because it always builds the big version
    pumped_hydro_efficiency=0.77,
    pumped_hydro_inflow_mw=10,
    pumped_hydro_max_capacity_mw=150,
    pumped_hydro_max_build_count=1
)

args.update(
    rps_targets = {2015: 0.15, 2020: 0.30, 2030: 0.40, 2040: 0.70, 2045: 1.00}
)

# data definitions for alternative scenarios
alt_args = [
    # dict(),         # base scenario
    # dict(inputs_subdir='high_oil_price', fuel_scen_id='EIA_high'),
    # dict(inputs_subdir='low_oil_price', fuel_scen_id='EIA_low'),
    # dict(inputs_subdir='lng_oil_peg', fuel_scen_id='EIA_lng_oil_peg'),
    # dict(inputs_subdir='high_lng_oil_peg', fuel_scen_id='EIA_high_lng_oil_peg'),
    # dict(inputs_subdir='re_cost_trend',
    #     wind_capital_cost_escalator=0.011,
    #     pv_capital_cost_escalator=-0.064),
    # dict(inputs_subdir='triple_ph',
    #     pumped_hydro_max_build_count=3,
    #     pumped_hydro_capital_cost_per_mw=1.25*args['pumped_hydro_capital_cost_per_mw']),
    # dict(inputs_subdir='efficient_ph',
    #     pumped_hydro_efficiency=0.8),
    # dict(inputs_subdir='rps_fast',
    #     # wind_capital_cost_escalator=0.011,
    #     # pv_capital_cost_escalator=-0.064,
    #     rps_targets = {2020: 0.4, 2025: 0.6, 2030: 0.8, 2035: 1.0},
    #     time_sample = "rps_fast_mini",
    #     ev_scen_id = 2, # high adoption (not used for now)
    #     fuel_scen_id = 'EIA_ref'  # 'EIA_ref_no_biofuel' eliminates all biofuel, but rps.py can restrict it more precisely
    # ),
    dict(inputs_subdir='rps_2030',
        # wind_capital_cost_escalator=0.011,
        # pv_capital_cost_escalator=-0.064,
        rps_targets = {2020: 0.4, 2025: 0.7, 2030: 1.0, 2035: 1.0},
        time_sample = "rps_fast_mini",
        ev_scen_id = 2, # high adoption (not used for now)
        fuel_scen_id = 'EIA_ref',  # 'EIA_ref_no_biofuel' eliminates all biofuel, but rps.py can restrict it more precisely
        # pumped_hydro_projects=[
        #     args["pumped_hydro_projects"][0],   # standard Lake Wilson project
        #     ['Project 2 (1.2x)', 'Oahu', 1.2*2800*1000+35e6/150, 50, 0.015, 0.77, 0, 100],
        #     ['Project 3 (1.3x)', 'Oahu', 1.3*2800*1000+35e6/150, 50, 0.015, 0.77, 0, 100],
        # ]
    ),
]

# annual change in capital cost of new renewable projects:
# solar cost projections: decline by 6.4%/year (based on residential PV systems from 1998 to 2014 in Fig. 7 of "Tracking the Sun VIII: The Installed Price of Residential and Non-Residential Photovoltaic Systems in the United States," https://emp.lbl.gov/reports (declines have been faster over more recent time period, and faster for non-residential systems).
# wind cost projections:
# increase by 1.1%/year (based on 1998-2014 in  2014 Wind Technologies Market Report, https://emp.lbl.gov/reports)



for a in alt_args:
    # clone the arguments dictionary and update it with settings from the alt_args entry, if any
    active_args = dict(args.items() + a.items())
    scenario_data.write_tables(**active_args)
    

