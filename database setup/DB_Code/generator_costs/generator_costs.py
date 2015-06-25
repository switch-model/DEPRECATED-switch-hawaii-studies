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
    completeFilePath = "/Volumes/Data/DB_Code/generator_costs/generator_costs.txt"
    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()
    query = """CREATE TABLE "generator_costs"(technologies char(15), min_vintage_year smallint, capital_cost_per_kw real, connect_cost_per_kw_generic real, fixed_o_m real, variable_o_m real, fuel char(15), heat_rate real, max_age_years smallint, forced_outage_rate real, scheduled_outage_rate real, intermittent smallint, resource_limited smallint)"""
    cur.execute(query)
    f = open(completeFilePath, 'r')
    query = """COPY "generator_costs"(technologies,min_vintage_year,capital_cost_per_kw,connect_cost_per_kw_generic,fixed_o_m,variable_o_m,fuel,heat_rate,max_age_years,forced_outage_rate,scheduled_outage_rate,intermittent,resource_limited) FROM '%s' WITH DELIMITER AS ','""" %completeFilePath
    cur.copy_expert(query, f)
    if f:
        f.close()
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
