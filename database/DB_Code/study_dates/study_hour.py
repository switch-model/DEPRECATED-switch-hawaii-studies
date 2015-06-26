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

    # set the timezone that we will use to define sample dates (i.e., if we say a sample date corresponds to 7/31/2008, which time zone do we mean?)
    # this should probably be read from some configuration file, since it varies from project to project
    cur.execute("""SET TIME ZONE 'HST'""")

    # make a master table of all historical dates and hours (this should really be moved to the scripts that import system loads or hourly weather data)
    query = """
    DROP TABLE IF EXISTS "date_time";
    CREATE TABLE "date_time" AS (
      SELECT DISTINCT CAST(date_trunc('day', date_time) AS DATE) as date, date_time
        FROM system_load
        ORDER by date_time
      );
    """
    con.commit()

    # note: eventually this may need to allow for shorter intervals instead of rounding hour_of_day to an integer
    query = """
    DROP TABLE IF EXISTS "study_hour";
    CREATE TABLE "study_hour" (study_date int, study_hour int, hour_of_day smallint, date_time timestamp with time zone);
    INSERT INTO "study_hour"
        SELECT s.study_date, 
          s.study_date*100+CAST(EXTRACT(HOUR FROM d.date_time) AS INTEGER) AS study_hour, 
          CAST(EXTRACT(HOUR FROM d.date_time) AS SMALLINT) AS hour_of_day, 
          d.date_time
          FROM study_date s INNER JOIN date_time d USING (date)
          ORDER BY study_date, study_hour;
    """
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
