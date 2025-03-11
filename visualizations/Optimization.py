import pypsa
import pandas as pd

n = pypsa.Network("final_network.nc")
n.optimize(solver_name="gurobi")
n.export_to_netcdf("optimized_network.nc")
