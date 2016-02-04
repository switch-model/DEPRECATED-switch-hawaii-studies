# switch-hawaii-studies
Data and code for Hawaii version of SWITCH

##INSTALLATION

###INSTALL PYTHON AND PYOMO

Python: On recent Mac or Linux systems, a suitable version of Python should already be installed (SWITCH needs one of the 2.7 versions). On Windows, you should download the binary installer from https://www.python.org/downloads/windows/ . If installing on Windows, choose the options to install pip and "Add Python.exe to path".

Pyomo: Once Python is installed go to a terminal window (Terminal.app on a Mac; Windows-R, then cmd on Windows). Then on Mac or Linux execute "sudo -H pip install pyomo". On Windows execute "pip install pyomo".

###INSTALL A SOLVER

SWITCH uses Pyomo to create standard matrices defining the numerical optimization model to be solved. 
Then it uses standard solvers to solve these models. 

CPLEX or GUROBI are high-performance solvers which are available from their developers at no cost for 
academic users. GLPK is an open-source solver which is free for any user. 

**On Linux,** glpk can be installed via
```
sudo yum install -y glpk glpk-utils
```
or 
```
sudo apt-get install -y glpk glpk-utils
```

**On a Mac,** the easiest way to install glpk and other unix-style software is via the Homebrew package manager. 
If you don't want to install Homebrew, you can replace the following steps with instructions from 
http://hichenwang.blogspot.com/2011/08/fw-installing-glpk-on-mac.html .

Install homebrew package manager by typing the following command in a Terminal window (more details at brew.sh):

```
ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```
Press Return when prompted, and enter your password when prompted.

Next, you can install glpk itself by typing the following commands in a Terminal window:
```
brew install git
brew install homebrew/science/glpk
``` 

**On Windows,** glpk can be installed as follows:

1. Download the Windows version of glpk from http://sourceforge.net/projects/winglpk/ . 
2. Open the .zip file you downloaded and look in the W32 or W64 folder (depending whether you have a 32-bit or 64-bit version of Windows). 
3. Copy glpsol.exe and glpk_n_nn.dll from this folder to C:\Python27\Scripts . (n_nn is the glpk version number, e.g., 4_57)

###INSTALL SWITCH

It is recommended that you install the git command line tool on your system and then follow Option 1 below. 
Alternatively you can install the latest version by following Option 2 below.

####Option 1

In a terminal window, use the cd command to switch to the folder where you want to install SWITCH-Hawaii. Then execute "git clone https://github.com/switch-model/switch-hawaii-studies.git"

If you want to use a previous version of the model and data, you should checkout the version you want from the repository 
you have just created. Do this with a command like this:
```
git checkout <version>
```
The current options for `<version>` are `v2016-01-15-data` and `v2016-01-28`. You can skip this command or use 
`git checkout master` to use the latest version of SWITCH. 

Please note: versions of SWITCH-Hawaii from before 2016-02-03 are currently 
only compatible with Pyomo 4.1, the cplex solver and a Mac or Linux system (not Windows). 
Please contact Matthias Fripp at UH (<mfripp@hawaii.edu>) if you would like 
to run earlier versions of SWITCH-Hawaii in a different environment than this.

On a Mac or Linux system, execute these commands:
```
cd switch-hawaii-studies/models/rps
./install_switch.sh
```
On Windows, execute these commands:
```
cd switch-hawaii-studies\models\rps
[then copy the "git clone ..." commands from install_switch.sh and run them from the command line]
```
####Option 2

Download the repository from https://github.com/switch-model/switch-hawaii-studies/archive/master.zip. 
Copy the "switch-hawaii-studies-master" folder from this zip archive to a suitable location (e.g., My Documents) 
and then rename it to switch-hawaii-studies. Make a note of the name and location of the folder you have created.

Download the repository from https://github.com/switch-model/switch/archive/master.zip. Copy the "switch-master"
folder from inside this zip archive into the "models/rps" folder within the "switch-hawaii-studies" folder that 
you just created. Rename "switch-master" to "switch".

Download the repository from https://github.com/switch-model/switch-hawaii-core/archive/master.zip. Copy the
"switch-hawaii-core-master" folder from inside this zip archive into the "models/rps" folder within the 
"switch-hawaii-studies" folder. Rename "switch-hawaii-core-master" to "switch-hawaii-core".


Whether you followed Option 1 or Option 2, you should now have a directory structure like this (it will have 
other files too, but these are most of the important ones):
```
switch-hawaii-studies/
    data/
    models/
        rps/
            inputs/
            inputs_tiny/
            scenarios_to_run.txt
            solve.py
            switch/
                switch_mod/
            switch-hawaii-core/
```

###RUN SWITCH

In a terminal window, use the cd command to get to the switch-hawaii-studies/models/rps directory you created earlier. Then execute this command to run the model:
```
python solve.py
```
Inputs will be read from the inputs directory, and outputs will be written to the outputs directory. 

"scenarios_to_run.txt" defines the scenarios that should be run. "completed_scenarios.txt" is a list of 
scenarios that have already been run. To re-run a scenario that has already been run, you can remove it 
from "completed_scenarios.txt" and run `python solve.py` again. Or you can just execute 
`python solve.py --scenario <scenario name>`. You can also run ad hoc scenarios by specifying 
`python solve.py --scenario_name <new_scenario>` followed (optionally) by command line arguments 
to change the scenario. You can see examples of command-line arguments in scenarios_to_run.txt

For testing purposes, it is helpful to use the "inputs_tiny" directory, via a command like this:
```
python solve.py --scenario_name test --inputs inputs_tiny
```

##SUPPORT
If you need help installing or running SWITCH-Hawaii or defining new scenarios, please contact Matthias Fripp at the University of Hawaii at <mfripp@hawaii.edu>.
