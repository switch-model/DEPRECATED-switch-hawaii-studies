# This will eventually be a good place to put all the code to create the main database
# for Switch-Hawaii. For now it just imports a few miscellaneous tables that were not
# imported by other code.
# Started by Matthias Fripp on 2015-07-27

import time, sys, os
from textwrap import dedent
import psycopg2, openpyxl

# TODO: set this up to use ssl certificates or an SSH tunnel, because
# otherwise postgres sends the password over the network as clear text.

# NOTE: instead of using the python csv writer, this directly writes tables to 
# file in the pyomo .tab format. This uses tabs between columns and the standard
# line break for the system it is run on. This does the following translations (only):
# - If a value contains double quotes, they get doubled.
# - If a value contains a single quote, tab or space character, the value gets enclosed in double quotes. 
#   (Note that pyomo doesn't allow quoting (and therefore spaces) in column headers.)
# - null values are converted to . (the pyomo/ampl standard for missing data)
# - any other values are simply passed to str().

# NOTE: this does not use the python csv writer because it doesn't support the quoting
# or null behaviors described above.

try:
    pghost='switch.eng.hawaii.edu'
    # note: the connection gets created when the module loads and never gets closed (until presumably python exits)
    con = psycopg2.connect(database='switch', host=pghost, user='switch_user')
    # set connection to commit changes automatically after each query is run
    con.autocommit = True
    
except psycopg2.OperationalError:
    print dedent("""
        ############################################################################################
        Error while connecting to switch database on postgres server {server} as user 'switch_user'.
        Please ensure that there is a line like "*:*:*:switch_user:<password>" in 
        ~/.pgpass (which should be chmod 0600) or %APPDATA%\postgresql\pgpass.conf (Windows).    
        See http://www.postgresql.org/docs/9.1/static/libpq-pgpass.html for more details.
        ############################################################################################
        """.format(server=pghost))
    raise

def execute(query, arguments=None):
    args = [dedent(query)]
    if arguments is not None:
        args.append(arguments)
    cur = con.cursor()
    cur.execute(*args)
    return cur

def executemany(query, arguments=None):
    args = [dedent(query)]
    if arguments is not None:
        args.append(arguments)
    cur = con.cursor()
    cur.executemany(*args)

def get_table_from_xlsx(xlsx_file, named_range):
    wb = openpyxl.load_workbook(xlsx_file, data_only=True)  # load the file, ignore formula text
    full_range = wb.get_named_range(named_range)
    # note: named range should be a simple rectangular region; 
    # if it contains more than one region we ignore all but the first
    d1 = full_range.destinations[0]
    ws = d1[0]
    region = d1[1]
    data = list(tuple(c.value for c in r) for r in ws[region])
    head = data.pop(0)  # take out the header row
    data = zip(*data)   # switch from row to column orientation
    # make a dictionary, with one column for each element of header row
    return dict(zip(head, data))
    

#########################
# ev adoption

# identify pairs of (ev_scen_id, HECO scenario name):
ev_adoption_scenarios=(
    (1, 'No Burning Desire'), # low
    (2, 'Blazing a Bold Frontier'), # high
    (3, 'Stuck in the Middle'), # medium, a.k.a. 'Moved by Passion'
)
# get the EV adoption curves from an Excel workbook 
# (based on HECO IRP 2013 Appendix E-10, p. E-113, extended to 2050)
ev_adoption_curves = get_table_from_xlsx("EV simple projections.xlsx", named_range='EV_Adoption')

# create the ev_adoption table
execute("""
    DROP TABLE IF EXISTS ev_adoption;
    CREATE TABLE ev_adoption (
        load_zone varchar(40),
        year int,
        ev_scen_id int,
        ev_gwh float
    );
""")

# insert data into the ev_adoption table
n_rows = len(ev_adoption_curves['Year'])
for (ev_scen_id, col_name) in ev_adoption_scenarios:
    executemany(
        "INSERT INTO ev_adoption (load_zone, year, ev_scen_id, ev_gwh) VALUES (%s, %s, %s, %s)",
        zip(['Oahu']*n_rows, ev_adoption_curves['Year'], [ev_scen_id]*n_rows, ev_adoption_curves[col_name])
    )

print "Created ev_adoption table."

