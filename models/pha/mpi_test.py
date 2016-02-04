import sys
from mpi4py import MPI
mpi_comm = MPI.COMM_WORLD
mpi_rank = mpi_comm.Get_rank()

arg = sys.argv[1]

print "gathering {}".format(arg)
data = mpi_comm.gather(arg)
print "rank={}, data={}".format(mpi_rank, data)