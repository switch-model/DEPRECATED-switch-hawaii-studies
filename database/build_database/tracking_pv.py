#!/usr/bin/python
# -*- coding: utf-8 -*-

# note: this script can be run piecemeal from iPython/Jupyter, or all-at-once from the command line

import datetime
import numpy as np
from util import execute, executemany
import shared_tables

from k_means import KMeans

# TODO: find the code that created the DistPV_flat (flat roofs) and DistPV_peak (peaked roofs) capacity factors
# in our original database (as of August 2015). That is all missing, but the DistPV found in the backup from 
# July 2014 matches DistPV_peak in the database, once the code from AppendData.py is applied to it (derating
# capacity factor due to various losses.)

# TODO: clean up this code and the DistPV code (when you find it), e.g., maybe cap capacity factors at 1.0 after
# accounting for losses instead of before.

# TODO: change the long list of updates below to be more efficient somehow.
# In postgresql, every update is done via a delete and insert, so they are very expensive.
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


print "Start Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")

# NOTE: this file and script_other_rough.txt are missing the code to create the
# cap_factor, max_capacity and connect_distance_temp tables. This code has been partly
# rewritten near the end of this file, but needs to be finished. (Also see notes about
# connect_distance_temp in script_other_rough.txt)
# TODO: rewrite the code that identifies interconnect locations for each project site
# and calculates the distance between them, and put that in this file (and also in a wind
# processing file). (Both scripts can just go through any records in max_capacity that don't have 
# interconnects or distances and fill them in.)
# TODO: put lat, lon, interconnect IDs, and distances in max_capacity instead of separate 
# temporary tables (are there any situations where a project would have a max_capacity but not
# an interconnect location or vice versa? maybe fossil projects with unlimited capacity, but
# we could add those to the max_capacity table anyway [maybe rename it to "project"])
# TODO: simplify project indexing, to have a unique ID for each project in the project table,
# and use that in the cap_factor table (not zone, technology, site, orientation)

# This code currently treats every cell as a separate solar site (i.e., each cell is added separately
# to max_capacity and cap_factor). In Dec. 2015,
# MF added code to group cells into clusters (project sites), adding a corresponding column
# to cell_central_pv_capacity. That column is used in the scenario_data.py script to aggregate 
# records from max_capacity and cap_factor into larger project sites, but this is a kludge.
# TODO: cluster cells into larger projects and only add the aggregated projects to cap_factor 
# and max_capacity, not the individual cells (i.e., site_id disappears and cluster_id becomes 
# site_id, with aggregated data). This is just waiting for the code that creates
# cap_factor and max_capacity to be rewritten and then for this whole script to be run through.)

########################################
# create central_pv tables
# NOTE: Matthias Fripp moved this code here from "script_other_rough.txt"
# on 2015-12-13, and then added code to cluster projects before reading
# them into cell_central_pv_capacity
execute("""
    DROP TABLE IF EXISTS cell_central_pv_capacity;
    CREATE TABLE cell_central_pv_capacity
    (
        cluster_id int NOT NULL,
        site_id int NOT NULL,
        grid_id character(1) NOT NULL,
        i smallint NOT NULL,
        j smallint NOT NULL,
        central_area double precision,
        net_pv_capacity double precision, 
        CONSTRAINT grid_id_ij_pkey1 PRIMARY KEY (grid_id, i, j)
    )
    WITH (
      OIDS=FALSE
    );
    ALTER TABLE cell_central_pv_capacity OWNER TO admin;
""")

# we have no record of where the original version of cell_central_pv_capacity
# came from (as of summer 2015). 
# An empty table was created in Postgresql Table Creation Scripts/script_other_rough.txt
# and then immediately used, without ever being filled in.
# MF exported the data from the postgres table to cell_central_pv_capacity_original.csv
# on 2015-12-13. We will eventually need to re-create this input file from scratch using
# GIS filters. This table should have central_area = [usable area in square meters].

# read in cell-level data
# table contains site_id, grid_id, i, j, central_area, net_pv_capacity.
with open('cell_central_pv_capacity_original.csv') as csvfile:
    data = list(csv.DictReader(csvfile))
    x, y, area = np.array(list((r["i"], r["j"], r["central_area"]) for r in data), dtype=float).T

