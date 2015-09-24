#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import os
import psycopg2
import sys

con = None
cur = None
f = None

def execute(query):
    print query
    cur.execute(query)
    con.commit()

# TODO: find the code that created the DistPV_flat (flat roofs) and DistPV_peak (peaked roofs) capacity factors
# in our original database (as of August 2015). That is all missing, but the DistPV found in the backup from 
# July 2014 matches DistPV_peak in the database, once the code from AppendData.py is applied to it (derating
# capacity factor due to various losses.)

# TODO: clean up this code and the DistPV code (when you find it), e.g., maybe cap capacity factors at 1.0 after
# accounting for losses instead of before.

# TODO: change the long list of updates below to be more efficient somehow.
# Every update is done via a delete and insert, so they are very expensive.
# One improvement would be to batch together updates that don't depend on each other.
# Another option may be to use a "with" clause to assemble the values in advance 
# (doesn't really seem to add much though.)
# Or do all the updates in a temporary table and then insert from there into cap_factor?
# (maybe the best idea)
# see http://dba.stackexchange.com/questions/41059/optimizing-bulk-update-performance-in-postgresql for some ideas.
# Another option might be to read all the data out into python (maybe a numpy array), 
# calculate row-by-row (or vectorized in numpy) and then insert the data back into postgresql
# (maybe in one giant insert statement.)
# This query works with 12.8 million rows, so it wouldn't need more than a few hundred MB to 
# represent everything in RAM.

