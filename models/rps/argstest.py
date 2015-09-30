#!/usr/bin/env python

import argparse

def iterify(item):
    """Return an iterable for the one or more items passed."""
    if isinstance(item, basestring):
        i = iter([item])
    else:
        try:
            # check if it's iterable
            i = iter(item)
        except TypeError:
            i = iter([item])
    return i

class AddModuleAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        for m in iterify(values):
            setattr(namespace, m, True)

class RemoveModuleAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        for m in iterify(values):
            setattr(namespace, m, False)

class AddListAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, list())
        getattr(namespace, self.dest).extend(iterify(values))

# define a standard argument parser, which can be used to setup scenarios
parser = argparse.ArgumentParser(description='Solve one or more Switch-Hawaii scenarios.')
parser.add_argument('--inputs', dest='inputs_dir')
parser.add_argument('--outputs', dest='outputs_dir')
parser.add_argument('--scenario', action=AddListAction, dest='scenario_to_run')
parser.add_argument('--scenarios', action=AddListAction, nargs='+', dest='scenario_to_run')
parser.add_argument('--scenario_name')
parser.add_argument('--tag')
parser.add_argument('--ph_year', type=int)
parser.add_argument('--ph_mw', type=float)
# TODO: something about dr_shares
parser.add_argument('--exclude', action=AddModuleAction, dest='exclude_module', nargs='+')
parser.add_argument('-n', action=RemoveModuleAction, dest='exclude_module')
parser.add_argument('--include', action=AddModuleAction, dest='include_module', nargs='+')
parser.add_argument('-y', action=AddModuleAction, dest='include_module')
parser.add_argument(action=AddModuleAction, dest='include_module', nargs='*')
#parser.add_argument('remainder', nargs=argparse.REMAINDER)

def args_dict(parser, *a):
    """call the parser to get the args, then return them as a dictionary, omitting None's'"""
    return {k: v for k, v in vars(parser.parse_args(*a)).iteritems() if v is not None}

def parse_scenario_list(scenarios):
    """Convert a list of scenarios (specified in the form of a command line string) into a list of argument dictionaries."""
    scenario_list = []
    for s in scenarios:
        # parse scenario arguments
        a = args_dict(parser, s.split())
        scenario_list.append(a)
    return scenario_list

def requested_scenarios(standard_scenarios):
    """Return a list of argument dictionries defining scenarios requested from the command line 
    (possibly drawn/modified from the specified list of standard_scenarios)."""
    args = args_dict(parser)    
    requested_scenarios = []
    standard_dict = {s["scenario_name"]: s for s in standard_scenarios}
    if "scenario_to_run" in args:
        for s in args["scenario_to_run"]:
            if s not in standard_dict:
                raise RuntimeError("scenario {s} has not been defined.".format(s=s))
            else:
                # note: if they specified a scenario_name here, it will override the standard one
                requested_scenarios.append(merge_scenarios(standard_dict[s], args))
    elif "scenario_name" in args:
        # they have defined one specific scenario on the command line
        requested_scenarios.append(args)
    return requested_scenarios


def merge_scenarios(*scenarios):
    # combine scenarios: start with the first and then apply most settings from later ones
    # but concatenate "tag" entries and remove "scenario_to_run" entries
    d = dict(tag='')
    for s in scenarios:
        t1 = d["tag"]
        t2 = s.get("tag", "")
        s["tag"] = t1 + ("" if t1 == "" or t2 == "" else "_") + t2
        d.update(s)
    if 'scenario_to_run' in d:
        del d['scenario_to_run']
    return d


def main():
    k, u = parser.parse_known_args()
    print 'known:', k
    print 'unknown:', u
    
    # scenarios_list = parse_scenario_list([
    #     '--scenario_name rps',
    #     '--scenario_name no_renewables -n rps -n renewables -n demand_response -n pumped_hydro',
    #     '--scenario_name free -n rps',
    #     '--scenario_name rps_no_wind -n wind',
    #     '--scenario_name rps_no_wind_ph2037_150 -n wind ph_year=2037 ph_mw=150',
    # ])
    #
    # scenarios_to_run = requested_scenarios(scenarios_list)
    # if len(scenarios_to_run) > 0:
    #     # user specified specific scenarios to run
    #     for s in scenarios_to_run:
    #         print "updating completed_scenarios.txt"
    #         print "calling solve({d})".format(d=s)
    # else:
    #     # they want to run the standard scenarios
    #     print "writing modified scenarios to scenarios_to_run<_tag>.txt"
    #     print "getting next scenario to run from scenarios_to_run<_tag>.txt and completed_scenarios<_tag>.txt"
    #     print "running next scenario"


def scenario_already_run(scenario):
    """Add the specified scenario to the list in completed_scenarios.txt. Return False if it wasn't there already."""
    with open('completed_scenarios.txt', 'a+') as f:
        # wait for exclusive access to the list (to avoid writing the same scenario twice in a race condition)
        fcntl.flock(f, fcntl.LOCK_EX)
        # file starts with pointer at end; move to start
        f.seek(0, 0)                    
        if scenario + '\n' in f:
            already_run = True
        else:
            already_run = False
            # append name to the list (will always go at end, because file was opened in 'a' mode)
            f.write(scenario + '\n')
        fcntl.flock(f, fcntl.LOCK_UN)
    return already_run

if __name__ == "__main__":
    main()


"""
see 
http://bioportal.weizmann.ac.il/course/python/PyMOTW/PyMOTW/docs/argparse/index.html
https://docs.python.org/2/library/argparse.html
https://pymotw.com/2/argparse/

# if they specify one or more scenarios, just run those
# otherwise: write scenario list to disk at start
# then, do a loop: read scenario list, find first one that's not completed, run that
# (this could be get_next_scenario(), which finds the next unfinished scenario, marks it as completed and returns it)

# also append any arguments they give to the scenario arguments (maybe )
# arguments: 
--scenario/scenarios +
read in these scenarios, then apply other arguments to them
If any are specified, then for each:
    add this scenario to completed_scenarios.txt, and run it, whether or not it has been run before
    -- don't read new scenario definitions from disk
--scenario_name 
define a single new scenario, then run it (similar to --scenario for predefined ones)

--tag 
extra text to add to scenario name

--inputs=inputs
--outputs=outputs
--dr_shares/dr_shares=0.2 (*)
--ph_year=None
--ph_mw=None

-n module
module

--no/-n modules+

--ymodules+

becomes true/false list for modules, passed to solve.py

modules:
rps=True, renewables=True, wind=None,
demand_response=True,
ev=None, 
pumped_hydro=True, ph_year=None, ph_mw=None,

    
    

"""