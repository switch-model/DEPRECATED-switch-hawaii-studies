#!/usr/bin/env python

import sys, os
from textwrap import dedent

path_to_core = os.path.abspath(os.path.join(os.path.dirname(__file__), 'switch-hawaii-core'))
sys.path.append(path_to_core)

import scenario_data, scenarios

###########################
# Scenario Definitions

# definitions of standard scenarios (may also specify inputs_subdir to read in alternative data)
# TODO: find a way to define the base scenario here, then apply the others as changes to it
# Maybe allow each to start with --inherit_scenario <parent>? (to one level) 
# (--scenario does this already)

scenario_list = [
    '--scenario_name 100_biofuel_0_dr --biofuel_limit 1.00 -n hydrogen -n demand_response_simple --ev_flat',
    '--scenario_name 5_biofuel_0_dr --biofuel_limit 0.05 -n hydrogen -n demand_response_simple --ev_flat',
    '--scenario_name 5_biofuel_hydrogen_0_dr --biofuel_limit 0.05 -n demand_response_simple --ev_flat',

    '--scenario_name 5_biofuel_hydrogen --biofuel_limit 0.05',
    '--scenario_name 100_biofuel --biofuel_limit 1.00 -n hydrogen',
    '--scenario_name 5_biofuel --biofuel_limit 0.05 -n hydrogen',
]

with open('scenarios_to_run.txt', 'w') as f:
    f.writelines(s + '\n' for s in scenario_list)

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
    ev_scen_id = 2,              # 1=low, 2=high, 3=reference (omitted or None=none)
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

# data for sodium sulfur batteries from Dropbox/kauai/OPL/Storage/power_plan.xlsx
# and http://www.energystoragenews.com/NGK%20Insulators%20Sodium%20Sulfur%20Batteries%20for%20Large%20Scale%20Grid%20Energy%20Storage.html
# This version was used for model runs before 2016-01-27
# args.update(
#     battery_capital_cost_per_mwh_capacity=363636.3636,
#     battery_n_cycles=4500,
#     battery_max_discharge=0.9,
#     battery_min_discharge_time=6,
#     battery_efficiency=0.75,
# )

# battery data for 7.2 MW sodium sulfide battery from Black & Veatch 2012, 
# "Cost and Performance Data for Power Generation Technologies"
# http://bv.com/docs/reports-studies/nrel-cost-report.pdf (for 2015 system)
# NOTE: this source includes forecasts for cost improvements in the future
# args.update(
#     battery_capital_cost_per_mwh_capacity=3890000/8.1
#     battery_n_cycles=5000,
#     battery_max_discharge=0.80,   # not specified; see notes under EPRI data below
#     battery_min_discharge_time=8.1,
#     battery_efficiency=0.75,
#     # they also include
#     # $59/MWh variable O&M
#     # $25200/MW-year fixed O&M
#     # and say "The O&M cost includes the cost of battery replacement every 5,000 hours."
#     # not sure whether this means 5,000 cycles or hours of use, but it seems to fit with cycles.
# )

# battery data for 50 MW/300 MWh system from EPRI, 2010, "Electric Energy Storage Technology Options: 
# A White Paper Primer on Applications, Costs, and Benefits",
# http://large.stanford.edu/courses/2012/ph240/doshay1/docs/EPRI.pdf
# This has been used as the preferred battery prices since 2016-01-27
inflate_2010 = (1.0+args["inflation_rate"])**(args["base_financial_year"]-2010)
args.update(
    battery_capital_cost_per_mwh_capacity=inflate_2010*3200.0*1000/6,
    battery_n_cycles=4500,
    battery_max_discharge=0.85,
    # DOD not specified;
    # https://en.wikipedia.org/wiki/Sodium-sulfur_battery says 'Lifetime of 2,500 cycles at 100% depth of discharge (DOD), or 4,500 cycles at 80% DOD';
    # brochure cited by wikipedia at http://web.archive.org/web/20060205153231/http://www.ulvac-uc.co.jp/prm/prm_arc/049pdf/ulvac049-02.pdf gives 4,500 cycles at 85% DOD.
    # this article says "Lifetime of 2,500 cycles (at 100% DOD - depth of discharge), or 4,500 cycles (at 80% DOD)":
    # http://www.rellpower.com/wp/wp-content/uploads/2015/07/Ioxus-The-Case-for-Sodium-Sulfur-Batters-and-Ultracapacitors.pdf
    # Bito (NGK Insulators), 2005, "Overview of the Sodium-Sulfur Battery for the
    # IEEE Stationary Battery Committee", http://dx.doi.org/10.1109/PES.2005.1489556 says
    # "Long calendar and cycle life - 15 years and 2500 for 100% depth-of-discharge (DOD)
    # or 4500 for 90% DOD or 6500 for 65% DOD, etc."
    battery_min_discharge_time=6,
    battery_efficiency=0.75,
)

