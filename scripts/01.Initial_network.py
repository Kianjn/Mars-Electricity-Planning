import pypsa
import pandas as pd
import numpy as np
import csv
import math
from datetime import datetime, timedelta

n = pypsa.Network()

n.add('Bus', 'electricity')
n.add('Bus', 'heat')
n.add('Bus', 'nuclear')
n.add('Bus', 'geothermal')

'''
In this section, we create the demand profiles based on our assumptions.
'''
start_year = 2040
end_year = 2060  # exclusive upper bound for iteration, will go until end of 2059
hours_total = 0

# Helper functions
def linear_interpolate(x, x0, x1, y0, y1):
    # Given x between x0 and x1, interpolate linearly between y0 and y1
    return y0 + (y1 - y0)*((x - x0)/(x1 - x0))

def get_electricity_baseline(year):
    # Electricity baseline transitions:
    # 2040 start ~50kW -> 2044 end ~100kW linearly
    # 2045 start ~500kW -> 2059 end ~20,000kW linearly
    if 2040 <= year <= 2044:
        # Interpolate from 50kW (2040) to 100kW (2044)
        return linear_interpolate(year, 2040, 2044, 50, 100)
    elif 2045 <= year <= 2059:
        # Interpolate from 500kW (2045) to 20,000kW (2059)
        return linear_interpolate(year, 2045, 2059, 500, 20000)
    else:
        # Before 2040 or after 2059 (not in our range), just return something neutral
        return 50

def get_heat_baseline(year):
    # Heat baseline transitions similarly:
    # 2040–2044: ~100 kW
    # 2045–2059: 500 kW to 20,000 kW
    if 2040 <= year <= 2044:
        return 100
    elif 2045 <= year <= 2059:
        return linear_interpolate(year, 2045, 2059, 500, 20000)
    else:
        return 100

def daily_profile_factor_electricity(hour):
    # Simple profile:
    # 0–5: 0.8 baseline
    # 6–10: ramp 1.0 to 1.2
    # 11–17: 1.0
    # 18–21: 1.2
    # 22–23: 1.0
    if 0 <= hour <= 5:
        return 0.8
    elif 6 <= hour <= 10:
        # linear ramp from 1.0 at 6 to 1.2 at 10
        return 1.0 + (0.2 * (hour - 6) / (10 - 6))
    elif 11 <= hour <= 17:
        return 1.0
    elif 18 <= hour <= 21:
        return 1.2
    else: # 22,23
        return 1.0

def daily_profile_factor_heat(hour):
    # Night is colder: higher factor
    # 0–5: +20% (1.2)
    # 6–10: baseline (1.0)
    # 11–17: -10% (0.9)
    # 18–21: baseline (1.0)
    # 22–23: baseline (1.0)
    if 0 <= hour <= 5:
        return 1.2
    elif 6 <= hour <= 10:
        return 1.0
    elif 11 <= hour <= 17:
        return 0.9
    elif 18 <= hour <= 21:
        return 1.0
    else:
        return 1.0

# Generate data
start_date = datetime(start_year, 1, 1, 0, 0)
end_date = datetime(end_year, 1, 1, 0, 0)  # end at start of 2060 (so last full year is 2059)
delta = timedelta(hours=1)

rows = []
t = 0
current = start_date
while current < end_date:
    year = current.year
    month = current.month
    hour_of_day = current.hour
    
    # Get baselines
    e_baseline = get_electricity_baseline(year)
    h_baseline = get_heat_baseline(year)
    
    # Apply daily profiles
    e_daily = daily_profile_factor_electricity(hour_of_day)
    h_daily = daily_profile_factor_heat(hour_of_day)
    
    # Final demands
    e_demand = e_baseline * e_daily
    h_demand = h_baseline * h_daily
    
    rows.append([t, round(e_demand,2), round(h_demand,2)])
    
    current += delta
    t += 1

