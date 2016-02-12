# based on pyomo/pysp/plugins/testphextension.py

from pyomo.util.plugin import *
from pyomo.pysp import phextension
from pyomo.environ import value
from pyomo.pysp.phboundbase import ExtractInternalNodeSolutionsforInner
from pyomo.pysp.phutils import indexToString

import sys, os, datetime
cur_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(cur_dir, "switch-hawaii-core"))
import util

class testphextension(SingletonPlugin):

    implements(phextension.IPHExtension) 

    def reset(self, ph):
        pass

    def pre_ph_initialization(self, ph):
        pass

    def post_instance_creation(self, ph):
        pass

    def post_ph_initialization(self, ph):
        pass

    def post_iteration_0_solves(self, ph):
        pass

    def post_iteration_0(self, ph):
        pass

    def pre_iteration_k_solves(self, ph):
        pass

    def post_iteration_k_solves(self, ph):
        pass

    def post_iteration_k(self, ph):
        pass

    def post_ph_execution(self, ph):
        #import pdb; pdb.Pdb(stdout=sys.__stdout__).set_trace() # have to grab original stdout, or this crashes

        # note: when solved in serial mode, ph.get_scenario_tree().get_arbitrary_scenario()._instance
        # contains a solved instance that can (maybe) be used for reporting at this point,
        # as done in old_post_ph_execution below. However, when using pyro, that is not available.
        # Also, at this point with the parallel or serial solver, ph.get_scenario_tree()._solution
        # and ph._scenario_tree.findRootNode().get_variable_value(name, index) (which reads it) have no values.

        # So we take a different course, using the best available solution directly from the scenario tree.
        # The code below is modeled on pyomo.pysp.ph.ProgressiveHedging.pprint()
        
        # note: at this point, we might be able to use ph.get_scenario_tree().get_arbitrary_scenario()._x[root_node.name] 
        # to get a solution for one of the scenarios (the first), but ExtractInternalNodeSolutionsforInner() 
        # seems designed to give a definitive solution (i.e., the best admissable solution) (see 
        # compute_and_report_inner_bound_using_xhat which is calculated a few lines below the point 
        # where this is called in pyomo.pysp.ph)
        
        # NOTE: this actually gets called by the phsolverserver (on the remote node), not runph.
        # It's not clear what information is in the local scenario tree about the solutions from 
        # other scenarios. So ExtractInternalNodeSolutionsforInner() may actually not be valid 
        # at this point. THIS NEEDS FURTHER INVESTIGATION.

        # useful elements for getting variable values:
        # node._variable_indices = {varname: [(key1a, key1b), (key2a, key2b)]}
        # node._variable_ids = {varid: (varname, (key1a, key1b))}
        # node._name_index_to_id = {(varname, (key1a, key1b)): varid}

        root_node = ph.get_scenario_tree().findRootNode()
        solution = ExtractInternalNodeSolutionsforInner(ph)[root_node.name] # {id: value}
        variable_names = sorted(root_node._variable_indices.keys())
        # alternatively, this could be (as in ph.pprint)
        # variable_names = sorted(ph.get_scenario_tree().stages[0]._variables.keys())

        variable_data = [
            (
                v + indexToString(k),   # var name with index
                solution[root_node._name_index_to_id[(v, k)]]   # current value
            )
                for v in variable_names 
                    for k in sorted(root_node._variable_indices[v])
        ]
        
        jobid = os.environ.get('SLURM_JOBID')
        if jobid is None:   # not running under slurm
            jobid = datetime.datetime.now().isoformat("_").replace(":", ".")
            
        output_file = os.path.join("outputs", "build_{}.tsv".format(jobid))
        
        print "writing {}...".format(output_file)
        # print "variables to write:"
        # print variable_data
        
        with open(output_file, 'w') as f:
            f.writelines(
                "\t".join(map(str, r)) + "\n"
                    for r in [("variable", "value")] + variable_data
            )
            

    def old_post_ph_execution(self, ph):
        # NOTE: when running in serial mode (without pyro), 
        # ph.get_scenario_tree().get_arbitrary_scenario()._instance
        # contains a solved instance at this point, which can be used
        # to report results, as done below. However, on parallel systems,
        # this instance doesn't exist yet. So we have to use the variable
        # ids and names from the RootNode as shown above.

        import pdb; pdb.Pdb(stdout=sys.__stdout__).set_trace() # have to grab original stdout, or this crashes

        # note: it is not clear whether all scenarios in this node have been
        # pushed to the same solution at this point, but they should at least
        # be close. The progressive hedging code sometimes uses a function 
        # ExtractInternalNodeSolutionsforInner to choose the scenario which is
        # closest to the average, which would be great to use here. But it's 
        # not clear how the result of this function should be used. One would 
        # hope it was used to provide data for the 
        # ph._scenario_tree.findRootNode().get_variable_value(name, index) function, but that
        # function says no data are available at this point 
        # (and ph._scenario_tree.findRootNode()._solution is indeed empty at this point).
        # So, lacking any better option, we pull values from an arbitrary instance.
        # (This could just as well be ph._scenario_tree._scenarios[0]._instance, and in fact it is.)

        m = ph.get_scenario_tree().get_arbitrary_scenario()._instance

        build_vars = [
            "BuildProj", "BuildBattery", 
            "BuildPumpedHydroMW", "BuildAnyPumpedHydro",
            "RFMSupplyTierActivate",
            "BuildElectrolyzerMW", "BuildLiquifierKgPerHour", "BuildLiquidHydrogenTankKg",
            "BuildFuelCellMW"
        ]
        
        vars = [getattr(m, v) for v in build_vars if hasattr(m, v)]
        vardata = [v[k] for v in vars for k in v]
        
        def safe_value(v):
            try:
                return value(v) # note: using v.value returns None, with no error
            except ValueError:
                # for some reason, some variable values are uninitialized, 
                # which gives errors when they're accessed
                print "No value found for {v}.".format(v=v.cname())
                return "*** None ***"
        
        jobid = os.environ.get('SLURM_JOBID')
        if jobid is None:
            jobid = datetime.datetime.now().isoformat("_").replace(":", ".")
            
        print "writing results for job {}...".format(jobid)
        print "variables to write:"
        print ", ".join(["{v}[{k}]".format(v=v, k=k) for v in vars for k in v])
        util.write_table(
            m, vardata,
            output_file=os.path.join("outputs", "build_{}.tsv".format(jobid)), 
            headings=("variable", "value"),
            values=lambda m, v: (v.cname(), safe_value(v))
        )
