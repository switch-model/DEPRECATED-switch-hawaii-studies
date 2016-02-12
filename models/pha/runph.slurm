#!/bin/sh

#SBATCH --job-name=ph15rho

#SBATCH --partition=kill.q
#SBATCH --time=1-12:00:00
#SBATCH --nodes=1
#SBATCH --tasks-per-node=20
#SBATCH --mem=128000    ## for the whole node
##SBATCH --ntasks=60

## reporting
#SBATCH --error=%A.err
#SBATCH --output=%A.out
##SBATCH --mail-type=BEGIN,END,FAIL,REQUEUE,TIME_LIMIT_80
##SBATCH --mail-user=8083489586@vtext.com

## max memory per cpu: 6400 for standard nodes, 26214 for large memory nodes 

# NOTE: specifying --ntasks and --mem-per-cpu instead of --nodes and --tasks-per-node
# might allow tasks to fit in on partial nodes, but there aren't many of these, and our
# coordinator thread uses a lot of memory, so we need to allocate as much memory as possible
# on that node. (Maybe this should go in the exclusive.q)

## 3 day max run time for community.q, kill.q, exclusive.q, and htc.q. 1 Hour max run time for sb.q 
## task-per-node x cpus-per-task should not typically exceed core count on an individual node 

## for output files: %A - filled with jobid. %a - filled with job arrayid

## All options and environment variables found on schedMD site: http://slurm.schedmd.com/sbatch.html 

# note: you should submit this by executing "sbatch runph.slurm"

# test version
# export runph_cmd='runph --solver-manager=phpyro --shutdown-pyro --pyro-port=$nsp --solver=cplexamp --scenario-solver-options="threads=1" --model-directory=. --instance-directory=inputs_tiny/pha_19 --default-rho=1000000000 --traceback --max-iterations=1000 --termdiff-threshold=0.001 --linearize-nonbinary-penalty-terms=7 --breakpoint-strategy=1 --bounds-cfgfile=pha_bounds_cfg.py --user-defined-extension=reporting_phextension --verbose'

# production version
# note: both of the settings below are out of a total of 20 tasks per node
export coordinator_reserved_slots=5  # number of slots to reserve for the coordinator processes on the first node
export workers_per_node=20  # number of slots to use for workers on each node (could be reduced to conserve RAM)
export runph_cmd='runph --phpyro-required-workers=15 --instance-directory=inputs/pha_15 --default-rho=10000000000 --termdiff-threshold=0.001 --linearize-nonbinary-penalty-terms=7 --breakpoint-strategy=1 --solver-manager=phpyro --shutdown-pyro --pyro-port=$nsp --solver=cplexamp --scenario-solver-options="threads=1" --model-directory=. --traceback --max-iterations=1000 --bounds-cfgfile=pha_bounds_cfg.py --user-defined-extension=reporting_phextension --verbose'

#export runph_cmd='runph --solver-manager=phpyro --shutdown-pyro --phpyro-required-workers=117 --pyro-port=$nsp --solver=cplexamp --scenario-solver-options="threads=1" --model-directory=. --instance-directory=inputs/pha_117 --default-rho=1000000000 --traceback --max-iterations=1000 --termdiff-threshold=0.001 --linearize-nonbinary-penalty-terms=7 --breakpoint-strategy=1 --bounds-cfgfile=pha_bounds_cfg.py --user-defined-extension=reporting_phextension --verbose'


# note: it appears that environment variables exported here will be inherited
# by all the tasks. We use this to pass the name server port and the main
# runph command to the worker script. This way all tasks know about the port
# and the worker script can be pretty generic. (All changes to define new runs
# occur in this .slurm file.)


export nsp=$(/home/mfripp/apps/next_port.py)
echo "Starting runph.slurm; will use port $nsp for pyro name server."

# show the runph command that will be run for this job
echo =============================== runph command ====================================
echo $runph_cmd
echo ================================================================================== 
# run the job
# note: we use stdbuf to switch to line buffering instead of default (4k?) buffering
# it's possible that the srun --unbuffered flag would help with this.
#srun stdbuf -oL -eL ./runph_slurm_share_proc
srun stdbuf -oL -eL ./runph_slurm_dedicated_coordinator
