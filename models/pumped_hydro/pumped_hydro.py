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
    m.BuildPumpedHydro = Var(m.LOAD_ZONES, m.PERIODS)
    m.Pumped_Hydro_Capacity = Expression(m.LOAD_ZONES, m.PERIODS, rule=lambda m, z, p:
        sum(m.BuildPumpedHydro[z, m.PERIODS[i]] for i in range(1, m.PERIODS.ord(p)))
    )

    # How to run pumped hydro
    m.GeneratePumpedHydro = Var(m.LOAD_ZONES, m.TIMEPOINTS)
    m.StorePumpedHydro = Var(m.LOAD_ZONES, m.TIMEPOINTS)
    
    # calculate costs
    m.Pumped_Hydro_Fixed_Cost_Annual = Expression(m.PERIODS, rule=lambda m, p:
        sum(m.pumped_hydro_fixed_cost_per_mw_per_year * m.Pumped_Hydro_Capacity[z, p] for z in m.LOAD_ZONES)
    )
    m.cost_components_annual.append('Pumped_Hydro_Fixed_Cost_Annual')
    

    # add the storage to the model's energy balance
    m.LZ_Energy_Components_Produce.append('GeneratePumpedHydro')
    m.LZ_Energy_Components_Consume.append('StorePumpedHydro')
    
    # add the batteries to the objective function

    # Calculate the state of charge based on conservation of energy
    # NOTE: this is circular for each day
    # NOTE: the overall level for the day is free, but the levels each timepoint are chained.
    m.Battery_Level_Calc = Constraint(m.LOAD_ZONES, m.TIMEPOINTS, rule=lambda m, z, t:
        m.BatteryLevel[z, t] == 
            m.BatteryLevel[z, m.tp_previous[t]]
            + m.battery_efficiency * m.ChargeBattery[z, m.tp_previous[t]] 
            - m.DischargeBattery[z, m.tp_previous[t]]
    )
      
    # limits on storage level
    m.Battery_Min_Level = Constraint(m.LOAD_ZONES, m.TIMEPOINTS, rule=lambda m, z, t: 
        (1.0 - m.battery_max_discharge) * m.Battery_Capacity[z, m.tp_period[t]]
        <= 
        m.BatteryLevel[z, t]
    )
    m.Battery_Max_Level = Constraint(m.LOAD_ZONES, m.TIMEPOINTS, rule=lambda m, z, t: 
        m.BatteryLevel[z, t]
        <= 
        m.Battery_Capacity[z, m.tp_period[t]]
    )

    m.Battery_Max_Charge = Constraint(m.LOAD_ZONES, m.TIMEPOINTS, rule=lambda m, z, t:
        m.ChargeBattery[z, t]
        <=
        m.Battery_Capacity[z, m.tp_period[t]] * m.battery_max_discharge / m.battery_min_discharge_time
    )
    m.Battery_Max_Disharge = Constraint(m.LOAD_ZONES, m.TIMEPOINTS, rule=lambda m, z, t:
        m.DischargeBattery[z, t]
        <=
        m.Battery_Capacity[z, m.tp_period[t]] * m.battery_max_discharge / m.battery_min_discharge_time
    )


def load_inputs(mod, switch_data, inputs_dir):
    """
    Import pumped hydro data from a .dat file. 
    TODO: change this to allow multiple storage technologies.
    """
    switch_data.load(filename=os.path.join(inputs_dir, 'pumped_hydro.dat'))
