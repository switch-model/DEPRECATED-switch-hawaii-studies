#!/bin/sh

#SBATCH --job-name=runph_117

## testing
##SBATCH --partition=sb.q
##SBATCH --time=0-00:10:00

## production
#SBATCH --partition=community.q
#SBATCH --time=1-00:00:00
#SBATCH --mail-type=BEGIN,END,FAIL,REQUEUE,TIME_LIMIT_80
#SBATCH --mail-user=mfripp@hawaii.edu

## 3 day max run time for community.q, kill.q, exclusive.q, and htc.q. 1 Hour max run time for sb.q 
## task-per-node x cpus-per-task should not typically exceed core count on an individual node 
# NOTE: specifying --ntasks seems to work better than --nodes and --tasks-per-node 
# if you don't need them to run on the same node
##SBATCH --nodes=n
##SBATCH --tasks-per-node=n
#SBATCH --ntasks=118
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=6000 ## max of 6400 for standard nodes, max of 26214 for large memory nodes 

#SBATCH --error=%A.err ## %A - filled with jobid. %a - filled with job arrayid
#SBATCH --output=%A.out ## %A - filled with jobid. %a - filled with job arrayid

## All options and environment variables found on schedMD site: http://slurm.schedmd.com/sbatch.html 

# note: you should submit this by executing "sbatch runph.slurm"

# note: it appears that environment variables exported here will be inherited
# by all the tasks. We use this to pass the name server port and the main
# runph command to the worker script. This way we all tasks know about the port
# and the worker script can be pretty generic. (All changes to define new runs
# occur in this .slurm file.)

export runph_cmd='runph --solver-manager=phpyro --shutdown-pyro --pyro-port=$nsp --solver=cplexamp --scenario-solver-options="threads=1" --model-directory=. --instance-directory=inputs/pha --default-rho=100000000 --traceback --max-iterations=1000 --termdiff-threshold=0.001 --linearize-nonbinary-penalty-terms=7 --breakpoint-strategy=1 --bounds-cfgfile=pha_bounds_cfg.py --user-defined-extension=reporting_phextension --verbose'

export nsp=$(($RANDOM))
echo "Starting runph.slurm; will use port $nsp for pyro server."

# show the runph command that will be run for this job
echo =============================== runph command ====================================
echo $runph_cmd
echo ================================================================================== 
# run the job
# note: even with --unbuffered, some tasks seem to do their own buffering 
# (e.g. the name server output doesn't get into the .out file until the job finishes)
# so we also use stdbuf to switch to line buffering instead of default (4k?) buffering
srun stdbuf -oL -eL ./runph_slurm_share_proc --unbuffered --resv-ports $nsp
