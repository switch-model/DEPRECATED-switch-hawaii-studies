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
    print "Start Time: " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")    
    query = """CREATE TABLE "tracking_central_cell_pv_hourly" (site_id integer, grid_id char, i smallint, j smallint, complete_time_stamp timestamp with time zone, doy smallint, phi_angle real, del_angle real, omg_angle real, z_angle real, cos_z real, cos_i real, dni_cos_z real, diffused real, tracking_radiation_troughs real, tracking_radiation_panels real, capacity_factor_troughs real, capacity_factor_panels real, ghi real, i0 real, kt real)"""
    cur.execute(query)
    query = """INSERT INTO "tracking_central_cell_pv_hourly" (site_id,grid_id,i,j,complete_time_stamp,doy,del_angle,omg_angle,ghi) SELECT "cell_central_pv_capacity".site_id,"hourly_average".grid_id,"hourly_average".i,"hourly_average".j,"hourly_average".complete_time_stamp,(date_part('month',"hourly_average".complete_time_stamp)-1)*30+date_part('day',"hourly_average".complete_time_stamp),23.45*sin(2*pi()*((date_part('month',"hourly_average".complete_time_stamp)-1)*30+date_part('day',"hourly_average".complete_time_stamp)-81)/365),15*(date_part('hour',"hourly_average".complete_time_stamp)-12),"hourly_average".dswrf FROM "hourly_average" INNER JOIN "cell_central_pv_capacity" ON "hourly_average".grid_id="cell_central_pv_capacity".grid_id AND "hourly_average".i="cell_central_pv_capacity".i AND "hourly_average".j="cell_central_pv_capacity".j"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET (phi_angle) = ("cell".lat) FROM "cell" WHERE "tracking_central_cell_pv_hourly".i="cell".i AND "tracking_central_cell_pv_hourly".j="cell".j """
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET cos_z = cos(pi()*phi_angle/180)*cos(pi()*del_angle/180)*cos(pi()*omg_angle/180) + sin(pi()*phi_angle/180)*sin(pi()*del_angle/180)"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET z_angle = (180*acos(abs(cos_z))/pi())"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET cos_i = sqrt(cos_z*cos_z + pow(cos(pi()*del_angle/180)*sin(pi()*omg_angle/180),2))"""
    cur.execute(query)     
    query = """UPDATE "tracking_central_cell_pv_hourly" SET i0 = abs(1367*(1+0.033*cos(2*pi()*doy/365))*cos_z) """
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET kt = CASE WHEN (i0 > '0') THEN (ghi/i0) ELSE '0' END """
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET kt = '1' WHERE kt > '1' """
    cur.execute(query)    
    query = """UPDATE "tracking_central_cell_pv_hourly" SET diffused = ghi*CASE WHEN (kt <= '0.22') THEN (1-0.09*kt) WHEN (kt > '0.22' AND kt <= '0.8') THEN (0.9511-0.16*kt+4.388*pow(kt,2)-16.638*pow(kt,3)+12.336*pow(kt,4)) ELSE '0.165' END """
    cur.execute(query)    
    query = """UPDATE "tracking_central_cell_pv_hourly" SET dni_cos_z = ghi - diffused"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET dni_cos_z = '0' WHERE dni_cos_z < '0' """
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET tracking_radiation_troughs = cos_i*dni_cos_z*cos(abs(phi_angle*pi()/180))/(abs(cos_z)+power(10,-10))"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET tracking_radiation_panels = tracking_radiation_troughs + diffused"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = tracking_radiation_troughs/1000"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = '1' WHERE capacity_factor_troughs > '1'"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_troughs = 0.896*capacity_factor_troughs"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = tracking_radiation_panels/1000"""
    cur.execute(query)
    query = """UPDATE "tracking_central_cell_pv_hourly" SET capacity_factor_panels = '1' WHERE capacity_factor_panels > '1'"""
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
