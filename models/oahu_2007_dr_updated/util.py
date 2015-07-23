import csv, sys, time, itertools
from pyomo.environ import value
import __main__ as main

# check whether this is an interactive session
# (if not, there will be no __main__.__file__)
interactive_session = not hasattr(main, '__file__')

csv.register_dialect("ampl-tab", 
    delimiter="\t", 
    lineterminator="\n",
    doublequote=False, escapechar="\\", 
    quotechar='"', quoting=csv.QUOTE_MINIMAL,
    skipinitialspace = False
)

def create_table(**kwargs):
    """Create an empty output table and write the headings."""
    output_file = kwargs["output_file"]
    headings = kwargs["headings"]

    with open(output_file, 'wb') as f:
        w = csv.writer(f, dialect="ampl-tab")
        # write header row
        w.writerow(list(headings))

def append_table(model, *indexes, **kwargs):
    """Add rows to an output table, iterating over the indexes specified, 
    and getting row data from the values function specified."""
    output_file = kwargs["output_file"]
    values = kwargs["values"]

    # create a master indexing set 
    # this is a list of lists, even if only one list was specified
    idx = itertools.product(*indexes)
    with open(output_file, 'ab') as f:
        w = csv.writer(f, dialect="ampl-tab")
        # write the data
        w.writerows(
            tuple(value(v) for v in values(model, *x)) 
            for x in idx
        )

def write_table(model, *indexes, **kwargs):
    """Write an output table in one shot - headers and body."""
    output_file = kwargs["output_file"]

    print "Writing {file} ...".format(file=output_file),
    sys.stdout.flush()  # display the part line to the user
    start=time.time()

    create_table(**kwargs)
    append_table(model, *indexes, **kwargs)

    print "time taken: {dur:.2f}s".format(dur=time.time()-start)


def write_table_old(model, *indexes, **kwargs):
    # there may be a way to accept specific named keyword arguments and also an 
    # open-ended list of positional arguments (*indexes), but I don't know what that is.
    output_file = kwargs["output_file"]
    headings = kwargs["headings"]
    values = kwargs["values"]

    print "Writing {file} ...".format(file=output_file),
    sys.stdout.flush()  # display the part line to the user
    start=time.time()

    # create a master indexing set 
    # this is a list of lists, even if only one list was specified
    idx = itertools.product(*indexes)
    with open(output_file, 'wb') as f:
        w = csv.writer(f, dialect="ampl-tab")
        # write header row
        w.writerow(list(headings))
        # write the data
        w.writerows(
            tuple(value(v) for v in values(model, *x)) 
            for x in idx
        )

    print "time taken: {dur:.2f}s".format(dur=time.time()-start)
