#!/usr/bin/env python

# This will eventually be a good place to put all the code to create the main database
# for Switch-Hawaii. For now it just imports a few miscellaneous tables that were not
# imported by other code.
# Started by Matthias Fripp on 2015-07-27

import time, sys, os, itertools, csv
from textwrap import dedent

try:
    import openpyxl
except ImportError:
    print "This script requires the openpyxl module to access the data in Microsoft Excel files."
    print "Please execute 'sudo pip install openpyxl' or 'pip install openpyxl' (Windows)."
    raise

switch_db = 'switch'
pghost = 'redr.eng.hawaii.edu'

try:
    import psycopg2
except ImportError:
    print "This script requires the psycopg2 module to access the postgresql database."
    print "Please execute 'sudo pip install psycopg2' or 'pip install psycopg2' (Windows)."
    raise
try:
    # note: the connection gets created when the module loads and never gets closed (until presumably python exits)
    con = psycopg2.connect(database=switch_db, host=pghost)
    # set connection to commit changes automatically after each query is run
    con.autocommit = True

except psycopg2.OperationalError:
    print dedent("""
        ############################################################################################
        Error while connecting to {db} database on postgresql server {server}.
        Please ensure that your user name on the local system is the same as your postgresql user 
        name or there is a local PGUSER environment variable set with your postgresql user name.
        There should also be a line like "*:*:{db}:<username>:<password>" in ~/.pgpass or 
        %APPDATA%\postgresql\pgpass.conf (Windows). On Unix systems, .pgpass should be chmod 0600.
        See http://www.postgresql.org/docs/9.3/static/libpq-pgpass.html for more details.
        ############################################################################################
        """.format(db=switch_db, server=pghost))
    raise


def main():
    # run all the import scripts (or at least the ones we want)
    # ev_adoption()
    # fuel_costs()
    # energy_source_properties()
    rps_timeseries()

def execute(query, arguments=None):
    args = [dedent(query)]
    if arguments is not None:
        args.append(arguments)
    cur = con.cursor()
    cur.execute(*args)
    return cur

def executemany(query, arguments=None):
    args = [dedent(query)]
    if arguments is not None:
        args.append(arguments)
    cur = con.cursor()
    cur.executemany(*args)

def get_table_from_xlsx(xlsx_file, named_range, transpose=False):
    wb = openpyxl.load_workbook(xlsx_file, data_only=True)  # load the file, ignore formula text
    full_range = wb.get_named_range(named_range)
    # note: named range should be a simple rectangular region; 
    # if it contains more than one region we ignore all but the first
    d1 = full_range.destinations[0]
    ws = d1[0]
    region = d1[1]
    data = list(tuple(c.value for c in r) for r in ws[region])
    if transpose:
        data = zip(*data)
    head = data.pop(0)  # take out the header row
    data = zip(*data)   # switch from row to column orientation
    # make a dictionary, with one column for each element of header row
    return dict(zip(head, data))
    
