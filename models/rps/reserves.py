"""
Defines types of reserve target and components that contribute to reserves,
and enforces the reserve targets.

Much of this could eventually be moved into balancing_areas instead.
"""
import os
from pyomo.environ import *


def define_components(mod):
    """

    """

    mod.lz_balancing_area = Param(mod.LOAD_ZONES, default=lambda m, z: z)
    mod.BALANCING_AREAS = Set(initialize=lambda m: set(
        m.lz_balancing_area[z] for z in m.LOAD_ZONES))

    mod.LZ_Reserves_Up = []
    mod.LZ_Reserves_Down = []


def define_dynamic_components(mod):
    """

    Adds components to a Pyomo abstract model object to enforce the
    first law of thermodynamics at the level of load zone busses. Unless
    otherwise stated, all terms describing power are in units of MW and
    all terms describing energy are in units of MWh.

    Energy_Balance[load_zone, timepoint] is a constraint that mandates
    conservation of energy in every load zone and timepoint. This
    constraint sums the model components in the lists
    LZ_Energy_Components_Produce and LZ_Energy_Components_Consume - each
    of which is indexed by (lz, t) - and ensures they are equal.

    """

    mod.Energy_Balance = Constraint(
        mod.LOAD_ZONES,
        mod.TIMEPOINTS,
        rule=lambda m, lz, t: (
            sum(
                getattr(m, component)[lz, t]
                for component in m.LZ_Energy_Components_Produce
            ) == sum(
                getattr(m, component)[lz, t]
                for component in m.LZ_Energy_Components_Consume)))


def load_inputs(mod, switch_data, inputs_dir):
    """

    Import load zone data. The following tab-separated files are
    expected in the input directory. Their index columns need to be on
    the left, but the data columns can be in any order. Extra columns
    will be ignored during import, and optional columns can be dropped.
    Other modules (such as local_td) may look for additional columns in
    some of these files. If you don't want to specify data for any
    optional parameter, use a dot . for its value. All columns in
    load_zones.tab except for the name of the load zone are optional.

    load_zones.tab
        LOAD_ZONE, lz_cost_multipliers, lz_ccs_distance_km, lz_dbid

    loads.tab
        LOAD_ZONE, TIMEPOINT, lz_demand_mw

    """
    # Include select in each load() function so that it will check out
    # column names, be indifferent to column order, and throw an error
    # message if some columns are not found.
    switch_data.load_aug(
        filename=os.path.join(inputs_dir, 'load_zones.tab'),
        auto_select=True,
        index=mod.LOAD_ZONES,
        param=(mod.lz_cost_multipliers, mod.lz_ccs_distance_km,
               mod.lz_dbid))
    switch_data.load_aug(
        filename=os.path.join(inputs_dir, 'loads.tab'),
        auto_select=True,
        param=(mod.lz_demand_mw))


def save_results(model, instance, outdir):
    """
    Export results to standard files.

    This initial placeholder version is integrating snippets of
    some of Matthias's code into the main codebase.

    """
    import switch_mod.export as export
    export.write_table(
        instance, instance.LOAD_ZONES, instance.TIMEPOINTS,
        output_file=os.path.join("outputs", "load_balance.txt"),
        headings=("load_zone", "timestamp",) + tuple(
            instance.LZ_Energy_Components_Produce +
            instance.LZ_Energy_Components_Consume),
        values=lambda m, lz, t: (lz, m.tp_timestamp[t],) + tuple(
            getattr(m, component)[lz, t]
            for component in (
                m.LZ_Energy_Components_Produce +
                m.LZ_Energy_Components_Consume)))
