#!/usr/bin/python
# -*- coding: utf-8 -*-

# sample SAM/NSRDB code available here:
# https://sam.nrel.gov/samples
# https://developer.nrel.gov/docs/solar/pvwatts-v5/
# https://nsrdb.nrel.gov/api-instructions
# https://sam.nrel.gov/sdk

# note: this script can be run piecemeal from iPython/Jupyter, or all-at-once from the command line

# NOTE: this uses pandas DataFrames for most calculations, and breaks the work into batches
# to avoid exceeding available memory (e.g., do one load zone worth of projects at a time,
# then calculate one grid cell at a time and add it to the relevant projects). However, this
# makes the code complex and the logic unclear, so it would probably be better to use a database,
# where everything can be calculated at once in one query. (e.g. get a list of grid cells for all
# projects from the database, then calculate cap factor for each grid cell and store it incrementally
# in a cell cap factor table, then run one query which joins project -> project cell -> cell to
# get hourly cap factors for all projects. This could use temporary tables for the cells, which
# are then discarded.

# NOTE: this stores all the hourly capacity factors in the postgresql database. That makes it
# difficult to share with others. An alternative would be to store a separate text file for each
# technology for each day and sync those via github. Disadvantages of that: querying is more complex
# and we have to specify a reference time zone before saving the data (day boundaries are time zone
# specific). Alternative: store in postgresql and publish a dump of the database.

from __future__ import print_function, division
import os, re, sys, struct, ctypes, datetime
import numpy as np
import pandas as pd
import dateutil.tz     # should be available, since pandas uses it
import sqlalchemy

from util import execute, executemany, switch_db, switch_host
import shared_tables

# number of digits that latitude and longitude should be rounded to before matching
# to the nsrdb files
lat_lon_digits = 2
# location of main database directory relative to this script file
database_rel_dir = '..'
# location of nsrdb hourly data files relative to the main database directory
# all subdirectories of this one will be scanned for data files
nsrdb_dir = 'NSRDB Hourly Irradiance Data'
# pattern to match lat and lon in nsrdb file name (all matching files will
# be read for that site, e.g., for multiple years); this should specify
# named groups for at least 'lat' and 'lon'.
# note: we don't try too hard to match an exact pattern of digits and symbols
# (just use .* for each group). If the expressions can't be parsed, we let them
# generate errors later.
nsrdb_file_regex = re.compile(r'^(?P<stn>.*)_(?P<lat>.*)_(?P<lon>.*)_(?P<year>.*)[.]csv$')
# location of System Advisor Model SDK relative to this script file
sam_sdk_rel_dir = 'System Advisor Model'

# load zone for which data is being prepared
# TODO: add load zone to cluster input file
load_zone = 'Oahu'

# tuple of technology name and array_type for pvwatts
# note: Appendix F of 2016-04-01 PSIP uses 2 for tracking,
# but 3 (backtracking) seems like a better choice
central_solar_techs = pd.DataFrame(dict(
    technology=['CentralFixedPV', 'CentralTrackingPV'],
    array_type=[0, 3],
    acres_per_mw=[7.6, 8.7],   # for projects < 20 MW from p. v of http://www.nrel.gov/docs/fy13osti/56290.pdf
))

# index the central_solar_techs and derive some useful values
central_solar_techs.set_index('technology', inplace=True)
# 1 / [(m2/acre) * (acre/mw)] 
central_solar_techs['mw_per_m2'] = (1.0 / (4046.86 * central_solar_techs['acres_per_mw']))

# find the database directory and System Advisor Model
try:
    curdir = os.path.dirname(__file__)
except NameError:
    # no __file__ variable; we're copying and pasting in an interactive session
    curdir = os.getcwd()
    pd.set_option('display.width', 200)

database_dir = os.path.normpath(os.path.join(curdir, database_rel_dir))
if not os.path.exists(database_dir):
    raise RuntimeError("Unable to find database directory at " + database_dir)
