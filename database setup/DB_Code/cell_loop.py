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
    rootPath = "/Volumes/LaCie/OWITS/"
    filterFileName = "_Georef.csv"
    ################   CHANGE THESE PARAMETERS ONLY   ################
    
    cur = con.cursor()
    query = """CREATE TEMPORARY TABLE "temp"(grid_id char, i smallint, j smallint, lat real, lon real)"""
    cur.execute(query)
    query = """CREATE TABLE "cell"(grid_id char, i smallint, j smallint, lat real, lon real, PRIMARY KEY(grid_id,i,j))"""
    cur.execute(query)
    listing = os.listdir(rootPath)
    for fileName in listing:
        if filterFileName in fileName:
            print "Current file is:" + fileName
            completeFilePath = rootPath + fileName
            f = open(completeFilePath, 'r')
            query = """COPY "temp"(i,j,lat,lon) FROM '%s' WITH DELIMITER AS ',' CSV HEADER""" %completeFilePath
            cur.copy_expert(query, f)
            if f:
                f.close()
            grid_id = fileName.split("_",1)[0]
            print "Current Grid ID is:" + grid_id + ":"
            query = """UPDATE "temp" SET grid_id='%s' WHERE grid_id IS NULL""" %grid_id
            cur.execute(query)
            query = """INSERT INTO cell SELECT * FROM temp"""
            cur.execute(query)
            query = """TRUNCATE temp"""
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
