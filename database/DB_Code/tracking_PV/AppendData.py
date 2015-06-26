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
    con = psycopg2.connect(database='switch', host='switch.eng.hawaii.edu', port='5432', user='deepakc_super', password='myPassword')
    ################   CHANGE THESE PARAMETERS ONLY   ################

    print "Start Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    cur = con.cursor()
    query = """UPDATE "tracking_central_cell_pv_hourly_1" SET capacity_factor_troughs = 0.896*capacity_factor_troughs"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly_1" SET capacity_factor_panels = 0.896*capacity_factor_panels"""
    cur.execute(query)
    query = """UPDATE "central_pv_tracking_hourly_1" SET capacity_factor = 0.896*capacity_factor"""
    cur.execute(query)
    query = """UPDATE "cap_factor" SET cap_factor = 0.896*cap_factor WHERE technology = 'CentralTrackingPV' """
    cur.execute(query)
    query = """UPDATE "cap_factor" SET cap_factor = 0.9076*cap_factor WHERE technology = 'DistPV' """
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