sam_sdk_dir = os.path.normpath(os.path.join(curdir, sam_sdk_rel_dir))
if not os.path.exists(sam_sdk_dir):
    raise RuntimeError("Unable to find System Advisor Model (SAM) SDK directory at " + sam_sdk_dir)

# Load the System Advisor Model (SAM) SDK API
# Note: SAM SDK can be downloaded from https://sam.nrel.gov/sdk
# nsrdb/sam code is based on examples in sscapi.py itself
# Also see https://nsrdb.nrel.gov/api-instructions and sam-sdk/ssc_guide.pdf

# preload ssc library, so sscapi won't fail if it's not in the library search path
if sys.platform == 'win32' or sys.platform == 'cygwin':
    if 8 * struct.calcsize("P") == 64:
        path = ['win64', 'ssc.dll']
    else:
        path = ['win32', 'ssc.dll']
elif sys.platform == 'darwin':
    path = ['osx64', 'ssc.dylib']
elif sys.platform == 'linux2':
    path = ['linux64', 'ssc.so']
else:
    raise RuntimeError('Unsupported operating system: {}'.format(sys.platform))
ssc_dll = ctypes.CDLL(os.path.join(sam_sdk_dir, *path))

# add search path to sscapi.py
sys.path.append(os.path.join(sam_sdk_dir, 'languages', 'python'))
import sscapi
ssc = sscapi.PySSC()
pvwatts5 = ssc.module_create("pvwattsv5")
ssc.module_exec_set_print(0)

# setup database
db_engine = sqlalchemy.create_engine('postgresql://' + switch_host + '/' + switch_db)

def main():
    tracking_pv()
    distributed_pv()

