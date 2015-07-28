import os
from pyomo.environ import *
from switch_mod.financials import capital_recovery_factor as crf

def define_components(m):
    
    m.pumped_hydro_capital_cost = Param()
    m.pumped_hydro_project_life = Param()
    
    # annual O&M cost for pumped hydro project, percent of capital cost
    m.pumped_hydro_fixed_om_percent = Param()
    
    # total annual cost
    m.pumped_hydro_fixed_cost_per_mw_per_year = Param(initialize=lambda m:
        m.pumped_hydro_capital_cost * 
            (crf(m.interest_rate, m.pumped_hydro_project_life) + m.pumped_hydro_fixed_om_percent)
    )
    
    # round-trip efficiency of the pumped hydro facility
    m.pumped_hydro_efficiency = Param()
    
    # average energy available from water inflow each day
    # (system must balance energy net of this each day)
    m.pumped_hydro_inflow_mw = Param()
    
    # How much pumped hydro to build
    m.BuildPumpedHydroMW = Var(m.LOAD_ZONES, m.PERIODS, within=NonNegativeReals)
    m.Pumped_Hydro_Capacity_MW = Expression(m.LOAD_ZONES, m.PERIODS, rule=lambda m, z, p:
        sum(m.BuildPumpedHydroMW[z, m.PERIODS[i]] for i in range(1, m.PERIODS.ord(p)))
    )

    # How to run pumped hydro
    m.GeneratePumpedHydro = Var(m.LOAD_ZONES, m.TIMEPOINTS, within=NonNegativeReals)
    m.StorePumpedHydro = Var(m.LOAD_ZONES, m.TIMEPOINTS, within=NonNegativeReals)
    
    # calculate costs
    m.Pumped_Hydro_Fixed_Cost_Annual = Expression(m.PERIODS, rule=lambda m, p:
        sum(m.pumped_hydro_fixed_cost_per_mw_per_year * m.Pumped_Hydro_Capacity_MW[z, p] for z in m.LOAD_ZONES)
    )
    m.cost_components_annual.append('Pumped_Hydro_Fixed_Cost_Annual')
    
    # add the pumped hydro to the model's energy balance
    m.LZ_Energy_Components_Produce.append('GeneratePumpedHydro')
    m.LZ_Energy_Components_Consume.append('StorePumpedHydro')
    
    # limits on pumping and generation
    m.Pumped_Hydro_Max_Generate_Rate = Constraint(m.LOAD_ZONES, m.TIMEPOINTS, rule=lambda m, z, t:
        m.GeneratePumpedHydro[z, t]
        <=
        m.Pumped_Hydro_Capacity_MW[z, m.tp_period[t]]
    )
    m.Pumped_Hydro_Max_Store_Rate = Constraint(m.LOAD_ZONES, m.TIMEPOINTS, rule=lambda m, z, t:
        m.StorePumpedHydro[z, t]
        <=
        m.Pumped_Hydro_Capacity_MW[z, m.tp_period[t]]
    )

    # return reservoir to the starting level every day, net of any inflow
    m.Pumped_Hydro_Daily_Balance = Constraint(m.LOAD_ZONES, m.TIMESERIES, rule=lambda m, z, ts:
        sum(
            m.pumped_hydro_efficiency * m.StorePumpedHydro[z, tp]
            + m.pumped_hydro_inflow_mw
            - m.GeneratePumpedHydro[z, tp]
            for tp in m.TS_TPS[ts]
         ) == 0
    )
    

def load_inputs(mod, switch_data, inputs_dir):
    """
    Import pumped hydro data from a .dat file. 
    TODO: change this to allow multiple storage technologies.
    """
    switch_data.load(filename=os.path.join(inputs_dir, 'pumped_hydro.dat'))
