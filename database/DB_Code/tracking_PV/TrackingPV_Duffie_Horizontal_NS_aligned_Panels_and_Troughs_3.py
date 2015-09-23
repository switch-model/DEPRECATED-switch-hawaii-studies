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
    con = psycopg2.connect(database='switch', host='redr.eng.hawaii.edu')
    ################   CHANGE THESE PARAMETERS ONLY   ################

    cur = con.cursor()
    print "Start Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")    
    query = """CREATE TABLE "tracking_central_cell_pv_hourly" 
        (site_id integer, grid_id char, i smallint, j smallint, complete_time_stamp timestamp with time zone, 
         doy smallint, hour smallint, phi_angle real, del_angle real, omg_angle real, z_angle real, cos_z real, 
         cos_i real, dni_cos_z real, diffused real, tracking_radiation_troughs real, tracking_radiation_panels real, 
         capacity_factor_troughs real, capacity_factor_panels real, ghi real, i0 real, 
         theoretical_sunrise_sunset_time real, kt real, PRIMARY KEY (site_id, grid_id, i, j, complete_time_stamp))"""
    cur.execute(query)
    con.commit()
    # NOTE: On 2015-01-01 MF changed this code:
    # (date_part('month',"hourly_average".complete_time_stamp)-1)*30
    #   +date_part('doy',"hourly_average".complete_time_stamp)
    # to this code (note "doy", not "day"):
    # date_part('doy',"hourly_average".complete_time_stamp)
    # this simplifies the code and should eliminate some minor mis-synchronization within the year
    query = """
       INSERT INTO "tracking_central_cell_pv_hourly" 
         (site_id,grid_id,i,j,complete_time_stamp,doy,hour,del_angle,ghi) 
       SELECT "cell_central_pv_capacity".site_id,
         "hourly_average".grid_id,
         "hourly_average".i,"hourly_average".j,
         "hourly_average".complete_time_stamp,
         date_part('doy',"hourly_average".complete_time_stamp),
         date_part('hour',"hourly_average".complete_time_stamp),
         23.45*sin(2*pi()*(date_part('doy',"hourly_average".complete_time_stamp)-81)/365),
         "hourly_average".dswrf 
         FROM "hourly_average" INNER JOIN "cell_central_pv_capacity" 
           ON "hourly_average".grid_id="cell_central_pv_capacity".grid_id 
             AND "hourly_average".i="cell_central_pv_capacity".i 
             AND "hourly_average".j="cell_central_pv_capacity".j
    """
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET (phi_angle) = ("cell".lat) FROM "cell" WHERE "tracking_central_cell_pv_hourly".i="cell".i AND "tracking_central_cell_pv_hourly".j="cell".j """
    cur.execute(query)  
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET theoretical_sunrise_sunset_time = CASE WHEN (hour < 12) THEN (12*abs(acos(abs(tan(phi_angle*pi()/180)*tan(del_angle*pi()/180))))/pi()) ELSE (12 + 12*abs(acos(abs(tan(phi_angle*pi()/180)*tan(del_angle*pi()/180))))/pi()) END"""
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET omg_angle = CASE WHEN (((hour<12) AND ((hour-theoretical_sunrise_sunset_time)<1) AND ((hour-theoretical_sunrise_sunset_time)>0)) OR ((hour>12) AND ((theoretical_sunrise_sunset_time-hour)<1) AND ((theoretical_sunrise_sunset_time-hour)>0))) THEN (15*((hour+theoretical_sunrise_sunset_time)/2-12)) ELSE (15*(hour-12+0.5)) END"""
    cur.execute(query)    
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET cos_z = cos(pi()*phi_angle/180)*cos(pi()*del_angle/180)*cos(pi()*omg_angle/180) + sin(pi()*phi_angle/180)*sin(pi()*del_angle/180)"""
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET z_angle = (180*acos(abs(cos_z))/pi())"""
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET cos_i = sqrt(cos_z*cos_z + pow(cos(pi()*del_angle/180)*sin(pi()*omg_angle/180),2))"""
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET i0 = abs(1367*(1+0.033*cos(2*pi()*doy/365))*cos_z)"""
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET kt = CASE WHEN (ghi > '0') THEN (abs(ghi/i0)) ELSE '0' END """
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET kt = '1' WHERE kt > '1' """
    cur.execute(query)    
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET diffused = ghi*CASE WHEN (kt <= '0.22') THEN (1-0.09*kt) WHEN (kt > '0.22' AND kt <= '0.8') THEN (0.9511-0.16*kt+4.388*pow(kt,2)-16.638*pow(kt,3)+12.336*pow(kt,4)) ELSE '0.165' END """
    cur.execute(query)    
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET dni_cos_z = ghi - diffused"""
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET dni_cos_z = '0' WHERE dni_cos_z < '0' """
    cur.execute(query)
    con.commit()
    query = """UPDATE "tracking_central_cell_pv_hourly" SET tracking_radiation_troughs = cos_i*dni_cos_z*cos(abs(phi_angle*pi()/180))/(abs(cos_z)+power(10,-10))"""
    cur.execute(query)
    con.commit()
    print "Starting calculation of Capacity Factors"
    query = """UPDATE "tracking_central_cell_pv_hourly" SET tracking_radiation_panels = tracking_radiation_troughs + diffused"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = tracking_radiation_troughs/1000"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = '1' WHERE capacity_factor_troughs > '1' """
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = 0.896*capacity_factor_troughs"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = tracking_radiation_panels/1000"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = '1' WHERE capacity_factor_panels > '1' """
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = 0.896*capacity_factor_panels"""
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
