import pypsa
import pandas as pd
import matplotlib.pyplot as plt
plt.style.use('bmh')
import holoviews as hv
import hvplot.pandas

n = pypsa.Network("optimized_network.nc")

#print(n.loads)
#n.loads_t.p_set["power demand"].plot(figsize=(6, 2), ylabel="MW", title="Electricity Demand")

#TC = n.objective / 1e6 #Total cost
#print('Total Cost:', TC, 'M$')
#Total Cost: 891.439083016357 M$

def plot_dispatch(n, time) : #Visualizes the dispatch of power generation and load demand 
    p = (
        n.statistics.energy_balance(aggregate_time = False) #The energy balance for the network, not aggregated across time steps
        .groupby('carrier') #Groups the energy balance data by the carrier.
        .sum() #Sums the power generation contributions for each carrier across all time steps.
        .div(1e3) #Converts the power generation values from megawatts (MW) to gigawatts (GW).
        .drop('-') #Drops rows where the carrier is '-'.
        .T #Transposes the resulting DataFrame so that rows represent time steps, and columns represent carriers.
    )
    fig, ax = plt.subplots(figsize = (6, 3)) #Creates a new figure and axes for the plot with a size of 6 inches by 3 inches.

    color = p.columns.map(n.carriers.color) #Maps the carrier types to their respective colors.

    p.where(p > 0).loc[time].plot.area( #Filters the DataFrame to include only positive values of power generation.
        ax = ax,
        linewidth = 0,
        color = color
    ) #Creates a stacked area plot for positive generation contributions, using the carrier-specific colors.

    charge = p.where(p < 0).dropna( #Filters the DataFrame to include only negative values, which represent power consumption or losses
        how = 'all', axis = 1 #Removes any columns (carriers) that do not have negative values in the selected time step.
    ).loc[time] 

    if not charge.empty :
        charge.plot.area(
            ax = ax,
            linewidth = 0,
            color = charge.columns.map(n.carriers.color)
        )

    n.loads_t.p_set.sum(axis = 1).loc[time].div(1e3).plot(ax = ax, c = 'k')

    #plt.legend(loc = (1.05, 0))
    ax.set_ylabel('GW')
    ax.set_ylim(-50, 50)

#plot_dispatch(n, '2050-07')

'''
The function calculates the total system cost.
n.statistics.capex(): Calculates the capital expenditure (CAPEX) for each component of the network. 
n.statistics.opex(): Calculates the operational expenditure (OPEX), which is the recurring cost of running the energy system.
pd.concat(..., axis=1): Concatenates the two DataFrames (capex and opex) along columns (i.e., side-by-side).
	•	The resulting DataFrame contains both CAPEX and OPEX for each component at each time step.

tsc.sum(axis=1): Sums the values across the columns (i.e., adds up CAPEX and OPEX for each time step).
.droplevel(0): Removes the first level of the index.
.div(1e9): Divides the total cost by  10^9  to convert the cost from currency units (e.g., EUR, USD) to billions.
.round(2): Rounds the resulting values to 2 decimal places for better readability.
'''
def system_cost(n) :
    tsc = pd.concat([n.statistics.capex(), n.statistics.opex()], axis = 1)
    return tsc.sum(axis = 1).droplevel(0).div(1e9).round(2)

system_cost(n)
#system_cost(n).plot.pie(figsize = (2, 2))

# Sum total energy generated (MWh) over the entire time period
gen_energy = n.generators_t.p.sum().groupby(n.generators.carrier).sum()
link_energy = n.links_t.p0.sum().groupby(n.links.carrier).sum()

# Combine generators and links
energy_mix = pd.concat([gen_energy, link_energy]).groupby(level=0).sum()

# Define a function to format labels (percentage + energy value)
def autopct_format(pct, all_values):
    absolute = int(round(pct/100. * sum(all_values)))  # Convert % to actual value
    return f"{pct:.1f}%\n({absolute} MWh)"  # Show both % and MWh

# Plot pie chart
plt.figure(figsize=(8, 8))
plt.pie(
    energy_mix, 
    labels=energy_mix.index, 
    autopct=lambda pct: autopct_format(pct, energy_mix),  # Use custom function
    startangle=140,
    colors=plt.cm.Paired.colors,  # Use a color map for better visualization
    wedgeprops={'edgecolor': 'black'}  # Add black edges for clarity
)

# Title
plt.title("Energy Mix from Generators & Links")

# Show the plot
plt.show()