def tracking_pv():
    # make a list of all available NSRDB data files
    nsrdb_file_dict, years = get_nsrdb_file_dict()
    cluster_cell = pd.DataFrame.from_csv(
        db_path('GIS/Utility-Scale Solar Sites/solar_cluster_nsrdb_grid_renamed.csv'),
        index_col='gridclstid'
    )
    cluster_cell = cluster_cell[cluster_cell['solar_covg']>0]
    cell = cluster_cell.groupby('nsrdb_id')
    cluster = cluster_cell.groupby('cluster_id')
    cluster_total_solar_area = cluster['solar_area'].sum()

    cluster_ids = cluster.groups.keys()             # list of all cluster ids, for convenience
    cluster_id_digits = len(str(max(cluster_ids)))  # max number of digits for a cluster id
    # site_ids for each cluster_id (these distinguish PV sites from wind sites that may have the same number)
    site_ids = ['PV_' + str(cluster_id).zfill(cluster_id_digits) for cluster_id in cluster_ids]

    # calculate weighted average lat and lon for each cluster
    # (note: the axis=0 and axis=1 keep pandas from generating lots of nans due to
    # trying to match column name in addition to row index)
    cluster_coords = pd.concat([
        cluster_cell['cluster_id'],
        cluster_cell[['solar_lat', 'solar_lon']].multiply(cluster_cell['solar_area'], axis=0)
    ], axis=1).groupby('cluster_id').sum().div(cluster_total_solar_area, axis=0)
    cluster_coords.columns=['latitude', 'longitude']

    # get list of technologies to be defined
    technologies = central_solar_techs.index.values

    # calculate capacity factors for all projects

    # This dict will hold vectors of capacity factors for each cluster for each year and technology.
    # This arrangement is simpler than using a DataFrame because we don't yet know the
    # indexes (timesteps) of the data for each year.
    cluster_cap_factors = dict()
    for tech in technologies:
        # go through all the needed nsrdb cells and add them to the capacity factor for the
        # relevant cluster and year
        for cell_id, grp in cell:
            # grp has one row for each cluster that uses data from this cell
            lat = round_coord(grp['nsrdb_lat'].iloc[0])
            lon = round_coord(grp['nsrdb_lon'].iloc[0])
            for year in years:
                cap_factors = get_cap_factors(nsrdb_file_dict[lat, lon, year], central_solar_techs.loc[tech, 'array_type'])
                # note: iterrows() would convert everything to a single (float) series, but itertuples doesn't
                for clst in grp.itertuples():
                    contrib = cap_factors * clst.solar_area / cluster_total_solar_area[clst.cluster_id]
                    key = (tech, clst.cluster_id, year)
                    if key in cluster_cap_factors:
                        cluster_cap_factors[key] += contrib
                    else:
                        cluster_cap_factors[key] = contrib

    # get timesteps for each year (based on lat and lon of first cell in the list)
    timesteps = dict()
    lat = round_coord(cluster_cell['nsrdb_lat'].iloc[0])
    lon = round_coord(cluster_cell['nsrdb_lon'].iloc[0])
    for year in years:
        timesteps[year] = get_timesteps(nsrdb_file_dict[(lat, lon, year)])

    # make an index of all timesteps
    timestep_index = pd.concat([pd.DataFrame(index=x) for x in timesteps.values()]).index.sort_values()

    # make a single dataframe to hold all the data
    cap_factor_df = pd.DataFrame(
        index=timestep_index,
        columns=pd.MultiIndex.from_product([technologies, site_ids]),
        dtype=float
    )

    # assign values to the dataframe
    for ((tech, cluster_id, year), cap_factors) in cluster_cap_factors.iteritems():
        cap_factor_df.update(pd.DataFrame(
                cap_factors,
                index=timesteps[year],
                columns=[(tech, 'PV_' + str(cluster_id).zfill(cluster_id_digits))]
        ))
    cap_factor_df.columns.names = ['technology', 'site']
    cap_factor_df.index.names=['date_time']

    # add load_zone and orientation to the index
    cap_factor_df['load_zone'] = load_zone
    cap_factor_df['orientation'] = 'na'
    cap_factor_df.set_index(['load_zone', 'orientation'], append=True, inplace=True)
    # convert to database orientation, with natural order for indexes,
    # but also keep as a DataFrame
    cap_factor_df = pd.DataFrame(
        {'cap_factor': cap_factor_df.stack(cap_factor_df.columns.names)}
    )
    # sort table, then switch to using z, t, s, o as index (to match with project table)
    cap_factor_df = cap_factor_df.reorder_levels(
        ['load_zone', 'technology', 'site', 'orientation', 'date_time']
    ).sort_index().reset_index('date_time')

    # make a dataframe showing potential projects (same structure as "project" table)
    # note: for now we don't really handle multiple load zones and we don't worry about orientation
    # (may eventually have projects available with different azimuth and slope)
    # This concatenates a list of DataFrames, one for each technology
    project_df = pd.concat([
        pd.DataFrame(dict(
            load_zone=load_zone,
            technology=tech,
            site=site_ids,
            orientation='na',
            max_capacity=cluster_total_solar_area*central_solar_techs.loc[tech, 'mw_per_m2'],
            latitude=cluster_coords['latitude'],
            longitude=cluster_coords['longitude'],
        ))
        for tech in technologies
    ], axis=0).set_index(['load_zone', 'technology', 'site', 'orientation'])


    # store data in postgresql tables
    shared_tables.create_table("project")
    execute("DELETE FROM project WHERE technology IN %s;", [tuple(technologies)])
    project_df.to_sql('project', db_engine, if_exists='append')
    # TODO: write shared_tables.calculate_interconnect_distances() and call it from here

    # retrieve the project IDs (created automatically in the database)
    project_ids = pd.read_sql(
        "SELECT project_id, load_zone, technology, site, orientation "
        + "FROM project WHERE technology IN %(techs)s;",
        db_engine, index_col=['load_zone', 'technology', 'site', 'orientation'],
        params={'techs': tuple(technologies)}
    )
    cap_factor_df['project_id'] = project_ids['project_id']

    # convert date_time values into strings for insertion into postgresql.
    # Inserting a timezone-aware DatetimeIndex into postgresql fails; see
    # http://stackoverflow.com/questions/35435424/pandas-to-sql-gives-valueerror-with-timezone-aware-column/35552061
    # note: the string conversion is pretty slow
    cap_factor_df['date_time'] = pd.DatetimeIndex(cap_factor_df['date_time']).strftime("%Y-%m-%d %H:%M:%S%z")

    cap_factor_df.set_index(['project_id', 'date_time'], inplace=True)
    # Do we need error checking here? If any projects aren't in cap_factor_df, they'll
    # create single rows with NaNs (and any prior existing cap_factors for them will
    # get dropped below).
    # If any rows in cap_factor_df aren't matched to a project, they'll go in with
    # a null project_id.

    shared_tables.create_table("cap_factor")    # only created if it doesn't exist
    shared_tables.drop_indexes("cap_factor")    # drop and recreate is faster than incremental sorting
    execute("DELETE FROM cap_factor WHERE project_id IN %s;", [tuple(project_ids['project_id'])])
    cap_factor_df.to_sql('cap_factor', db_engine, if_exists='append', chunksize=10000)
    shared_tables.create_indexes("cap_factor")


