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
    rootPath = "/Volumes/Data/DB_Code/grids/"
    fileName = "grids.csv"
    ################   CHANGE THESE PARAMETERS ONLY   ################
    
    cur = con.cursor()
    query = """CREATE TABLE "grid"(grid_id char primary key, grid_description text)"""
    cur.execute(query)
    completeFilePath = rootPath + fileName
    f = open(completeFilePath, 'r')
    query = """COPY "grid"(grid_id, grid_description) FROM '%s' WITH DELIMITER AS ',' CSV HEADER""" %completeFilePath
    cur.copy_expert(query, f)
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
