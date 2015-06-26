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
    query = """CREATE TABLE "connect_cost" (load_zone text, technology text, site integer, orientation text, connect_length_km real, connect_cost_per_kw real)"""
    cur.execute(query)
    query = """INSERT INTO "connect_cost" (load_zone,technology,site,orientation) SELECT load_zone,technology,site,orientation FROM "max_capacity" """
    cur.execute(query)
    query = """UPDATE "connect_cost" SET connect_length_km = '0' """
    cur.execute(query)
    query = """UPDATE "connect_cost" SET connect_cost_per_kw = '0' """
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
