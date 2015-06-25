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
    rootPath = "/Volumes/LaCie/OWITS_DATA/"
    filterFileName = ".G.txt"
    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()
    query = """SET TIME ZONE 'UTC'"""
    cur.execute(query)    
    query = """CREATE TEMPORARY TABLE "temp_tenminutely_average"(grid_id char, i smallint, j smallint, date char(8), time char(4), time_stamp timestamp with time zone, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real)"""
    cur.execute(query)
    #query = """CREATE TABLE "tenminutely_average"(grid_id char, i smallint, j smallint, date char(8), time char(4), time_stamp timestamp with time zone, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real, PRIMARY KEY (grid_id, i, j, date, time))"""
    #cur.execute(query)
    query = """CREATE TEMPORARY TABLE "temp_hourly_average"(grid_id char, i smallint, j smallint, date char(8), hour real, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real)"""
    cur.execute(query)
    #query = """CREATE TABLE "hourly_average"(grid_id char, i smallint, j smallint, date char(8), hour real, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real, PRIMARY KEY (grid_id, i, j, date, hour))"""
    #cur.execute(query)
    query = """CREATE TEMPORARY TABLE "temp_daily_average"(grid_id char, i smallint, j smallint, date char(8), tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real)"""
    cur.execute(query)
    #query = """CREATE TABLE "daily_average"(grid_id char, i smallint, j smallint, date char(8), tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real, PRIMARY KEY (grid_id, i, j, date))"""
    #cur.execute(query)
    query = """CREATE TEMPORARY TABLE "temp_monthly_average"(grid_id char, i smallint, j smallint, year_month real, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real)"""
    cur.execute(query)
    #query = """CREATE TABLE "monthly_average"(grid_id char, i smallint, j smallint, year_month real, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real, PRIMARY KEY (grid_id, i, j, year_month))"""
    #cur.execute(query)
    query = """CREATE TEMPORARY TABLE "temp_annual_average"(grid_id char, i smallint, j smallint, year real, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real)"""
    cur.execute(query)
    #query = """CREATE TABLE "annual_average"(grid_id char, i smallint, j smallint, year real, tsfc real, psfc real, pcp real, q2m real, dswrf real, dlwrf real, t10 real, s10 real, w10 real, t50 real, s50 real, w50 real, t80 real, s80 real, w80 real, t100 real, s100 real, w100 real, t200 real, s200 real, w200 real, PRIMARY KEY (grid_id, i, j, year))"""
    #cur.execute(query)
    con.commit()
    folderListing = os.listdir(rootPath)
    print "Start Time:" + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    for folderName in folderListing:
        print "Current folder is:" + folderName + ":"
        completeFolderPath = rootPath + folderName
        fileListing = os.listdir(completeFolderPath)
        for fileName in fileListing:
            if filterFileName in fileName:
                latlon = fileName.split(".",1)[0]
                lat = latlon.split("_",1)[0]
                lon = latlon.split("_",1)[1]
                if ((int(lat)==182 and int(lon)>81) or (int(lat)>182)):
                    print "Current file is:" + fileName + ":"
                    completeFilePath = completeFolderPath + "/" + fileName
                    f = open(completeFilePath, 'r')
                    query = """COPY "temp_tenminutely_average"(date,time,tsfc,psfc,pcp,q2m,dswrf,dlwrf,t10,s10,w10,t50,s50,w50,t80,s80,w80,t100,s100,w100,t200,s200,w200) FROM '%s' WITH DELIMITER AS ','""" %completeFilePath
                    cur.copy_expert(query, f)
                    if f:
                        f.close()
                    grid_id = folderName
                    query = """UPDATE "temp_tenminutely_average" SET (grid_id,i,j,time_stamp)=('%s','%s','%s',to_timestamp(date || time, 'YYYYMMDDHH24MI')) WHERE i IS NULL AND j IS NULL""" %(grid_id,lat,lon)
                    cur.execute(query)
                    #query = """INSERT INTO tenminutely_average SELECT * FROM temp_tenminutely_average"""
                    #cur.execute(query)
                    query = """INSERT INTO temp_hourly_average SELECT grid_id, i, j, date, floor(to_number(time,'9999')/100) "hour", avg(tsfc) "tsfc", avg(psfc) "psfc", avg(pcp) "pcp", avg(q2m) "q2m", avg(dswrf) "dswrf", avg(dlwrf) "dlwrf", avg(t10) "t10", avg(s10) "s10", avg(w10) "w10", avg(t50) "t50", avg(s50) "s50", avg(w50) "w50", avg(t80) "t80", avg(s80) "s80", avg(w80) "w80", avg(t100) "t100", avg(s100) "s100", avg(w100) "w100", avg(t200) "t200", avg(s200) "s200", avg(w200) "w200" FROM "temp_tenminutely_average" GROUP BY 1,2,3,4,5"""
                    cur.execute(query)
                    query = """INSERT INTO hourly_average SELECT * FROM temp_hourly_average"""
                    cur.execute(query)
                    query = """INSERT INTO temp_daily_average SELECT grid_id, i, j, date, avg(tsfc) "tsfc", avg(psfc) "psfc", avg(pcp) "pcp", avg(q2m) "q2m", avg(dswrf) "dswrf", avg(dlwrf) "dlwrf", avg(t10) "t10", avg(s10) "s10", avg(w10) "w10", avg(t50) "t50", avg(s50) "s50", avg(w50) "w50", avg(t80) "t80", avg(s80) "s80", avg(w80) "w80", avg(t100) "t100", avg(s100) "s100", avg(w100) "w100", avg(t200) "t200", avg(s200) "s200", avg(w200) "w200" FROM "temp_hourly_average" GROUP BY 1,2,3,4"""
                    cur.execute(query)
                    query = """INSERT INTO daily_average SELECT * FROM temp_daily_average"""
                    cur.execute(query)
                    query = """INSERT INTO temp_monthly_average SELECT grid_id, i, j, floor(to_number(date,'99999999')/100) "year_month", avg(tsfc) "tsfc", avg(psfc) "psfc", avg(pcp) "pcp", avg(q2m) "q2m", avg(dswrf) "dswrf", avg(dlwrf) "dlwrf", avg(t10) "t10", avg(s10) "s10", avg(w10) "w10", avg(t50) "t50", avg(s50) "s50", avg(w50) "w50", avg(t80) "t80", avg(s80) "s80", avg(w80) "w80", avg(t100) "t100", avg(s100) "s100", avg(w100) "w100", avg(t200) "t200", avg(s200) "s200", avg(w200) "w200" FROM "temp_daily_average" GROUP BY 1,2,3,4"""
                    cur.execute(query)
                    query = """INSERT INTO monthly_average SELECT * FROM temp_monthly_average"""
                    cur.execute(query)
                    query = """INSERT INTO temp_annual_average SELECT grid_id, i, j, floor(year_month/100) "year", avg(tsfc) "tsfc", avg(psfc) "psfc", avg(pcp) "pcp", avg(q2m) "q2m", avg(dswrf) "dswrf", avg(dlwrf) "dlwrf", avg(t10) "t10", avg(s10) "s10", avg(w10) "w10", avg(t50) "t50", avg(s50) "s50", avg(w50) "w50", avg(t80) "t80", avg(s80) "s80", avg(w80) "w80", avg(t100) "t100", avg(s100) "s100", avg(w100) "w100", avg(t200) "t200", avg(s200) "s200", avg(w200) "w200" FROM "temp_monthly_average" GROUP BY 1,2,3,4"""
                    cur.execute(query)                
                    query = """INSERT INTO annual_average SELECT * FROM temp_annual_average"""
                    cur.execute(query)
                    con.commit()
                    query = """TRUNCATE temp_tenminutely_average"""
                    cur.execute(query)
                    query = """TRUNCATE temp_hourly_average"""
                    cur.execute(query)
                    query = """TRUNCATE temp_daily_average"""
                    cur.execute(query)
                    query = """TRUNCATE temp_monthly_average"""
                    cur.execute(query)
                    query = """TRUNCATE temp_annual_average""";
                    cur.execute(query)
                    con.commit()
        print "Completed Folder " + folderName + " at Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
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
