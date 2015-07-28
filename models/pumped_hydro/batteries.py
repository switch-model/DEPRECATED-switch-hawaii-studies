import os
from pyomo.environ import *

def define_components(m):
    
    # battery capital cost
    m.battery_capital_cost_per_mwh_capacity = Param()
    # number of full cycles the battery can do; we assume shallower cycles do proportionally less damage
    m.battery_n_cycles = Param()
    # maximum depth of discharge
    m.battery_max_discharge = Param()
    # round-trip efficiency
    m.battery_efficiency = Param()
    # fastest time that storage can be emptied (down to max_discharge)
    m.battery_min_discharge_time = Param()

    # we treat storage as infinitely long-lived (so we pay just interest on the loan),
    # but charge a usage fee corresponding to the reduction in life during each cycle 
    # (i.e., enough to restore it to like-new status, on average)
    m.battery_cost_per_mwh_cycled = Param(initialize = lambda m:
        m.battery_capital_cost_per_mwh_capacity / (m.battery_n_cycles * m.battery_max_discharge)
    )
    m.battery_fixed_cost_per_year = Param(initialize = lambda m:
        m.battery_capital_cost_per_mwh_capacity * m.interest_rate
    )

    # amount of battery capacity to build and use
    # TODO: integrate this with other project data, so it can contribute to reserves, etc.
    m.BuildBattery = Var(m.LOAD_ZONES, m.PERIODS, within=NonNegativeReals)
    m.Battery_Capacity = Expression(m.LOAD_ZONES, m.PERIODS, rule=lambda m, z, p:
        sum(m.BuildBattery[z, m.PERIODS[i]] for i in range(1, m.PERIODS.ord(p)))
    )

    # rate of charging/discharging battery
    m.ChargeBattery = Var(m.LOAD_ZONES, m.TIMEPOINTS, within=NonNegativeReals)
    m.DischargeBattery = Var(m.LOAD_ZONES, m.TIMEPOINTS, within=NonNegativeReals)

    # storage level at start of each timepoint
    m.BatteryLevel = Var(m.LOAD_ZONES, m.TIMEPOINTS, within=NonNegativeReals)

    # add the storage to the model's energy balance
    m.LZ_Energy_Components_Produce.append('DischargeBattery')
    m.LZ_Energy_Components_Consume.append('ChargeBattery')
    
    # add the batteries to the objective function
    m.Battery_Variable_Cost = Expression(m.TIMEPOINTS, rule=lambda m, t:
        sum(m.battery_cost_per_mwh_cycled * m.DischargeBattery[z, t] for z in m.LOAD_ZONES)
    )
    m.Battery_Fixed_Cost_Annual = Expression(m.PERIODS, rule=lambda m, p:
        sum(m.battery_fixed_cost_per_year * m.Battery_Capacity[z, p] for z in m.LOAD_ZONES)
    )
    m.cost_components_tp.append('Battery_Variable_Cost')
    m.cost_components_annual.append('Battery_Fixed_Cost_Annual')

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
    Import battery data from a .dat file. 
    TODO: change this to allow multiple storage technologies.
    """
    switch_data.load(filename=os.path.join(inputs_dir, 'batteries.dat'))
