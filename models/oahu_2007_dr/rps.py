"""
# cancel out the basic system load and replace it with a convex combination of bids
"""
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

#    rps_data = {2015: 0.15, 2020: 0.30, 2030: 0.40, 2040: 0.70, 2045: 1.00}
    # accelerated RPS for testing
    rps_data = {2015: 0.30, 2020: 0.40, 2025: 0.70, 2030: 1.00, 2040: 1.00} # must extend past end
    m.RPS_ENERGY_SOURCES = Set(initialize=['WND', 'SUN', 'Biocrude', 'Biodiesel', 'MLG'])
#    m.RPS_DATES = Set(initialize=[2015, 2020, 2030, 2040, 2045], ordered=True)
    m.RPS_DATES = Set(initialize=sorted(rps_data.keys()), ordered=True)
    m.rps_targets = Param(m.RPS_DATES, initialize=lambda m, y: rps_data[y])
#        {2015: 0.15, 2020: 0.30, 2030: 0.40, 2040: 0.70, 2045: 1.00}[y])
    m.rps_target_for_period = Param(m.PERIODS, initialize=lambda m, y:
        m.rps_targets[m.RPS_DATES[bisect.bisect_right(m.RPS_DATES, y)-1]])

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