def get_cap_factors(file, array_type):
    dat = ssc.data_create()

    # set system parameters
    # These match Table 7 of Appendix F of 2016-04-01 PSIP Book 1 unless otherwise noted
    dc_ac_ratio = 1.5
    ssc.data_set_number(dat, 'system_capacity', 1.0 * dc_ac_ratio) # dc, kW (we want 1000 kW AC)
    ssc.data_set_number(dat, 'dc_ac_ratio', dc_ac_ratio)
    ssc.data_set_number(dat, 'tilt', 0)
    ssc.data_set_number(dat, 'azimuth', 180)
    ssc.data_set_number(dat, 'inv_eff', 96)
    ssc.data_set_number(dat, 'losses', 14.0757)
    # array_type: 0=fixed rack, 1=fixed roof, 2=single-axis, 3=single-axis backtracked
    ssc.data_set_number(dat, 'array_type', array_type)
    # gcr: ground cover ratio (may be used for backtrack and shading calculations)
    ssc.data_set_number(dat, 'gcr', 0.4)
    ssc.data_set_number(dat, 'adjust:constant', 0)
    # module_type: 0=standard, 1=premium, 2=thin film
    # I set it to a reasonable value (probably default)
    ssc.data_set_number(dat, 'module_type', 0)

    # specify the file holding the solar data
    ssc.data_set_string(dat, 'solar_resource_file', file)

    # run PVWatts5
    if ssc.module_exec(pvwatts5, dat) == 0:
        err = 'PVWatts V5 simulation error:\n'
        idx = 1
        msg = ssc.module_log(pvwatts5, 0)
        while (msg is not None):
            err += '\t: {}\n'.format(msg)
            msg = ssc.module_log(pvwatts5, idx)
            idx += 1
        raise RuntimeError(err.strip())
    else:
        # get power production in kW; for a 1 kW AC system this is also the capacity factor
        cap_factors = np.asarray(ssc.data_get_array(dat, 'gen'), dtype=float)

    ssc.data_free(dat)

    return cap_factors

