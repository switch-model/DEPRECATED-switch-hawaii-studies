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
    AnalysisFile = "AllVintageYear.txt"
    TrackingPVFile = "TrackingPV.txt"
    WindFile = "Wind.txt"
    step_TrackingPV = 0.1
    step_Wind = 0.1
    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()  
    print "Start Time:" + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    f = open(AnalysisFile, 'r')
    f1 = open(TrackingPVFile, 'w')
    f2 = open(WindFile, 'w')
    for line in f:
        if line.find(":=") == -1:
            words = line.split()
            if words[2] != "0":
                int_TrackingPV = 0.0
                f1.write(words[0] + ";")
                site_id = words[0];
                while int_TrackingPV < 1:
                    query = """SELECT avg(cap_factor),stddev(cap_factor) FROM "cap_factor" WHERE technology='CentralTrackingPV' AND site='%s' AND cap_factor>'%s' AND cap_factor<='%s' """ %(site_id,str(int_TrackingPV),str(int_TrackingPV+step_TrackingPV))
                    cur.execute(query)
                    rows = cur.fetchall()
                    for row in rows:
                        if row[0] == None:
                            avg = 0
                        else:
                            avg = row[0]
                        if row[1] == None:
                            std = 0
                        else:
                            std = row[1]
                    f1.write("Site_ID="+site_id+";  Interval="+str(int_TrackingPV)+" to "+str(int_TrackingPV+step_TrackingPV)+";  Avg="+str(avg)+";  Std="+str(std))
                    int_TrackingPV += step_TrackingPV
            if words[4] != "0":
                int_Wind = 0.0
                f2.write(words[0] + ";")
                site_id = words[0];
                while int_Wind < 1:
                    query = """SELECT avg(cap_factor),stddev(cap_factor) FROM "cap_factor" WHERE technology='Wind' AND site='%s' AND cap_factor>'%s' AND cap_factor<='%s' """ %(site_id,str(int_Wind),str(int_TrackingPV+step_Wind))
                    cur.execute(query)
                    rows = cur.fetchall()
                    for row in rows:
                        if row[0] == None:
                            avg = 0
                        else:
                            avg = row[0]
                        if row[1] == None:
                            std = 0
                        else:
                            std = row[1]
                    f2.write("Site_ID="+site_id+";  Interval="+str(int_Wind)+" to "+str(int_Wind+step_Wind)+";  Avg="+str(avg)+";  Std="+str(std))
                    int_Wind += step_Wind
    if f2:
        f2.close()
    if f1:
        f1.close()
    if f:
        f.close()
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
