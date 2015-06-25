#!/usr/bin/python
# -*- coding: utf-8 -*-

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
    query = """SET TIME ZONE 'UTC'"""
    cur.execute(query)  
    query = """ALTER TABLE hourly_average ADD complete_time_stamp timestamp with time zone"""
    cur.execute(query)
    query = """UPDATE hourly_average SET complete_time_stamp = to_timestamp(date || to_char(hour::real,'FM99'),'YYYYMMDDHH24')"""
    cur.execute(query)
    con.commit()
    
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
    if f:
        f.close()
