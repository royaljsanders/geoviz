#!/usr/bin/env python

import sys
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Point, LineString

# Parse command-line args for resolution
# e.g. python mvp_animation.py 1920 1080
if len(sys.argv) == 3:
    width_px = int(sys.argv[1])
    height_px = int(sys.argv[2])
else:
    # default
    width_px = 640
    height_px = 480

# Choose a DPI (dots per inch)
DPI = 100  # you can tweak this as needed

# Convert pixel dims to inches for matplotlib
width_in = width_px / DPI
height_in = height_px / DPI
# 1. LOAD CITY CSV
city_df = pd.read_csv('../data/city_pop_chicago.csv')

# City lat/lon is constant in the CSV, so let's just extract them from one row
city_lat = city_df['lat'].iloc[0]
city_lon = city_df['lon'].iloc[0]

# Convert "year" to numeric if needed
city_df['year'] = city_df['year'].astype(int)
city_df.set_index('year', inplace=True)

# 2. INTERPOLATE POPULATION FOR EVERY YEAR
years = range(1850, 1951)  # 1850 -> 1950 inclusive
# Reindex the dataframe so it includes all years, filling population by interpolation
city_df_full = city_df.reindex(years)
city_df_full['population'] = city_df_full['population'].interpolate(method='linear')

# We'll create a simple GeoDataFrame for the city point
# We'll do that once, but population is read from city_df_full on each iteration
city_point = gpd.GeoDataFrame({'city': ['Chicago'], 
                               'geometry': [Point(city_lon, city_lat)]},
                              crs="EPSG:4326")

# 3. LOAD THE NATIONAL ROAD GEOJSON
roads_gdf = gpd.read_file('../data/national_road.geojson')  # each segment

##################################################
# HELPER FUNCTION: Returns fraction of a line "built" by a given year.
# If year < start_year, fraction=0 (not built)
# If year > end_year, fraction=1 (fully built)
# If in between, fraction is proportion.
##################################################
def get_build_fraction(year, start, end):
    if year < start:
        return 0.0
    elif year > end:
        return 1.0
    else:
        # linear fraction for partial years
        return (year - start) / float(end - start)

# 4. LOOP OVER YEARS, GENERATE PNG FRAMES
import os
os.makedirs('../outputs/frames', exist_ok=True)

for current_year in years:
    print(current_year)
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=DPI)
    
    # --- PLOT ROAD SEGMENTS ---
    # For each segment, we see how much is built by current_year
    for idx, row in roads_gdf.iterrows():
        start_y = row['start_year']
        end_y = row['end_year']
        frac = get_build_fraction(current_year, start_y, end_y)
        
        line_geom = row['geometry']  # a LineString
        # If frac == 0, skip plotting (not built yet)
        # If frac == 1, plot entire line
        # If 0 < frac < 1, we plot partial line from start to fraction
        if frac > 0:
            # Convert line_geom to shapely, get partial
            # Easiest approach: linear referencing or segmentize approach
            # We'll do a simple approach using line_geom.interpolate for fraction
            line_length = line_geom.length
            partial_length = frac * line_length
            partial_line = line_geom.interpolate(partial_length, normalized=False)
            
            if isinstance(line_geom, LineString):
                # Construct a new line from the start to partial_line
                # We'll handle it by stepping or by shapely "substring" approach
                # For a minimal example, let's do a 2-point line from the start to partial point
                # (Better approaches exist for multi-vertex lines.)
                
                coords = list(line_geom.coords)
                start_coord = coords[0]
                # partial_line is a POINT, we find its coords
                partial_coord = (partial_line.x, partial_line.y)
                
                if frac < 1.0:
                    # create a new line with just 2 coords
                    partial_geom = LineString([start_coord, partial_coord])
                else:
                    partial_geom = line_geom  # fully built
            else:
                partial_geom = line_geom  # if not a simple linestring
            
            # Plot partial_geom
            gpd.GeoSeries([partial_geom], crs=roads_gdf.crs).plot(
                ax=ax, color='red', linewidth=2
            )
    
    # --- PLOT CITY POINT ---
    population = city_df_full.loc[current_year, 'population']
    # Dot size can be, for example, proportional to sqrt of population
    # scale factor is arbitrary for visualization
    dot_size = (population ** 0.5) / 100  # adjust to taste
    
    city_point.plot(ax=ax, color='blue', markersize=dot_size*50)  # markersize scale
    
    # Add a label
    ax.text(city_lon+0.3, city_lat, 
            f"Chicago {current_year}\nPop: {int(population):,}", 
            fontsize=8, color='blue')
    
    # --- MAP EXTENT ---
    # We can set a fixed extent or auto
    # Let's just set a broad extent that shows from MD to IL, for example
    ax.set_xlim(-90, -77) 
    ax.set_ylim(38, 43) # where did we get this number?
    
    ax.set_title(f"Year: {current_year}")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    
    # Save figure
    frame_index = current_year - 1850
    frame_path = f"../outputs/frames/frame_{frame_index}.png"
    plt.savefig(frame_path)
    plt.close(fig)

print("Frames generated in outputs/frames/. Use ffmpeg (or similar) to create a video.")