def get_timesteps(file):
    """Retrieve timesteps from nsrdb file as pandas datetime series. Based on code in sscapi.run_test2()."""
    dat = ssc.data_create()

    ssc.data_set_string(dat, 'file_name', file)
    ssc.module_exec_simple_no_thread('wfreader', dat)

    # create a tzinfo structure for this file
    # note: nsrdb uses a fixed offset from UTC, i.e., no daylight saving time
    tz_offset = ssc.data_get_number(dat, 'tz')
    tzinfo = dateutil.tz.tzoffset(None, 3600 * tz_offset)

    df = pd.DataFrame(dict(
        year=ssc.data_get_array(dat, 'year'),
        month=ssc.data_get_array(dat, 'month'),
        day=ssc.data_get_array(dat, 'day'),
        hour=ssc.data_get_array(dat, 'hour'),
        minute=ssc.data_get_array(dat, 'minute'),
    )).astype(int)

    ssc.data_free(dat)

    # create pandas DatetimeIndex for the timesteps in the file
    # note: we ignore minutes because time indexes always refer to the start of the hour
    # in our database
    # note: if you use tz-aware datetime objects with pd.DatetimeIndex(), it converts them
    # to UTC and makes them tz-naive. If you use pd.to_datetime() to make a column of datetime
    # values, you have to specify UTC=True and then it does the same thing.
    # So we start with naive datetimes and then specify the tzinfo when creating the
    # DatetimeIndex. (We could also use idx.localize(tzinfo) after creating a naive DatetimeIndex.)

    timesteps = pd.DatetimeIndex(
        [datetime.datetime(year=t.year, month=t.month, day=t.day, hour=t.hour) for t in df.itertuples()],
        tz=tzinfo
    )
    return timesteps

# # This class is based on http://stackoverflow.com/questions/17976063/how-to-create-tzinfo-when-i-have-utc-offset
# # It does the same thing as dateutil.tz.tzoffset, so we use that instead.
# class TimeZoneInfo(datetime.tzinfo):
#     """tzinfo derived concrete class"""
#     _dst = datetime.timedelta(0)
#     _name = None
#     def __init__(self, offset_hours):
#         self._offset = datetime.timedelta(hours=offset_hours)
#     def utcoffset(self, dt):
#         return self._offset
#     def dst(self, dt):
#         return self.__class__._dst
#     def tzname(self, dt):
#         return self.__class__._name

def db_path(path):
    """Convert the path specified relative to the database directory into a real path.
    For convenience, this also converts '/' file separators to whateer is appropriate for
    the current operating system."""
    return os.path.join(database_dir, *path.split('/'))
def round_coord(coord):
    # convert lat or lon from whatever form it's currently in to a standard form (2-digit rounded float)
    # this gives more stable matching in dictionaries, indexes, etc.
    return round(float(coord), 2)

def get_nsrdb_file_dict():
    # get a list of all the files that have data for each lat/lon pair
    # (parsed from the file names)
    file_dict = dict()
    years = set()
    for dir_name, dirs, files in os.walk(db_path(nsrdb_dir)):
        for f in files:
            file_path = os.path.join(dir_name, f)
            m = nsrdb_file_regex.match(f)
            if m is None:
                # print "Skipping unrecognized file {}".format(file_path)
                pass
            else:
                lat = round_coord(m.group('lat'))
                lon = round_coord(m.group('lon'))
                year = int(m.group('year'))
                file_dict[lat, lon, year] = file_path
                years.add(year)
    return file_dict, years

def distributed_pv():
    # for now, just reuse old data

    # store data in postgresql tables
    shared_tables.create_table("project")
    shared_tables.create_table("cap_factor")

    # remove old records (best before removing indexes)
    execute("""
        DELETE FROM cap_factor WHERE project_id IN (SELECT project_id FROM project WHERE technology = 'DistPV');
    """)
    execute("""
        DELETE FROM project WHERE technology = 'DistPV';
    """)

    # remove indexes
    shared_tables.drop_indexes("cap_factor")    # drop and recreate is faster than incremental sorting

    execute("""
        INSERT INTO project (load_zone, technology, site, orientation, max_capacity)
        SELECT load_zone, technology, 'DistPV' AS site, orientation, max_capacity
            FROM max_capacity_pre_2016_06_21
            WHERE technology = 'DistPV';
    """)
    execute("""
        INSERT INTO cap_factor (project_id, date_time, cap_factor)
            SELECT project_id, date_time, cap_factor
                FROM cap_factor_pre_2016_06_21 cf JOIN project USING (load_zone, technology, orientation)
                WHERE cf.technology = 'DistPV';
    """)

    # restore indexes
    shared_tables.create_indexes("cap_factor")

if __name__ == '__main__':
    main()
