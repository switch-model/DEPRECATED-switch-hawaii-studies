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
    completeFilePath = "/Volumes/Data/DB_Code/SolarCode/gridE_ThiessenRooftop_PV.txt"
    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()
    query = """CREATE TABLE "cell_roofarea_pv_capacity"(grid_id char, i smallint, j smallint, roof_area double precision, net_pv_capacity double precision)"""
    cur.execute(query)
    f = open(completeFilePath, 'r')
    query = """COPY "cell_roofarea_pv_capacity"(grid_id,i,j,roof_area,net_pv_capacity) FROM '%s' WITH DELIMITER AS ','""" %completeFilePath
    cur.copy_expert(query, f)
    if f:
        f.close()
    query = """CREATE TABLE "grid_roofarea_pv_capacity"(grid_id char, roof_area double precision, net_pv_capacity double precision)"""
    cur.execute(query)
    query = """INSERT INTO "grid_roofarea_pv_capacity" SELECT grid_id, sum(roof_area), sum(net_pv_capacity) FROM "cell_roofarea_pv_capacity" GROUP BY 1"""
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