#########################
# rps timeseries (reusing version from before the server crashed)
def rps_timeseries():
    execute("""
        delete from study_date where time_sample='rps';
        delete from study_hour where time_sample='rps';    
    """)

    with open('timeseries_rps.tab','r') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            dt = str(r["TIMESERIES"])[2:8]
            execute("""
                INSERT INTO study_date 
                    (time_sample, period, study_date, 
                    month_of_year, date, 
                    hours_in_sample,
                    ts_num_tps, ts_duration_of_tp, ts_scale_to_period)
                VALUES
                    (%s, %s, %s,
                    %s, %s,
                    %s,
                    %s, %s, %s);
            """,
                ('rps', r["ts_period"], r["TIMESERIES"], 
                int(dt[2:4]), "20"+dt[0:2]+"-"+dt[2:4]+"-"+dt[4:6],
                float(r["ts_duration_of_tp"])*float(r["ts_scale_to_period"]),
                r["ts_num_tps"], r["ts_duration_of_tp"], r["ts_scale_to_period"])
            )
    
    import sys
    with open('timepoints_rps.tab','r') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            i += 1
            sys.stdout.write('row: {}\r'.format(i))
            sys.stdout.flush()
            t = r["timestamp"][5:]
            dt = str(r["timeseries"])[2:8]
            execute("""
                INSERT INTO study_hour 
                    (time_sample, study_date, study_hour,
                    hour_of_day, date_time)
                VALUES
                    (%s, %s, %s,
                    %s, 
                    cast(%s as timestamp with time zone));
            """,
                ('rps', r["timeseries"], r["timepoint_id"], 
                int(t[6:8]), 
                "20" + dt[0:2] + '-' + t[:5] + ' ' + t[6:] + ':00-10')
            )

    execute("""
        delete from study_periods where time_sample='rps';
        insert into study_periods
            select distinct time_sample, period from study_date
            where time_sample='rps'
            order by 2;

        -- mini RPS study (even months, even hours) for reasonable results in relatively short time

        drop table if exists tdoublemonths;
        create temporary table tdoublemonths
            (month_of_year smallint primary key, days_in_month smallint);
        insert into tdoublemonths values 
          (1, 59), (2, 59), (3, 61), (4, 61), (5, 61), (6, 61),
          (7, 62), (8, 62), (9, 61), (10, 61), (11, 61), (12, 61);

        delete from study_date where time_sample='rps_mini';
        insert into study_date 
            (period, study_date, month_of_year, date, 
            hours_in_sample, time_sample, ts_num_tps, ts_duration_of_tp, ts_scale_to_period)
            select period, study_date, d.month_of_year, date,
                0.0 as hours_in_sample, 
                'rps_mini' as time_sample,
                12 as ts_num_tps, 2.0 as ts_duration_of_tp,
                case when ts_scale_to_period < 100 then 2*%(years_per_period)s 
                    else (days_in_month-2)*%(years_per_period)s end as ts_scale_to_period
            from study_date d join tdoublemonths m using (month_of_year)
            where time_sample = 'rps' and mod(month_of_year, 2)=0
            order by 1, 3, 5 desc, 4;

        delete from study_hour where time_sample='rps_mini';
        insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
          select h.study_date, study_hour, hour_of_day, date_time, 
            'rps_mini' as time_sample
          from study_hour h join study_date d on (d.time_sample='rps_mini' and d.study_date=h.study_date)
          where h.time_sample = 'rps' and mod(hour_of_day, 2)=0 
          order by period, month_of_year, hours_in_sample desc, hour_of_day;

        delete from study_periods where time_sample='rps_mini';
        insert into study_periods
            select distinct time_sample, period from study_date
            where time_sample='rps_mini'
            order by 2;


    """, dict(years_per_period=8))


    print "Created rps and rps_mini time samples."


#########################
# ev adoption
def ev_adoption():
    # identify pairs of (ev_scen_id, HECO scenario name):
    ev_adoption_scenarios=(
        (1, 'No Burning Desire'), # low
        (2, 'Blazing a Bold Frontier'), # high
        (3, 'Stuck in the Middle'), # medium, a.k.a. 'Moved by Passion'
    )
    # get the EV adoption curves from an Excel workbook
    # (based on HECO IRP 2013 Appendix E-10, p. E-113, extended to 2050)
    ev_adoption_curves = get_table_from_xlsx("EV simple projections.xlsx", named_range='EV_Adoption')

    # create the ev_adoption table
    execute("""
        DROP TABLE IF EXISTS ev_adoption;
        CREATE TABLE ev_adoption (
            load_zone varchar(40),
            year int,
            ev_scen_id int,
            ev_gwh float
        );
    """)

    # insert data into the ev_adoption table
    n_rows = len(ev_adoption_curves['Year'])
    for (ev_scen_id, col_name) in ev_adoption_scenarios:
        executemany(
            "INSERT INTO ev_adoption (load_zone, year, ev_scen_id, ev_gwh) VALUES (%s, %s, %s, %s)",
            zip(['Oahu']*n_rows, ev_adoption_curves['Year'], [ev_scen_id]*n_rows, ev_adoption_curves[col_name])
        )

    print "Created ev_adoption table."


