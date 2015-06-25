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

    print "Start Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    cur = con.cursor()
    query = """CREATE TABLE "central_pv_tracking_hourly_1" (site_id integer, complete_time_stamp timestamp with time zone, capacity_factor real)"""
    cur.execute(query)
    query = """INSERT INTO "central_pv_tracking_hourly_1" (site_id,complete_time_stamp,capacity_factor) SELECT site_id,complete_time_stamp,capacity_factor_panels FROM "tracking_central_cell_pv_hourly_1" """
    cur.execute(query)
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
