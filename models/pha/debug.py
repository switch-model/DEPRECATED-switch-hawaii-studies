# based on http://stackoverflow.com/questions/242485/starting-python-debugger-automatically-on-error
# use "import debug" somewhere in your code as an alternative to "python -m pdb myscript...",
# which requires a keypress at the start and may or may not process arguments correctly.

import os, sys, socket, traceback, pdb
import remote_pdb

def info(type, value, tb):
    hostname = socket.gethostname()
    jobid = os.environ.get('SLURM_JOBID')
    port = get_unused_port()
    
    # note: this fails, probably because the node user acct can't send e-mail.
    # it should also be generalized to send the message to the account designated
    # to receive notices for this job (if any). The recipient e-mails are not 
    # shown in local environment variables, but they could be set in the .slurm batch file.
    # os.system(
    #     'mail -s "Error running job {j}. Remote debugger is running on {h}:{p}." '
    #     + '8083489586@vtext.com < /dev/null'.format(j=jobid, h=hostname, p=port)
    # )

    print
    traceback.print_exception(type, value, tb)
    print
    print 'Starting remote debugger.'
    print 'Use "telnet {h} {p}" to connect'.format(h=hostname, p=port)
    print
    post_mortem(tb, port=port)

sys.excepthook = info

# based on remote_pdb.set_trace() and
# https://github.com/python/cpython/blob/master/Lib/pdb.py
def post_mortem(t=None, host='0.0.0.0', port=0, patch_stdstreams=False):
    # handling the default
    if t is None:
        # sys.exc_info() returns (type, value, traceback) if an exception is
        # being handled, otherwise it returns None
        t = sys.exc_info()[2]
    if t is None:
        raise ValueError("A valid traceback must be passed if no "
                         "exception is being handled")

    p = remote_pdb.RemotePdb(host=host, port=port, patch_stdstreams=patch_stdstreams)
    p.reset()
    p.interaction(None, t)

def get_unused_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    addr = s.getsockname()
    port = addr[1]
    s.close()
    return port
