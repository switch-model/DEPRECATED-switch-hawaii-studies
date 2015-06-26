import time, sys
from textwrap import dedent
import psycopg2

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

def write_table(output_file, query, arguments):
    cur = con.cursor()

    print "Writing {file} ...".format(file=output_file),
    sys.stdout.flush()  # display the part line to the user

    start=time.time()
    cur.execute(dedent(query), arguments)

    with open(output_file, 'w') as f:
        # write header row
        writerow(f, [d[0] for d in cur.description])
        # write the query results (cur is used as an iterator here to get all the rows one by one)
        writerows(f, cur)

    print "time taken: {dur:.2f}s".format(dur=time.time()-start)

def stringify(val):
    if val is None:
        out = '.'
    elif type(val) is str:
        out = val.replace('"', '""')
        if any(char in out for char in [' ', '\t', '"', "'"]):
            out = '"' + out + '"'
    else:
        out = str(val)
    return out

def writerow(f, row):
    f.write('\t'.join(stringify(c) for c in row) + '\n')

def writerows(f, rows):
    for r in rows:
        writerow(f, r)
