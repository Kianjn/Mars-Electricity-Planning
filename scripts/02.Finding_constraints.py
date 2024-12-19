import pypsa
import pandas as pd

# Load the initial network
n = pypsa.Network("network.nc")

'''
To find a logical value for the Solar PV capacity limit.
'''
# Run initial optimization to get total generation potential
print("Running initial optimization without constraints...")
initial_result = n.optimize(solver_name="gurobi", log_fn="initial_solver_log.txt")

# Sum the optimal capacities of solar generators
solar_installed_capacity = n.generators.loc[n.generators.carrier == "solar", "p_nom_opt"].sum()
print(f"Installed Solar Capacity: {solar_installed_capacity:.2f} MW")

# Calculate 40% of the installed solar capacity
solar_capacity_limit = 0.4 * solar_installed_capacity
print(f"Solar Capacity Limit (40%): {solar_capacity_limit:.2f} MW")

# Step 4: Remove previous solar generators
n = pypsa.Network("network.nc")
n.generators = n.generators[n.generators.carrier != "solar"]

# Add a new solar generator with the `p_nom_max` constraint
n.add("Generator",
      name="Solar PV",
      bus="electricity",
      carrier="solar",
      p_nom_extendable=True,
      p_nom_max=solar_capacity_limit)

'''
To find a logical value for the Geothermal Power Plant capacity limit.
'''
# second optimization, with the solar capacity constraint
print("Running final optimization with solar capacity constraint...")
final_result = n.optimize(solver_name="gurobi", log_fn="final_solver_log.txt")

# Sum the optimal capacities of geothermal power plants
geothermal_installed_capacity = n.links.loc[n.links.carrier == "geothermal", "p_nom_opt"].sum()
print(f"Installed Geothermal Capacity: {geothermal_installed_capacity:.2f} MW")

# Calculate 50% of the installed solar capacity
geothermal_capacity_limit = 0.5 * geothermal_installed_capacity
print(f"Geothermal Capacity Limit (50%): {geothermal_capacity_limit:.2f} MW")

solar_capacity_limit = 70908.05 # Found from the first optimization run.
geothermal_capacity_limit = 12351.89 # Found from the second optimization run.