# data = csv_to_dict('cell_central_pv_capacity_original.csv')
# i = np.array(data["i"], dtype=float)
# j = np.array(data["j"], dtype=float)
# area = np.array(data["central_area"], dtype=float)

# cluster the cells into 150 projects (somewhat arbitrarily) instead of ~750,
# and use the cluster numbers as new site_id's.
km = KMeans(150, np.c_[x, y], size=0.0001*area)
km.init_centers()
km.find_centers()
# km.plot()
for i in range(len(x)):
    # km.cluster_id is an array of cluster id's, same length as x and y
    data[i]["cluster_id"] = km.cluster_id[i]

# insert the modified data into the database
# note: it is reportedly faster to construct a single 
# insert query with all the values using python's string
# construction operators, since executemany runs numerous 
# separate inserts. However, it's considered more secure to use 
# the database library's template substitution, so we do that.
executemany("""
    INSERT INTO cell_central_pv_capacity
    (cluster_id, site_id, grid_id, i, j, central_area, net_pv_capacity)
    VALUES (
        %(cluster_id)s, %(site_id)s, 
        %(grid_id)s, %(i)s, %(j)s, 
        %(central_area)s, %(net_pv_capacity)s
    )
""", data)

# list(execute("select * from cell_central_pv_capacity order by site_id;"))
# TODO: add an index on cluster_id to use when aggregating clusters.

# note: the code below was moved here from "script_other_rough.txt"
# in December 2015. It has never been run or properly evaluated.
# TODO: make sure the code below makes sense before rerunning it.
execute("""
    DROP TABLE IF EXISTS central_pv_temp;
    CREATE TABLE central_pv_temp AS
        SELECT h.grid_id, h.i, h.j, h.date, h.hour, h.complete_time_stamp, h.dswrf
        FROM cell_central_pv_capacity c JOIN hourly_average h USING (grid_id, i, j);

    UPDATE central_pv_temp SET cp_cell = (dswrf*0.001);

    UPDATE central_pv_temp SET cp_cell_updated = cp_cell;

    UPDATE central_pv_temp SET cp_cell_updated = 1 
    WHERE cp_cell_updated > 1;

    CREATE TABLE central_pv_hourly AS
    SELECT  site_id, complete_time_stamp, cp_cell_updated AS cap_factor
    FROM central_pv_temp ;

    DROP TABLE central_pv_temp;

    CREATE TABLE central_pv AS
    SELECT  A1.site_id, A1.net_pv_capacity as size_MW, T1.interconnect_id
    FROM cell_central_pv_capacity A1, interconnect T1
    WHERE T1.interconnect_id=1;
""")

# done creating central_pv tables (2015-12-13)
########################################

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

# MF moved clustering code from "script_other_rough.txt" to here 2015-12-30.
# note: the code to create max_capacity seems to have been lost, so MF rewrote it 2015-12-30.


# TODO: finish writing code below, including making it aggregate by clusters
shared_tables.create_table("project")
shared_tables.create_table("cap_factor")

# note: code below is not quite right yet
execute("""
    CREATE TABLE cluster_solar_hourly AS
        SELECT 
            c.site_id, h.date_time, 
            SUM(h.capacity_factor_troughs*c.net_pv_capacity)/SUM(c.net_pv_capacity) AS capacity_factor_troughs,
            SUM(h.capacity_factor_panels*c.net_pv_capacity)/SUM(c.net_pv_capacity) AS capacity_factor_panels
        FROM cell_central_pv_capacity c JOIN tracking_central_cell_pv_hourly h USING (grid_id, i, j)
        GROUP BY 1, 2;
""")

# TODO: insert clusters into project table

# TODO: write this function
shared_tables.calculate_interconnect_distances()

# TODO: calculate capacity factors for clusters

# TODO: change code below to call shared_tables.drop_indexes("cap_factor")
# then delete all "CentralTrackingPV" records from cap_factor
# then add new CentralTrackingPV records to cap_factor (with project_id 
# from project table instead of z, t, s, o)
# then call shared_tables.create_indexes("cap_factor")

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


print "End Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y") 
    
