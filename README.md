# switch-hawaii
Data and code for Hawaii version of SWITCH

##INSTALLATION

###INSTALL PYTHON AND PYOMO

Python: On recent Mac or Linux systems, a suitable version of Python should already be installed (SWITCH needs one of the 2.7 versions). On Windows, you should download the binary installer from https://www.python.org/downloads/windows/ . If installing on Windows, choose the options to change system settings (this adds the python commands to your command-line path) and to install pip.

Pyomo: Once Python is installed go to a terminal window (Terminal.app on a Mac; Windows-R, then cmd on Windows). Then on Mac or Linux execute "sudo -H pip install pyomo". On Windows execute "pip install pyomo".

###INSTALL SWITCH.

It is recommended that you install the git command line tool on your system and then follow Option 1 below. Alternatively you can install the latest version by following Option 2 below.

####Option 1

In a terminal window, use the cd command to switch to the folder where you want to install SWITCH-Hawaii. Then execute "git clone https://github.com/switch-model/switch-hawaii-studies.git"

If you want to use a previous version of the model and data, you should checkout the version you want from the repository you have just created. Do this with a command like this:

git checkout <version>

The current options for <version> are "v2016-01-15-data" and "v2016-01-28". You can skip this command or use "git checkout master" to use the latest version of SWITCH.

On a Mac or Linux system, execute these commands:
```
cd switch-hawaii-studies/models/rps
./install_switch.sh
```
On Windows, execute these commands:
```
cd switch-hawaii-studies\models\rps
[then copy the "git clone ..." commands from install_switch.sh and run them from the commadn line]
```
####Option 2

Download the repository from https://github.com/switch-model/switch-hawaii-studies/archive/master.zip and decompress it into a suitable location. Make a note of the name of the folder you have created ("switch-hawaii-studies" is a good name).

Download the repository from https://github.com/switch-model/switch/archive/master.zip and decompress it into a folder called "switch". Place this folder inside the "models/rps" folder within the "switch-hawaii-studies" folder that you just created.

Download the repository from https://github.com/switch-model/switch-hawaii-core/archive/master.zip and decompress it into a folder called "switch-hawaii-core". Place this folder inside the "models/rps" folder within the "switch-hawaii-studies" folder that you just created.

###INSTALL A SOLVER

SWITCH creates standard matrices defining the numerical optimization model to be solved. Then it uses standard solvers to solve these models. 

CPLEX or GUROBI are high-performance solvers which are available from their developers at no cost for academic users. GLPK is an open-source solver which is free for any user. 

Please see https://github.com/switch-model/switch/blob/master/INSTALL for information on installing a solver.

###RUN SWITCH

In a terminal window, use the cd command to get to the switch-hawaii-studies/models/rps directory you created earlier. Then execute this command to run the model:
```
python solve.py
```
Inputs will be read from the inputs directory, and outputs will be written to the outputs directory. 

"scenarios_to_run.txt" defines the scenarios that should be run. "completed_scenarios.txt" is a list of scenarios that have already been run. To re-run a scenario that has already been run, you can remove it from "completed_scenarios.txt" and run "python solve.py" again. Or you can just execute "python solve.py --scenario <scenario name>". You can also run ad hoc scenarios by specifying "python solve.py --scenario_name <new_scenario>" followed (optionally) by command line arguments to change the scenario. You can see examples of command-line arguments in scenarios_to_run.txt

For testing purposes, it is helpful to use the "inputs_tiny" directory, via a command like "python solve.py --scenario_name test --inputs inputs_tiny"