#########################
# Oahu fuel price forecasts, derived from EIA

def fuel_costs():
    # get the forecasts from an Excel workbook 
    # Based on various sources, cited in the workbook, extended to 2050
    fuel_forecast = get_table_from_xlsx(
        "../../../Reference Docs/HECO Plans/HECO fuel cost forecasts.xlsx", 
        named_range='Adjusted_EIA_Forecast',
        transpose=True
    )

    # create the fuel_costs table if needed
    execute("""
        CREATE TABLE IF NOT EXISTS fuel_costs (
            load_zone varchar(40),
            year int,
            fuel_type varchar(30),
            price_mmbtu float,
            fuel_scen_id varchar(20),
            tier varchar(20)
        );
    """)

    # remove any existing records
    execute("""
        DELETE FROM fuel_costs WHERE fuel_scen_id='EIA_ref';
    """)

    # take out the list of years, so the dictionary just has one entry for each fuel
    years = fuel_forecast.pop('Year')

    # insert data into the fuel_costs table
    n_rows = len(years)
    for f in fuel_forecast:
        ft=f.split(", ")
        fuel = ft[0]
        tier = ft[1] if len(ft) >= 2 else 'base'
        executemany("""
            INSERT INTO fuel_costs (load_zone, year, fuel_type, price_mmbtu, fuel_scen_id, tier) 
            VALUES (%s, %s, %s, %s, %s, %s)""",
            zip(['Oahu']*n_rows, 
                years,
                [fuel]*n_rows,
                fuel_forecast[f], 
                ["EIA_ref"]*n_rows,
                [tier]*n_rows
            )
        )

    print "Added EIA-derived forecast (fuel_scen_id=EIA_ref) to fuel_costs table."

#########################
# Fuel properties, maintained manually in the Excel forecast workbook 
def energy_source_properties():
    properties = get_table_from_xlsx(
        "../../../Reference Docs/HECO Plans/HECO fuel cost forecasts.xlsx", 
        named_range='Fuel_Properties'
    )

    # create the fuel_properties table if needed
    execute("""
        CREATE TABLE IF NOT EXISTS energy_source_properties (
            energy_source VARCHAR(30) PRIMARY KEY,      -- name of the fuel
            fuel_rank DECIMAL(4, 2),           -- usually 1-5, but may be decimal, e.g., 1.5
            rps_eligible SMALLINT,             -- 0 or 1
            co2_intensity FLOAT                -- tCO2 per MMBtu
        );
    """)

    # create a temporary table to hold the data before aggregating by fuel type
    execute("""
        DROP TABLE IF EXISTS t_energy_source_properties;
        CREATE TEMPORARY TABLE t_energy_source_properties (LIKE energy_source_properties);
    """)

    # insert data into the energy_source_properties table
    executemany("""
        INSERT INTO t_energy_source_properties (energy_source, fuel_rank, rps_eligible, co2_intensity) 
        VALUES (%s, %s, %s, %s)""",
        zip(
            [f.split(', ')[0] for f in properties['Fuel']], 
            properties['Rank'],
            properties['RPS Eligible'],
            [i/1000.0 for i in properties['kg CO2 per MMbtu']], 
        )
    )

    # move the data into the main energy_source_properties table
    execute("""
        DELETE FROM energy_source_properties;
        INSERT INTO energy_source_properties SELECT DISTINCT * FROM t_energy_source_properties;
        DROP TABLE t_energy_source_properties;
    """)

    print "Created energy_source_properties table."

if __name__ == "__main__":
    main()
    con.close()