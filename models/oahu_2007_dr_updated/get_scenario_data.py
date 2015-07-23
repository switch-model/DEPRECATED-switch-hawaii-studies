#!/usr/bin/python

# based on "Switch-Hawaii/ampl/working oahu version/get_scenario_data.py"

from write_pyomo_table import write_table

# NOTE: ANSI SQL specifies single quotes for literal strings, and postgres conforms
# to this, so all the queries below should use single quotes around strings.

# NOTE: write_table() will automatically convert null values to '.', 
# so pyomo will recognize them as missing data

###########################
# Scenario Definition

# particular settings chosen for this case
# (these will be passed as arguments when the queries are run)
args = dict(
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


#########################
# timescales

write_table('periods.tab', """
    SELECT period AS "INVESTMENT_PERIOD",
            period as period_start,
            period + (
                SELECT (max(period)-min(period)) / (count(distinct period)-1) as length 
                    FROM study_periods WHERE time_sample = %(time_sample)s
                ) - 1 as period_end
        FROM study_periods
        WHERE time_sample = %(time_sample)s
        ORDER by 1;
""", args)

write_table('timeseries.tab', """
    SELECT study_date as "TIMESERIES", period as ts_period, 
        ts_duration_of_tp, ts_num_tps, ts_scale_to_period
    FROM study_date
    WHERE time_sample = %(time_sample)s
    ORDER BY 1;
""", args)

write_table('timepoints.tab', """
    SELECT h.study_hour as timepoint_id, 
            to_char(date_time + (period - extract(year from date_time)) * interval '1 year',
                'YYYY-MM-DD-HH24:MI') as timestamp,
            h.study_date as timeseries 
        FROM study_hour h JOIN study_date d USING (study_date, time_sample)
        WHERE h.time_sample = %(time_sample)s
        ORDER BY period, 3, 2;
""", args)

#########################
# financials

# this just uses a dat file, not a table (and the values are not in a database for now)
with open('financials.dat', 'w') as f:
    f.writelines([
        'param ' + name + ' := ' + str(args[name]) + ';\n' 
        for name in ['base_financial_year', 'interest_rate', 'discount_rate']
    ])

#########################
# load_zones

# note: we don't provide the following fields in this version:
# lz_cost_multipliers, lz_ccs_distance_km, lz_dbid, 
# existing_local_td, local_td_annual_cost_per_mw
write_table('load_zones.tab', """
    SELECT load_zone as "LOAD_ZONE"
    FROM load_zone 
    WHERE load_zone in %(load_zones)s
""", args)

# NOTE: we don't provide lz_peak_loads.tab (sometimes used by local_td.py) in this version.

# get system loads, scaled from the historical years to the model years
# note: 'offset' is a keyword in postgresql, so we use double-quotes to specify the column name
write_table('loads.tab', """
    SELECT 
        l.load_zone AS "LOAD_ZONE", 
        study_hour AS "TIMEPOINT",
        system_load * scale + "offset" AS lz_demand_mw
    FROM study_date d 
        JOIN study_hour h USING (time_sample, study_date)
        JOIN system_load l USING (date_time)
        JOIN system_load_scale s ON (
            s.load_zone = l.load_zone 
            AND s.year_hist = extract(year from l.date_time)
            AND s.year_fore = d.period)
    WHERE l.load_zone in %(load_zones)s
        AND d.time_sample = %(time_sample)s
        AND load_scen_id = %(load_scen_id)s;
""", args)


#########################
# fuels

write_table('non_fuel_energy_sources.tab', """
    SELECT DISTINCT fuel AS "NON_FUEL_ENERGY_SOURCES"
        FROM generator_costs 
        WHERE fuel NOT IN (SELECT fuel_type FROM fuel_costs)
            AND min_vintage_year <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    UNION DISTINCT 
        SELECT aer_fuel_code AS "NON_FUEL_ENERGY_SOURCES" 
        FROM existing_plants 
        WHERE aer_fuel_code NOT IN (SELECT fuel_type FROM fuel_costs)
            AND load_zone in %(load_zones)s
            AND insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s);
""", args)

# TODO: tabulate CO2 intensity of fuels
write_table('fuels.tab', """
    SELECT DISTINCT fuel_type AS fuel, 0.0 AS co2_intensity, 0.0 AS upstream_co2_intensity
    FROM fuel_costs
    WHERE load_zone in %(load_zones)s;
""", args)
        
#########################
# fuel_markets

# TODO: get monthly fuel costs from Karl Jandoc spreadsheet

write_table('fuel_cost.tab', """
    SELECT load_zone, fuel_type as fuel, period, price_mmbtu as fuel_cost 
        FROM fuel_costs c JOIN study_periods p ON (c.year=p.period)
        WHERE load_zone in %(load_zones)s 
            AND fuel_scen_id = %(fuel_scen_id)s
            AND p.time_sample = %(time_sample)s;
""", args)


#########################
# gen_tech

# TODO: provide reasonable retirement ages for existing plants (not 100+base age)
# TODO: rename/drop the DistPV_peak and DistPV_flat technologies in the generator_costs table
# note: this zeroes out variable_o_m for renewable projects
# TODO: find out where variable_o_m came from for renewable projects and put it in the right place
# TODO: fix baseload flag in the database
# TODO: account for multiple fuel sources for a single plant in the upstream database
# and propagate that to this table.
# TODO: make sure the heat rates are null for non-fuel projects in the upstream database, 
# and remove the correction code from here
# TODO: create heat_rate and fuel columns in the existing_plants_gen_tech table and simplify the query below.
# TODO: add unit sizes for new projects to the generator_costs table (new projects) from
# Switch-Hawaii/data/HECO\ IRP\ Report/IRP-2013-App-K-Supply-Side-Resource-Assessment-062813-Filed.pdf
# and then incorporate those into unit_sizes.tab below.
# NOTE: this converts variable o&m from $/kWh to $/MWh
# NOTE: for now we turn off the baseload flag for all gens, to allow for a 100% RPS
# NOTE: we don't provide the following in this version:
# g_min_build_capacity
# g_ccs_capture_efficiency, g_ccs_energy_load,
# g_storage_efficiency, g_store_to_release_ratio
            
write_table('generator_info.tab', """
    SELECT  replace(technology,'DistPV_peak', 'DistPV') as generation_technology, 
            replace(technology,'DistPV_peak', 'DistPV') as g_dbid,
            max_age_years as g_max_age, 
            scheduled_outage_rate as g_scheduled_outage_rate, 
            forced_outage_rate as g_forced_outage_rate,
            intermittent as g_is_variable, 
            0 as g_is_baseload,
            0 as g_is_flexible_baseload, 
            0 as g_is_cogen,
            0 as g_competes_for_space, 
            CASE WHEN fuel IN ('SUN', 'WND') THEN 0 ELSE variable_o_m * 1000.0 END AS g_variable_o_m,
            fuel AS g_energy_source,
            CASE WHEN fuel IN (SELECT fuel_type FROM fuel_costs) THEN 0.001*heat_rate ELSE null END
                AS g_full_load_heat_rate,
            null AS g_unit_size
        FROM generator_costs
        WHERE technology NOT IN ('DistPV_flat')
            AND min_vintage_year <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    UNION SELECT
            g.technology as generation_technology, 
            g.technology as g_dbid, 
            g.max_age + 100 as g_max_age, 
            g.scheduled_outage_rate as g_scheduled_outage_rate, 
            g.forced_outage_rate as g_forced_outage_rate,
            g.variable as g_is_variable, 
            0 as g_is_baseload,
            0 as g_is_flexible_baseload, 
            g.cogen as g_is_cogen,
            g.competes_for_space as g_competes_for_space, 
            CASE WHEN MIN(p.aer_fuel_code) IN ('SUN', 'WND') THEN 0.0 ELSE AVG(g.variable_o_m) * 1000.0 END 
                AS g_variable_o_m,
            MIN(p.aer_fuel_code) AS g_energy_source,
            CASE WHEN MIN(p.aer_fuel_code) IN (SELECT fuel_type FROM fuel_costs) 
                THEN 0.001*ROUND(SUM(p.heat_rate*p.avg_mw)/SUM(p.avg_mw)) 
                ELSE null 
                END 
                AS g_full_load_heat_rate,
            AVG(peak_mw) AS g_unit_size  -- minimum block size for unit commitment
        FROM existing_plants_gen_tech g JOIN existing_plants p USING (technology)
        WHERE p.load_zone in %(load_zones)s
            AND p.insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
        GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
    ORDER BY 1;
""", args)

# TODO: write code in project.unitcommit.commit to load part-load heat rates
# TODO: get part-load heat rates for new plant technologies and report them in 
# project.unit.commit instead of full-load heat rates here.
# TODO: report part-load heat rates for existing plants in project.unitcommit.commit
# (maybe on a project-specific basis instead of generalized for each technology)
# NOTE: we divide heat rate by 1000 to convert from Btu/kWh to MBtu/MWh


# note: this table can only hold costs for technologies with future build years,
# so costs for existing technologies are specified in project_specific_costs.tab
# NOTE: costs in this version of switch are expressed in $/MW, $/MW-year, etc., not per kW.
write_table('gen_new_build_costs.tab', """
    SELECT  
        replace(technology,'DistPV_peak', 'DistPV') as generation_technology, 
        period AS investment_period,
        capital_cost_per_kw *1000.0 AS g_overnight_cost, 
        fixed_o_m*1000.0 AS g_fixed_o_m
    FROM generator_costs, study_periods
    WHERE technology NOT IN ('DistPV_flat')
        AND time_sample = %(time_sample)s
        AND min_vintage_year <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    ORDER BY 1, 2;
""", args)
    # UNION
    # SELECT technology AS generation_technology, 
    #         insvyear AS investment_period, 
    #         sum(overnight_cost * 1000.0 * peak_mw) / sum(peak_mw) as g_overnight_cost,
    #         sum(fixed_o_m * 1000.0 * peak_mw) / sum(peak_mw) as g_fixed_o_m
    # FROM existing_plants
    # WHERE load_zone in %(load_zones)s
    #     AND insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    # GROUP BY 1, 2



#########################
# project.build

# TODO: find connection costs and add them to the switch database (currently all zeroes)
# TODO: find out why exissting wind and solar projects have non-zero variable O&M in the switch 
# database, and zero them out there instead of here.
# NOTE: if a generator technology in the generator_costs table doesn't have a match in the connect_cost
# table, we use the generic_cost_per_kw from the generator_costs table. If that is also null,
# then the connection cost will be given whatever default value is specified in the SWITCH code
# (probably zero).
# If individual projects are identified in connect_cost or max_capacity, we use those;
# then we also add generic projects in each load_zone for any technologies that are not
# marked as resource_limited in generator_costs.
# NOTE: if a technology ever appears in either max_capacity or connect_cost, then
# every possible project of that type should be recorded in that table. 
# Technologies that don't appear in these tables are deemed generic projects,
# which can be added once in each load zone.
# NOTE: the queries below will not detect if a technology is attached to different 
# sets of project definitions in the max_capacity and connect_cost tables;
# we leave it to the user to ensure this doesn't happen.
# NOTE: we don't provide the following, because they are specified in generator_info.tab instead
# proj_full_load_heat_rate, proj_forced_outage_rate, proj_scheduled_outage_rate
# (the project-specific data would only be for otherwise-similar projects that have degraded and 
# now have different heat rates)
# NOTE: variable costs for existing plants could alternatively be added to the generator_info.tab 
# table (aggregated by technology instead of project). That is where we put the variable costs for new projects.
# NOTE: we convert costs from $/kWh to $/MWh

write_table('project_info.tab', """
        -- make a list of all projects with detailed definitions (and gather the available data)
        DO $$ BEGIN PERFORM drop_temporary_table('t_specific_projects'); END $$;
        CREATE TEMPORARY TABLE t_specific_projects AS
            SELECT 
                concat_ws('_', 
                    COALESCE(m.load_zone, c.load_zone),
                    COALESCE(m.technology, c.technology),
                    COALESCE(m.site, c.site),
                    COALESCE(m.orientation, c.orientation)
                ) AS "PROJECT",
                COALESCE(m.load_zone, c.load_zone) as proj_load_zone,
                COALESCE(m.technology, c.technology) AS proj_gen_tech,
                %(connect_cost_per_mw_km)s*connect_length_km + 1000.0*connect_cost_per_kw as proj_connect_cost_per_mw,
                max_capacity as proj_capacity_limit_mw
            FROM connect_cost c FULL JOIN max_capacity m USING (load_zone, technology, site, orientation);

        -- make a list of generic projects (for which no detailed definitions are available)
        DO $$ BEGIN PERFORM drop_temporary_table('t_generic_projects'); END $$;
        CREATE TEMPORARY TABLE t_generic_projects AS
            SELECT 
                concat_ws('_', load_zone, technology) AS "PROJECT",
                load_zone as proj_load_zone,
                technology AS proj_gen_tech,
                cast(null as float) AS proj_connect_cost_per_mw,
                cast(null as float) AS proj_capacity_limit_mw
            FROM generator_costs g
                CROSS JOIN (SELECT DISTINCT load_zone FROM system_load) z
            WHERE g.technology NOT IN (SELECT proj_gen_tech FROM t_specific_projects);
        
        -- merge the specific and generic projects
        DO $$ BEGIN PERFORM drop_temporary_table('t_all_projects'); END $$;
        CREATE TEMPORARY TABLE t_all_projects AS
        SELECT * FROM t_specific_projects UNION SELECT * from t_generic_projects;
        
        -- collect extra data from the generator_costs table and filter out disallowed projects
        SELECT
            a."PROJECT", 
            null as proj_dbid,
            a.proj_gen_tech, 
            a.proj_load_zone, 
            COALESCE(a.proj_connect_cost_per_mw, 1000.0*g.connect_cost_per_kw_generic, 0.0) AS proj_connect_cost_per_mw,
            a.proj_capacity_limit_mw,
            cast(null as float) AS proj_variable_om    -- this is supplied in generator_info.tab for new projects
        FROM t_all_projects a JOIN generator_costs g on g.technology=a.proj_gen_tech
        WHERE a.proj_load_zone IN %(load_zones)s
            AND g.min_vintage_year <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
        UNION
        -- collect data on existing projects
        SELECT DISTINCT 
            project_id AS "PROJECT",
            null AS dbid,
            technology AS proj_gen_tech, 
            load_zone AS proj_load_zone, 
            0.0 AS proj_connect_cost_per_mw,
            cast(null as float) AS proj_capacity_limit_mw,
            sum(CASE WHEN aer_fuel_code IN ('SUN', 'WND') THEN 0.0 ELSE variable_o_m END * 1000.0 * avg_mw)
               / sum(avg_mw) AS proj_variable_om
        FROM existing_plants
        WHERE load_zone IN %(load_zones)s
            AND insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
        GROUP BY 1, 2, 3, 4, 5, 6
        ORDER BY 4, 3, 1;
""", args)


write_table('proj_existing_builds.tab', """
    SELECT project_id AS "PROJECT", 
            insvyear AS build_year, 
            sum(peak_mw) as proj_existing_cap
    FROM existing_plants
    WHERE load_zone in %(load_zones)s
        AND insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    GROUP BY 1, 2;
""", args)

# note: we have to put cost data for existing projects in proj_build_costs.tab
# because gen_new_build_costs only covers future investment periods.
# NOTE: these costs must be expressed per MW, not per kW
write_table('proj_build_costs.tab', """
    SELECT project_id AS "PROJECT", 
            insvyear AS build_year, 
            sum(overnight_cost * 1000.0 * peak_mw) / sum(peak_mw) as proj_overnight_cost,
            sum(fixed_o_m * 1000.0 * peak_mw) / sum(peak_mw) as proj_fixed_om
    FROM existing_plants
    WHERE load_zone in %(load_zones)s
        AND insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    GROUP BY 1, 2;
""", args)


#########################
# project.dispatch

write_table('variable_capacity_factors.tab', """
    SELECT 
        concat_ws('_', load_zone, technology, site, orientation) as "PROJECT",
        study_hour as timepoint,
        cap_factor as proj_max_capacity_factor
    FROM generator_costs g JOIN cap_factor c USING (technology)
        JOIN study_hour h using (date_time)
    WHERE load_zone in %(load_zones)s and time_sample = %(time_sample)s
        AND min_vintage_year <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    UNION 
    SELECT 
        c.project_id as "PROJECT", 
        study_hour as timepoint, 
        cap_factor as proj_max_capacity_factor
    FROM existing_plants p JOIN existing_plants_cap_factor c USING (project_id)
        JOIN study_hour h USING (date_time)
    WHERE h.date_time = c.date_time 
        AND c.load_zone in %(load_zones)s
        AND h.time_sample = %(time_sample)s
        AND insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
    ORDER BY 1, 2
""", args)


#########################
# project.discrete_build

# include this module, but it doesn't need any additional data.


#########################
# project.unitcommit.commit

# minimum commitment levels for existing projects

# TODO: set proj_max_commit_fraction based on maintenance outage schedules
# (needed for comparing switch marginal costs to FERC 715 data in 2007-08)

# TODO: eventually add code to only provide these values for the timepoints before 
# each project retires (providing them after retirement will cause an error).

write_table('proj_commit_bounds_timeseries.tab', """
    SELECT * FROM (
        SELECT project_id as "PROJECT",
            study_hour AS "TIMEPOINT",
            case when %(enable_must_run)s = 1 and must_run = 1 then 1.0 else null end as proj_min_commit_fraction, 
            null as proj_max_commit_fraction,
            null as proj_min_load_fraction
        FROM existing_plants, study_hour
        WHERE load_zone in %(load_zones)s
            AND time_sample = %(time_sample)s
    ) AS the_data
    WHERE proj_min_commit_fraction IS NOT NULL OR proj_max_commit_fraction IS NOT NULL OR proj_min_load_fraction IS NOT NULL;
""", args)

# TODO: get minimum loads for new and existing power plants and then activate the query below

# write_table('gen_unit_commit.tab', """
#     SELECT 
#         technology AS generation_technology, 
#         min_load / unit_size AS g_min_load_fraction, 
#         null AS g_startup_fuel,
#         null AS g_startup_om
#     FROM generator_costs
#     UNION SELECT DISTINCT
#         technology AS generation_technology, 
#         sum(min_load) / sum(peak_mw) AS g_min_load_fraction, 
#         null AS g_startup_fuel,
#         null AS g_startup_om
#     FROM existing_plants
#     WHERE load_zone in %(load_zones)s
#        AND insvyear <= (SELECT MAX(period) FROM study_periods WHERE time_sample = %(time_sample)s)
#     GROUP BY 1
#     ORDER by 1;
# """, args)


#########################
# project.unitcommit.fuel_use

# TODO: heat rate curves for new projects
# TODO: heat rate curves for existing plants

#########################
# project.unitcommit.discrete

# include this module, but it doesn't need any additional data.


# TODO: write reserves code
# TODO: create data files showing reserve rules


#########################
# trans_build
# --- Not used ---

#             
# write_table('trans_lines.tab', """
#     SELECT load_area_start AS load_zone_start, load_area_end AS load_zone_end, 
#         tid, length_km AS transmission_length_km, efficiency AS transmission_efficiency,
#         existing_mw_from AS existing_transmission_from, 
#         existing_mw_to AS existing_transmission_to 
#     FROM trans_line 
#     WHERE load_area_start IN %(load_zones)s OR load_area_end IN %(load_zones)s
# """, args)
#             
#             
#      

#########################
# trans_dispatch
# --- Not used ---


