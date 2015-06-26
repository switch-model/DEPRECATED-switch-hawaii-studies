import pdb, sys, traceback, inspect

def run(cmd):
    frame = inspect.currentframe().f_back
    try:
        eval(cmd, frame.f_globals,frame.f_locals)
    except:
        # type, value, tb = sys.exc_info()
        # print_tb(tb)
        traceback.print_exc()
        pdb.post_mortem()
