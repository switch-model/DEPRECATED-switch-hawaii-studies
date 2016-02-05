# based on pyomo/pysp/plugins/testphextension.py

from pyomo.util.plugin import *
from pyomo.pysp import phextension
from pyomo.environ import value

import sys, os
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

        # import pdb; pdb.Pdb(stdout=sys.__stdout__).set_trace() # have to grab original stdout, or this crashes

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

        m = ph._scenario_tree.get_arbitrary_scenario()._instance

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
        
        print "writing results (newest version)..."
        util.write_table(
            m, vardata,
            output_file=os.path.join("outputs", "build.tsv"), 
            headings=("variable", "value"),
            values=lambda m, v: (v.cname(), safe_value(v))
        )