# Data for Tesla PowerWall from https://www.teslamotors.com/powerwall
# assuming 10 years * 365 cycles/year = 3650 cycle life
# args.update(
#     battery_capital_cost_per_mwh_capacity=(3000.0+1000.0)*1000/7.0,
#     # ($3000 (batteries) + $1000 (inverter))/7 kWh
#     # inverter cost estimate from
#     # http://www.catalyticengineering.com/top-ten-facts-about-teslas-350kwh-powerwall-battery/
#     # similar to power conversion costs in http://bv.com/docs/reports-studies/nrel-cost-report.pdf
#     # much more than power conversion costs in
#     # http://energyenvironment.pnnl.gov/pdf/National_Assessment_Storage_PHASE_II_vol_2_final.pdf
#     battery_n_cycles=10*365,
#     battery_max_discharge=1.0,
#     # DOD not specified by tesla, probably 100% (i.e. 10 MWh module capped at 7 MWh) according to
#     # http://www.catalyticengineering.com/top-ten-facts-about-teslas-350kwh-powerwall-battery/
#     battery_min_discharge_time=7.0/3.3, # 7.0 kWh / 3.3 kW
#     battery_efficiency=0.87,
#     # AC efficiency not given by tesla, estimated by
#     # http://www.catalyticengineering.com/top-ten-facts-about-teslas-350kwh-powerwall-battery/
# )


# other sources of battery cost data:
# http://energyenvironment.pnnl.gov/pdf/National_Assessment_Storage_PHASE_II_vol_2_final.pdf
# (also has depth-of-discharge vs. cycle life curves for NaS and Li-ion batteries)
# PSIP appendix J (but doesn't look at multi-hour storage or give storage depth): http://files.hawaii.gov/puc/3_Dkt%202011-0206%202014-08-26%20HECO%20PSIP%20Report.pdf
# http://www.hawaiianelectric.com/heco/Clean-Energy/Issues-and-Challenges/Energy-Storage
# http://www.nrel.gov/docs/fy10osti/46719.pdf
# http://www.irena.org/documentdownloads/publications/irena_battery_storage_report_2015.pdf
# https://www.purdue.edu/discoverypark/energy/assets/pdfs/SUFG/publications/SUFG%20Energy%20Storage%20Report.pdf (refs 5 and 22 from EPRI)
# https://www.wecc.biz/Reliability/2014_TEPPC_Generation_CapCost_Report_E3.pdf
# http://www.nrel.gov/docs/fy11osti/48595.pdf
# also see some NaS specs at http://www.eei.org/about/meetings/meeting_documents/abe.pdf
# and https://books.google.com/books?id=hGHr2L6HtKwC&pg=PA101&lpg=PA101&dq=sodium-sulfur+battery+calendar+life&source=bl&ots=ro3kExJx7o&sig=pciJ4sWF8wMmnYMljJPc2xlb4Bc&hl=en&sa=X&ved=0ahUKEwja6JyAmIDKAhUP0mMKHfyTDyIQ6AEINjAD#v=onepage&q=sodium-sulfur%20battery%20calendar%20life&f=false



# electrolyzer data from centralized current electrolyzer scenario version 3.1 in 
# http://www.hydrogen.energy.gov/h2a_prod_studies.html -> 01D_Current_Central_Hydrogen_Production_from_PEM_Electrolysis_version_3.1.xlsm
# (cited by 46719.pdf)
# note: we neglect land costs because they are small and can be recovered later
# TODO: move electrolyzer refurbishment costs from fixed to variable

# liquifier and tank data from http://www.nrel.gov/docs/fy99osti/25106.pdf

# fuel cell data from http://www.nrel.gov/docs/fy10osti/46719.pdf

