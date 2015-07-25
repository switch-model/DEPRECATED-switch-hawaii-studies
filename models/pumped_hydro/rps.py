import bisect
from pprint import pprint
from pyomo.environ import *
import switch_mod.utilities as utilities


def define_components(m):
    """

    """
    ###################
    # RPS calculation (very crude)
    ##################
    
    rps_data = {2015: 0.15, 2020: 0.30, 2030: 0.40, 2040: 0.70, 2045: 1.00, 2100: 1.00} # must extend past last period
    rps_energy_sources = ['WND', 'SUN', 'Biocrude', 'Biodiesel', 'MLG']

    m.RPS_ENERGY_SOURCES = Set(initialize=rps_energy_sources)
    m.RPS_DATES = Set(initialize=sorted(rps_data.keys()), ordered=True)
    m.rps_targets = Param(m.RPS_DATES, initialize=lambda m, y: rps_data[y])
    m.rps_target_for_period = Param(m.PERIODS, initialize=lambda m, period:
        # find the last target that is in effect before the end of the period
        # note that RPS_DATES is 1-based
        m.rps_targets[m.RPS_DATES[bisect.bisect_right(m.RPS_DATES, period)-1]])

    m.RPS_Enforce = Constraint(m.PERIODS, rule=lambda m, per:
        ( # RE Sources
            sum(
                m.DispatchProj[proj, tp] 
                for proj, tp in m.PROJ_DISPATCH_POINTS
                if m.tp_period[tp] == per and proj in m.FUEL_BASED_PROJECTS and m.proj_fuel[proj] in m.RPS_ENERGY_SOURCES
            )
            +
            sum(
                m.DispatchProj[proj, tp] 
                for proj, tp in m.PROJ_DISPATCH_POINTS
                if m.tp_period[tp] == per and proj in m.NON_FUEL_BASED_PROJECTS and m.proj_non_fuel_energy_source[proj] in m.RPS_ENERGY_SOURCES
            )
            +
            sum(    # assume DumpPower is curtailed renewable energy (note: DumpPower is negative)
                m.DumpPower[lz, tp]
                for lz in m.LOAD_ZONES for tp in m.TIMEPOINTS
                if m.tp_period[tp] == per
            )
        )
        >=
        m.rps_target_for_period[per] 
        * sum(  # all energy sources
            m.DispatchProj[proj, tp] 
            for (proj, tp) in m.PROJ_DISPATCH_POINTS
            if m.tp_period[tp] == per
        )
    )