try:
    ################   CHANGE THESE PARAMETERS ONLY   ################
    con = psycopg2.connect(database='switch', host='redr.eng.hawaii.edu')
    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()
    print "Start Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")    

    execute("""
        CREATE TABLE tracking_central_cell_pv_hourly (
            site_id integer, grid_id char, i smallint, j smallint, 
            date_time timestamp with time zone, doy smallint, hour smallint, 
            sunrise_sunset_time real, 
            longitude real, phi_angle real, 
            del_angle real, omg_angle real, z_angle real, cos_z real, 
            cos_i real, dni_cos_z real, 
            diffused real, ghi real, i0 real, kt real,
            tracking_radiation_troughs real, tracking_radiation_panels real, 
            capacity_factor_troughs real, capacity_factor_panels real
        );
    """)

    # NOTE: On 2015-01-01 MF changed this code:
    # (date_part('month',"hourly_average".complete_time_stamp)-1)*30
    #   +date_part('doy',"hourly_average".complete_time_stamp)
    # to this code (note "doy", not "day"):
    # date_part('doy',"hourly_average".complete_time_stamp)
    # this simplifies the code and should eliminate some minor mis-synchronization within the year
    execute("""
       INSERT INTO "tracking_central_cell_pv_hourly" 
         (site_id,grid_id,i,j,date_time,doy,hour,del_angle,ghi) 
       SELECT "cell_central_pv_capacity".site_id,
         "hourly_average".grid_id,
         "hourly_average".i,"hourly_average".j,
         "hourly_average".complete_time_stamp,
         date_part('doy',"hourly_average".complete_time_stamp),
         date_part('hour',"hourly_average".complete_time_stamp),
         23.45*sin(2*pi()*(date_part('doy',"hourly_average".complete_time_stamp)-81)/365),
         "hourly_average".dswrf 
         FROM "hourly_average" INNER JOIN "cell_central_pv_capacity" USING (grid_id, i, j)
    """)

    execute("""
        UPDATE "tracking_central_cell_pv_hourly"
        SET phi_angle = "cell".lat, longitude = "cell".lon
        FROM "cell" 
        WHERE "tracking_central_cell_pv_hourly".i="cell".i AND "tracking_central_cell_pv_hourly".j="cell".j 
    """)

    execute("""
        UPDATE "tracking_central_cell_pv_hourly" 
        SET sunrise_sunset_time = 
            CASE 
                WHEN hour < 12
                THEN 12*abs(acos(abs(tan(phi_angle*pi()/180)*tan(del_angle*pi()/180))))/pi() 
                ELSE 12 + 12*abs(acos(abs(tan(phi_angle*pi()/180)*tan(del_angle*pi()/180))))/pi()
            END + (15*EXTRACT(timezone from date_time)/3600 - longitude)/15
    """)

    # Find the solar hour angle at the middle of each hour, or at the middle of the sunlit period
    # if the hour contains has a sunrise or sunset in the middle.
    # note: omega is zero when the sun is due south
    execute("""
        UPDATE "tracking_central_cell_pv_hourly" 
        SET omg_angle = longitude-15*EXTRACT(timezone from date_time)/3600 + 15.0 * (-12.0 +
        CASE
            WHEN 
                hour < 12 
                AND sunrise_sunset_time > hour
                AND sunrise_sunset_time < hour + 1 
            THEN (sunrise_sunset_time + hour + 1) / 2
            WHEN 
                hour >= 12
                AND sunrise_sunset_time > hour
                AND sunrise_sunset_time < hour + 1
            THEN (sunrise_sunset_time + hour) / 2
            ELSE hour+0.5
        END)
    """)

    query = """UPDATE "tracking_central_cell_pv_hourly" SET cos_z = cos(pi()*phi_angle/180)*cos(pi()*del_angle/180)*cos(pi()*omg_angle/180) + sin(pi()*phi_angle/180)*sin(pi()*del_angle/180)"""
    execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET z_angle = (180*acos(abs(cos_z))/pi())"""
    execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET cos_i = sqrt(cos_z*cos_z + pow(cos(pi()*del_angle/180)*sin(pi()*omg_angle/180),2))"""
    execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET i0 = abs(1367*(1+0.033*cos(2*pi()*doy/365))*cos_z)"""
    execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET kt = CASE WHEN (ghi > 0) THEN (abs(ghi/i0)) ELSE 0 END """
    execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET kt = 1 WHERE kt > 1 """
    execute(query)    
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET diffused = ghi*CASE WHEN (kt <= '0.22') THEN (1-0.09*kt) WHEN (kt > '0.22' AND kt <= '0.8') THEN (0.9511-0.16*kt+4.388*pow(kt,2)-16.638*pow(kt,3)+12.336*pow(kt,4)) ELSE '0.165' END """
    execute(query)    
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET dni_cos_z = ghi - diffused"""
    execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET dni_cos_z = 0 WHERE dni_cos_z < 0 """
    execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET tracking_radiation_troughs = cos_i*dni_cos_z*cos(abs(phi_angle*pi()/180))/(abs(cos_z)+power(10,-10))"""
    execute(query)
    con.commit()
    print "Starting calculation of Capacity Factors"
    query = """UPDATE "tracking_central_cell_pv_hourly" SET tracking_radiation_panels = tracking_radiation_troughs + diffused"""
    execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = tracking_radiation_troughs/1000"""
    execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = 1 WHERE capacity_factor_troughs > 1 """
    execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = 0.896*capacity_factor_troughs"""
    execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = tracking_radiation_panels/1000"""
    execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = 1 WHERE capacity_factor_panels > 1 """
    execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = 0.896*capacity_factor_panels"""
    execute(query)
    con.commit()
    
    # manipulate cap_factor table (slow)
    # execute("""
    #     UPDATE "cap_factor"
    #     SET technology='DistPV_peak', cap_factor = 0.9076*cap_factor
    #     WHERE technology = 'DistPV';
    # """)
    # execute("""
    #     DELETE FROM cap_factor WHERE technology = 'CentralTrackingPV';
    #     INSERT INTO cap_factor (technology, load_zone, site, orientation, date_time, cap_factor)
    #     SELECT 'CentralTrackingPV' as technology, grid_description as load_zone, site_id as site,
    #         'na' as orientation, date_time, capacity_factor_panels as cap_factor
    #     FROM tracking_central_cell_pv_hourly JOIN grid USING (grid_id);
    # """)

    # rebuild cap_factor table and then add indexes, because that's probably faster than inserting/updating
    # (the inserts below each take about two minutes, and each index takes 6-7 mins. The insert above takes several hours.)
    # see http://dba.stackexchange.com/questions/41059/optimizing-bulk-update-performance-in-postgresql for some ideas.
    # NOTE: in the future, it may be better just to drop the indexes, add the CentralTrackingPV data to cap_factor
    # and then recreate the indexes.
    # (you can check times in psql by using the \timing command, then pasting the code below into the window.)
    execute("""
        DROP TABLE IF EXISTS t_cap_factor;
        CREATE TABLE t_cap_factor AS SELECT * FROM cap_factor LIMIT 0;
        INSERT INTO t_cap_factor (technology, load_zone, site, orientation, date_time, cap_factor)
            SELECT CASE WHEN technology = 'DistPV' THEN 'DistPV_peak' ELSE technology END as technology,
                load_zone, site, orientation, date_time, 
                CASE WHEN technology = 'DistPV' THEN 0.9076*cap_factor ELSE cap_factor END AS cap_factor
            FROM cap_factor WHERE technology != 'CentralTrackingPV';
        INSERT INTO t_cap_factor (technology, load_zone, site, orientation, date_time, cap_factor)
            SELECT 'CentralTrackingPV' as technology, grid_description as load_zone, site_id as site,
                'na' as orientation, date_time, capacity_factor_panels as cap_factor
            FROM tracking_central_cell_pv_hourly JOIN grid USING (grid_id);
    """)
    execute("""
        SET maintenance_work_mem = '4GB';
        CREATE UNIQUE INDEX dztos ON t_cap_factor (date_time, load_zone, technology, orientation, site);
        CREATE UNIQUE INDEX ztsod ON t_cap_factor (load_zone, technology, site, orientation, date_time);
        ALTER TABLE t_cap_factor ADD PRIMARY KEY USING INDEX dztos;
    """)
    execute("""
        ALTER TABLE cap_factor RENAME TO cap_factor_old;
        ALTER TABLE t_cap_factor RENAME TO cap_factor;
    """)

    execute("""UPDATE max_capacity SET technology='DistPV_peak' WHERE technology='DistPV';""")

    print "End Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y") 
    
except psycopg2.DatabaseError, e:
    if con:
        con.rollback()
    print 'Error %s' % e    
    sys.exit(1)

except IOError, e:
    if con:
        con.rollback()
    print 'Error %s' % e   
    sys.exit(1)
    
    
finally:
    if con:
        con.close()
