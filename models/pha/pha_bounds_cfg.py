# use this by adding terms like the following to the runph command:
# --linearize-nonbinary-penalty-terms=5 --breakpoint-strategy=1 --bounds-cfgfile=pha_bounds_cfg.py

print "loading pha_bounds_cfg.py"

# grab the model from the great-grandparent's namespace, 
# since it's not provided as promised by the documentation (m = self._model_instance)

# import inspect
# ph_framerec = inspect.stack()[3]
# ph_frame = ph_framerec[0]
# ph_locals = ph_frame.f_locals
# print ph_locals
# if 'callback_name' in ph_locals and ph_locals['callback_name'] == 'pysp_boundsetter_callback':
#     m = ph_locals['self']._model_instance
# else:
#     print "local variables in current callstack:"
#     for i, framerec in enumerate(inspect.stack()):
#         frame = framerec[0]
#         print i, frame.f_locals
#     raise RuntimeError("Unable to find frame record for Progressive Hedging object.")


def pysp_boundsetter_callback(self, scenario_tree, scenario):
    m = scenario._instance 	# see pyomo/pysp/scenariotree/tree_structure.py

    # import pdb; f = pdb.set_trace; f()

    if hasattr(m, "hydrogen_electrolyzer_kg_per_mwh"):
        electrolyzer_kg_per_mwh = m.hydrogen_electrolyzer_kg_per_mwh
        fuel_cell_mwh_per_kg = m.hydrogen_fuel_cell_mwh_per_kg
    else:
        electrolyzer_kg_per_mwh = 18
        fuel_cell_mwh_per_kg = 0.018
    
    # limit most variables to 3000 MW (only used to linearize progressive hedging quadratic term)
    build_var_limits = [
        ("BuildProj", 3000),
        ("BuildBattery", 3000),
        ("BuildPumpedHydroMW", 300),  # may be redundant with tighter constraints already in place
        # skip BuildAnyPumpedHydro, and RFMSupplyTierActivate because they are binary
        ("BuildElectrolyzerMW", 3000),
        ("BuildLiquifierKgPerHour", 3000.0 * electrolyzer_kg_per_mwh),  # enough to consume 3000 MW
        ("BuildLiquidHydrogenTankKg", 1500 * 8760 / fuel_cell_mwh_per_kg), # enough to produce 1500 MW for 1 y
        ("BuildFuelCellMW", 3000),
    ]

    for (var_name, limit) in build_var_limits:
        # print "checking for var {}".format(var_name)
        if hasattr(m, var_name):
            # print "setting bounds for {}".format(var_name)
            var = getattr(m, var_name)
            for k in var:
                # print "setting bounds for {var}[{k}]".format(var=var_name, k=k)

                # import pdb; pdb.set_trace()
                
                if var[k].lb is None:
                    # print "setting lower bound for {var}[{k}]".format(var=var_name, k=k)
                    var[k].setlb(0.0)
                # else:
                #     print "lower bound for {var}[{k}] already set to {b}".format(var=var_name, k=k, b=var[k].lb)
                    
                if var[k].ub is None:
                    # print "setting upper bound for {var}[{k}]".format(var=var_name, k=k)
                    var[k].setub(float(limit))
                # else:
                #     print "upper bound for {var}[{k}] already set to {b}".format(var=var_name, k=k, b=var[k].ub)

                # note: the code below seems to be the current official way to do it, but it is unnecessarily complicated
                # and just does the same as the code above; it may be on the way to deprecation

                # # note: we have to pass a tree node to setVariableBoundsOneScenario.
                # # It doesn't actually use it, so this one is as good as any.
                # tree_node = scenario_tree.findRootNode()
                # # note: getSymbol appears to be inverse of getObject, used in setVariableBoundsAllScenarios
                # var_id = m._ScenarioTreeSymbolMap.getSymbol(var[k])
                # # NOTE: contrary to the documentation, this gets called once for every scenario,
                # # so it makes more sense to use setVariableBoundsOneScenario instead of
                # # setVariableBoundsAllScenarios. Also note: that function doesn't really need
                # # a treenode, but we pass it anyway.
                # self.setVariableBoundsOneScenario(tree_node, scenario, var_id, 0.0, float(limit))
    
# for some reason runph looks for pysp_boundsetter_callback when run in single-thread mode
# and ph_boundsetter_callback when called from mpirun with remote execution via pyro.
# so we map both names to the same function.
ph_boundsetter_callback = pysp_boundsetter_callback