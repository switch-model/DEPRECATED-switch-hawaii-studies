#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import os
import psycopg2
import sys

con = None
f = None

try:
    ################   CHANGE THESE PARAMETERS ONLY   ################
    con = psycopg2.connect(database='switch', host='localhost', port='5432', user='deepakc_super', password='myPassword')
    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()
    query = """CREATE TABLE "cell_pv_power_hourly" (grid_id char, i smallint, j smallint, complete_time_stamp timestamp with time zone, pv_power double precision, capacity_factor double precision)"""
    cur.execute(query)
    query = """INSERT INTO "cell_pv_power_hourly" (grid_id,i,j,complete_time_stamp,pv_power,capacity_factor) SELECT "hourly_average".grid_id,"hourly_average".i,"hourly_average".j,"hourly_average".complete_time_stamp,"cell_roofarea_pv_capacity".net_pv_capacity*"hourly_average".dswrf/1000,"hourly_average".dswrf/1000 FROM "hourly_average" INNER JOIN "cell_roofarea_pv_capacity" ON "hourly_average".grid_id="cell_roofarea_pv_capacity".grid_id AND "hourly_average".i="cell_roofarea_pv_capacity".i AND "hourly_average".j="cell_roofarea_pv_capacity".j"""
    cur.execute(query)
    query = """UPDATE "cell_pv_power_hourly" SET capacity_factor = '1' WHERE capacity_factor > '1'"""
    cur.execute(query)
    query = """CREATE TABLE "grid_pv_power_hourly"(grid_id char, complete_time_stamp timestamp with time zone, pv_power double precision, capacity_factor double precision)"""
    cur.execute(query)
    query = """INSERT INTO "grid_pv_power_hourly" (grid_id,complete_time_stamp,pv_power) SELECT grid_id,complete_time_stamp,sum(pv_power) FROM "cell_pv_power_hourly" GROUP BY 1,2"""
    cur.execute(query)
    query = """UPDATE "grid_pv_power_hourly" SET capacity_factor = (pv_power/"grid_roofarea_pv_capacity".net_pv_capacity) FROM "grid_roofarea_pv_capacity" WHERE "grid_pv_power_hourly".grid_id = "grid_roofarea_pv_capacity".grid_id"""
    cur.execute(query)
    query = """UPDATE "grid_pv_power_hourly" SET capacity_factor = '1' WHERE capacity_factor > '1'"""
    cur.execute(query)
    print "Start Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    con.commit()
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