inflate_1995 = (1.0+args["inflation_rate"])**(args["base_financial_year"]-1995)
inflate_2007 = (1.0+args["inflation_rate"])**(args["base_financial_year"]-2007)
inflate_2008 = (1.0+args["inflation_rate"])**(args["base_financial_year"]-2008)
h2_lhv_mj_per_kg = 120.21   # from http://hydrogen.pnl.gov/tools/lower-and-higher-heating-values-fuels
h2_mwh_per_kg = h2_lhv_mj_per_kg / 3600     # (3600 MJ/MWh)
electrolyzer_kg_per_mwh = 1000.0/54.3    # (1000 kWh/1 MWh)(1kg/54.3 kWh)   # TMP_Usage cell
electrolyzer_mw = 50000.0 * (1.0/electrolyzer_kg_per_mwh) * (1.0/24.0)   # (kg/day) * (MWh/kg) * (day/h)    # design_cap cell

args.update(
    hydrogen_electrolyzer_capital_cost_per_mw=inflate_2007*144641663.0/electrolyzer_mw,        # depr_cap cell
    hydrogen_electrolyzer_fixed_cost_per_mw_year=inflate_2007*7134560.0/electrolyzer_mw,         # fixed cell
    hydrogen_electrolyzer_variable_cost_per_kg=0.0,       # they only count electricity as variable cost
    hydrogen_electrolyzer_kg_per_mwh=electrolyzer_kg_per_mwh,
    hydrogen_electrolyzer_life_years=40,                      # plant_life cell

    hydrogen_liquifier_capital_cost_per_kg_per_hour=inflate_1995*25600,       # 25106.pdf p. 18, for 1500 kg/h plant, approx. 100 MW
    hydrogen_liquifier_fixed_cost_per_kg_hour_year=0.0,   # unknown, assumed low
    hydrogen_liquifier_variable_cost_per_kg=0.0,      # 25106.pdf p. 23 counts tank, equipment and electricity, but those are covered elsewhere
    hydrogen_liquifier_mwh_per_kg=10.0/1000.0,        # middle of 8-12 range from 25106.pdf p. 23
    hydrogen_liquifier_life_years=30,             # unknown, assumed long

    liquid_hydrogen_tank_capital_cost_per_kg=inflate_1995*18,         # 25106.pdf p. 20, for 300000 kg vessel
    liquid_hydrogen_tank_life_years=40,                       # unknown, assumed long

    hydrogen_fuel_cell_capital_cost_per_mw=813000*inflate_2008,   # 46719.pdf
    hydrogen_fuel_cell_fixed_cost_per_mw_year=27000*inflate_2008,   # 46719.pdf
    hydrogen_fuel_cell_variable_cost_per_mwh=0.0, # not listed in 46719.pdf; we should estimate a wear-and-tear factor
    hydrogen_fuel_cell_mwh_per_kg=0.53*h2_mwh_per_kg,   # efficiency from 46719.pdf
    hydrogen_fuel_cell_life_years=15,   # 46719.pdf
)

args.update(
    pumped_hydro_headers=[
        'ph_project_id', 'ph_load_zone', 'ph_capital_cost_per_mw', 'ph_project_life', 'ph_fixed_om_percent',
        'ph_efficiency', 'ph_inflow_mw', 'ph_max_capacity_mw'],
    pumped_hydro_projects=[
        ['Lake_Wilson', 'Oahu', 2800*1000+35e6/150, 50, 0.015, 0.77, 10, 150],
    ]
)

args.update(
    rps_targets = {2015: 0.15, 2020: 0.30, 2030: 0.40, 2040: 0.70, 2045: 1.00}
)

# data definitions for alternative scenarios
alt_args = [
    dict(inputs_dir="inputs", time_sample="rps_mini"),
    dict(inputs_dir="inputs_tiny", time_sample="tiny"),
    dict(
        inputs_dir="inputs_tiny_tiny", time_sample="tiny",
        exclude_technologies=args["exclude_technologies"]+('CentralTrackingPV', 'Wind')
    ),
]

for a in alt_args:
    # clone the arguments dictionary and update it with settings from the alt_args entry, if any
    active_args = dict(args.items() + a.items())
    scenario_data.write_tables(**active_args)
    

