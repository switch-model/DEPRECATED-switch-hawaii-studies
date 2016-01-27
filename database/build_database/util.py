import psycopg2
from textwrap import dedent

# note: con and cur stay open until the module goes out of scope
con = psycopg2.connect(database='switch', host='redr.eng.hawaii.edu')
cur = con.cursor()    

def execute(query, *args, **kwargs):
    _execute(query, False, *args, **kwargs)

def executemany(query, *args, **kwargs):
    _execute(query, True, *args, **kwargs)

def _execute(query, many, *args, **kwargs):
    q = dedent(query)
    func = cur.executemany if many else cur.execute
    print q
    try:
        func(q, *args, **kwargs)
        con.commit()
        return cur
    except:
        con.rollback()
        raise
    
