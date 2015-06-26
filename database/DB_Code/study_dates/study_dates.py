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
    con = con = psycopg2.connect(database='switch', host='localhost', port='5432', user='deepakc_super', password='myPassword')
    completeFilePath = "/Volumes/Data/DB_Code/study_dates/study_dates.txt"

    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()

    cur.execute("""DROP TABLE IF EXISTS study_date""")

    # note: study_date is an integer identifying a particular date in the study; 'date' is a date value corresponding to a specific historical date
    # also note: in this case, 'date' is meant to refer to a date in the local timezone 
    query = """CREATE TABLE "study_date"(period smallint, study_date int, month_of_year smallint, date date, hours_in_sample smallint)"""
    cur.execute(query)

    # note: eventually the date sampling logic should be moved into this script (possibly using some minimal parameters set externally by the user)
    # but for now we import a pre-written list of date samples
    f = open(completeFilePath, 'r')
    query = """COPY "study_date"(period,study_date,month_of_year,date,hours_in_sample) FROM '%s' WITH DELIMITER AS ',' NULL '' """ %completeFilePath
    cur.copy_expert(query, f)
    if f:
        f.close()

    # in future, this should include a sequence number that increments for all the different sample dates that occur in the same month and same period.
    # for now we just use 1
    query = """UPDATE "study_date" SET study_date = (period * 100 + month_of_year) * 100 + 1 """
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
        
