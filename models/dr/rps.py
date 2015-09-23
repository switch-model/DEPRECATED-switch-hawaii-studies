from pprint import pprint
from pyomo.environ import *
import switch_mod.utilities as utilities


def define_components(m):
    """

    """
    ###################
    # RPS calculation
    ##################
    
    m.f_rps_eligible = Param(m.FUELS, within=Binary)

    m.RPS_ENERGY_SOURCES = Set(initialize=lambda m: m.NON_FUEL_ENERGY_SOURCES + [f for f in m.FUELS if m.f_rps_eligible[f]])

    m.RPS_YEARS = Set(ordered=True)
    m.rps_target = Param(m.RPS_YEARS)

    def rps_target_for_period_rule(m, p):
        """find the last target that is in effect before the _end_ of the period"""
        latest_target = max(y for y in m.RPS_YEARS if y < p + m.period_length_years[p])
        return m.rps_target[latest_target]
    m.rps_target_for_period = Param(m.PERIODS, initialize=rps_target_for_period_rule)

    # Note: this rule ignores pumped hydro, so it could be gamed by producing extra 
    # RPS-eligible power and burning it off in storage losses; on the other hand, 
    # it also neglects the (small) contribution from net flow of pumped hydro projects.
    # TODO: incorporate pumped hydro into this rule, maybe change the target to refer to 
    # sum(getattr(m, component)[lz, t] for lz in m.LOAD_ZONES) for component in m.LZ_Energy_Components_Produce)
    m.RPS_Enforce = Constraint(m.PERIODS, rule=lambda m, per:
        ( # RPS-eligible sources
            sum(
                get(m.DispatchProjByFuel, (p, t, f), 0.0) 
                    for f in m.FUELS if f in m.RPS_ENERGY_SOURCES
                        for p in m.PROJECTS_BY_FUEL[f]
                            for t in m.PERIOD_TPS[per]  # could be accelerated a bit if we had m.ACTIVE_PERIODS_FOR_PROJECT[p]
            )
            +
            sum(
                get(m.DispatchProj, (p, t), 0.0)
                    for f in m.NON_FUEL_ENERGY_SOURCES if f in m.RPS_ENERGY_SOURCES
                        for p in m.PROJECTS_BY_NON_FUEL_ENERGY_SOURCE[f]
                            for t in m.PERIOD_TPS[per]
            )
            -
            # assume DumpPower is curtailed renewable energy
            sum(m.DumpPower[lz, tp] for lz in m.LOAD_ZONES for tp in m.PERIOD_TPS[per])
        )
        >=
        m.rps_target_for_period[per]
        # all energy sources
        * sum(get(m.DispatchProj, (p, t), 0.0) for p in m.PROJECTS for t in m.PERIOD_TPS[per])
    )

def load_inputs(m, switch_data, inputs_dir):
    switch_data.load_aug(
        optional=True,
        filename=os.path.join(inputs_dir, 'fuels.tab'),
        select=('rps_eligible',),
        param=(m.f_rps_eligible,))
    switch_data.load_aug(
        optional=True,
        filename=os.path.join(inputs_dir, 'rps_targets.tab'),
        autoselect=True,
        index=m.RPS_YEARS,
        param=(m.rps_target,))

