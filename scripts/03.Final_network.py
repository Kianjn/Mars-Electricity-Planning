import pypsa
import pandas as pd

'''
With reasonable values to limit the Solar & Geothermal installed capacity, we can run the final optimization.
With this approach, we made sure that the power mix is balanced, diverse, and secure to unforseen circumstances.
'''
n = pypsa.Network("network.nc")

solar_capacity_limit = 70908.05 # Found from the first optimization run.
geothermal_capacity_limit = 12351.89 # Found from the second optimization run.

techs = pd.read_csv('final_techs.csv', index_col=0)
CF_hourly = pd.read_csv('CF_hourly.csv', index_col=0, parse_dates=True)

n.add(
    "Generator",
    "Solar PV",
    bus = "electricity",   
    carrier = 'solar',
    p_nom_extendable = True,      
    capital_cost = techs.at['solar', 'capital_cost'],           
    marginal_cost = techs.at['solar', 'marginal_cost'],            
    efficiency = 1,               # Efficiency (default = 1 for PV, since CF already accounted for the efficiency)
    p_max_pu = CF_hourly["CF"],   # Set the time-varying capacity factor
    lifetime = techs.at['solar', 'Lifetime (years)'],
    p_nom_max = solar_capacity_limit,
    overwrite = True
)

n.add(
    'Link',
    'Geothermal Power Plant',
    bus0 = 'geothermal',
    bus1 = 'electricity',
    bus2 = 'heat',
    carrier = 'geothermal',
    capital_cost = techs.at['geothermal', 'capital_cost'],
    marginal_cost = techs.at['geothermal', 'marginal_cost'],
    efficiency = techs.at['geothermal', 'Efficiency (electricity)'],
    efficiency2 = techs.at['geothermal', 'Efficiency (heat)'],
    p_nom_extendable = True,
    lifetime = techs.at['geothermal', 'Lifetime (years)'],
    p_nom_max = geothermal_capacity_limit,
    overwrite = True
)

n.export_to_netcdf("final_network.nc")