# Write to CSV
with open('mars_energy_demands_2040_2060.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["timestep", "electricity_kW", "heat_kW"])
    writer.writerows(rows)

print("CSV file generated.")

snapshots = pd.date_range(start="2040-01-01 00:00",
                          end="2059-12-31 23:00",
                          freq="h")
n.set_snapshots(snapshots)

url = 'mars_energy_demands_2040_2060.csv'
demand = pd.read_csv(url)

elec = demand["electricity_kW"]
heat = demand["heat_kW"]

# Reindex to match snapshots
elec.index = snapshots
heat.index = snapshots

n.add(
    'Load',
    'power demand',
    bus = 'electricity',
    p_set = elec,
    overwrite = True
)

n.add(
    'Load',
    'heat demand',
    bus = 'heat',
    p_set = heat,
    overwrite = True
)

carriers = [
    'solar', 'nuclear', 'geothermal', 'heater', 'hydrogen storage', 'battery storage'
]
colors = ['gold', 'dodgerblue', 'brown', 'green', 'indianred', 'magenta']

n.add(
    'Carrier',
    carriers,
    color = colors,
)

url2 = '/Users/kian/GitHub/Mars-Electricity-Planning/data/Techs.csv'
techs = pd.read_csv(url2, index_col = 0)

# Define annuity
def annuity(r, n) :
    return r / (1 - 1 / (1 +r) ** n )

discount_rate = 0.06
techs['annuity'] = annuity(discount_rate, techs['Lifetime (years)'])

# Calculate capital cost 
techs['capital_cost'] = (techs['annuity'] + techs['Fixed Cost ($/kW.year)'] / 100) * techs['Investment Cost ($/kW)']

# Marginal costs for electricity and heat
techs['marginal_cost_elec'] = techs['Variable Cost ($/kWh)'] + techs['Fuel Cost ($/kWh)'] / techs['Efficiency (electricity)']
techs['marginal_cost_heat'] = techs['Variable Cost ($/kWh)'] + techs['Fuel Cost ($/kWh)'] / techs['Efficiency (heat)']

# Calculate marginal cost based on the presence of efficiencies
techs['marginal_cost'] = np.where(
    (techs['Efficiency (electricity)'] > 0) & (techs['Efficiency (heat)'] > 0),
    # Cogeneration: Weighted average
    (techs['Efficiency (electricity)'] / (techs['Efficiency (electricity)'] + techs['Efficiency (heat)'])) * techs['marginal_cost_elec'] +
    (techs['Efficiency (heat)'] / (techs['Efficiency (electricity)'] + techs['Efficiency (heat)'])) * techs['marginal_cost_heat'],
    np.where(
        techs['Efficiency (electricity)'] > 0,
        # Electricity-only technologies
        techs['marginal_cost_elec'],
        # Heat-only technologies
        techs['marginal_cost_heat']
    )
)

techs.to_csv('final_techs.csv', index=True)

n.add("Generator",
      name="Nuclear_Fuel_Supply",
      bus="nuclear",
      carrier="nuclear",
      p_nom=1e9,           
      marginal_cost=0
)       

n.add("Generator",
      name="Geothermal_Heat_Supply",
      bus="geothermal",
      carrier="geothermal",
      p_nom=1e9,             
      marginal_cost=0
)

n.add(
    'Link',
    'Nuclear Power Plant + SuperCritical CO2',
    bus0 = 'nuclear',
    bus1 = 'electricity',
    bus2 = 'heat',
    carrier = 'nuclear',
    capital_cost = techs.at['nuclear', 'capital_cost'],
    marginal_cost = techs.at['nuclear', 'marginal_cost'],
    efficiency = techs.at['nuclear', 'Efficiency (electricity)'],
    efficiency2 = techs.at['nuclear', 'Efficiency (heat)'],
    p_nom_extendable = True,
    lifetime = techs.at['nuclear', 'Lifetime (years)'],
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
    overwrite = True
)

n.add(
    'Link',
    'Regenerative Heater',
    bus0 = 'electricity',
    bus1 = 'heat',
    carrier = 'heater',
    capital_cost = techs.at['heater', 'capital_cost'],
    marginal_cost = techs.at['heater', 'marginal_cost'],
    efficiency = techs.at['heater', 'Efficiency (heat)'],
    p_nom_extendable = True,
    lifetime = techs.at['heater', 'Lifetime (years)'],
    overwrite = True
)

# Monthly Capacity Factors (0.2–0.3 range)
CF = [0.30, 0.29, 0.28, 0.27, 0.26, 0.25, 
      0.24, 0.23, 0.24, 0.25, 0.27, 0.29]

# Hourly date range
hourly_range = pd.date_range(start="2040-01-01", end="2059-12-31 23:00", freq="h")

# Create a DataFrame to hold hourly CF
hourly_cf = pd.DataFrame(index = hourly_range, columns=["CF"])

# Define daylight parameters (for simplicity)
sunrise = 6   # 6 AM
sunset = 18   # 6 PM
daylength = sunset - sunrise  # 12 hours of "daylight"
hours = np.arange(24)         # Hour indices

# Daily shape: sine curve between sunrise and sunset
def daily_solar_shape(hour):
    if sunrise <= hour < sunset:
        x = (hour - sunrise) / daylength
        return max(0, np.sin(np.pi * x))
    else:
        return 0.0

# Compute the unscaled shape for a single day
unscaled_shape = np.array([daily_solar_shape(h) for h in hours])
daily_avg_unscaled = unscaled_shape.mean()  # ~0.3183

# Assign the monthly CF
months = hourly_cf.index.month

for month in range(1, 13):
    month_cf = CF[month - 1]
    scaling_factor = month_cf / daily_avg_unscaled
    
    # Since month_cf <= 0.30 and daily_avg_unscaled ~0.3183,
    # scaling_factor ≤ 0.30/0.3183 ≈ 0.94 < 1, ensuring peak < 1.
    
    month_mask = (months == month)
    monthly_hours = hourly_cf.index[month_mask]
    num_hours_in_month = len(monthly_hours)
    
    # Repeat the unscaled_shape to match num_hours_in_month
    repeated_pattern = np.tile(unscaled_shape, int(np.ceil(num_hours_in_month / 24)))[0:num_hours_in_month]
    
    # Apply scaling
    scaled_values = repeated_pattern * scaling_factor
    
    hourly_cf.loc[month_mask, "CF"] = scaled_values

# Fill any NaNs with 0
CF_hourly = hourly_cf.fillna(0.0)
CF_hourly.index = snapshots

CF_hourly.to_csv('CF_hourly.csv', index=True)

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
    overwrite = True
)

n.add(
    'StorageUnit',
    'BESS', 
    bus = 'electricity',
    carrier = 'battery storage',
    max_hours = 6, 
    capital_cost = techs.at['battery', 'capital_cost'],
    efficiency = techs.at['battery', 'Efficiency (electricity)'], #Round-trip efficiency
    p_nom_extendable = True,
    e_cyclic = True,
    standing_loss = 0.001,  # 0.1% daily loss for BESS
    cyclic_state_of_charge = True #This allows the state of charge to be cyclic, meaning the battery’s state can reset at the beginning of each time period
)


n.add(
    'StorageUnit',
    'Hydrogen Storage', 
    bus = 'electricity',
    carrier = 'hydrogen storage',
    max_hours = 168, 
    capital_cost = techs.at['hydrogen', 'capital_cost'],
    efficiency = techs.at['hydrogen', 'Efficiency (electricity)'], #Round-trip efficiency
    p_nom_extendable = True,
    e_cyclic=True,
    standing_loss = 0.005,  # 0.5% daily loss
    cyclic_state_of_charge = True #This allows the state of charge to be cyclic, meaning the battery’s state can reset at the beginning of each time period
)

n.export_to_netcdf("network.nc")