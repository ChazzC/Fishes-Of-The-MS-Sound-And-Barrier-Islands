import streamlit as st
import leafmap.foliumap as leafmap
import pandas as pd

st.set_page_config(layout="wide")

st.title("Heatmap")

# ---------------------------------------------------------
# Data
# ---------------------------------------------------------

filepath = (
    "https://raw.githubusercontent.com/"
    "giswqs/leafmap/master/examples/data/us_cities.csv"
)

dem_filepath = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/data/Elevation_and_Bathymertry_Study_Area.tiff.tif"
)

# ---------------------------------------------------------
# Create map
# ---------------------------------------------------------

m = leafmap.Map(
    center=[31, -88],
    zoom=8,
)

# ---------------------------------------------------------
# TiTiler COG layer
# ---------------------------------------------------------

titiler_tiles = (
    "https://titiler.opengeos.org/cog/tiles/WebMercatorQuad/"
    "{z}/{x}/{y}.png"
    "?url=" + dem_filepath
    + "&bidx=1"
    + "&rescale=-19.212,57.122"
    + "&colormap_name=terrain"
)

m.add_tile_layer(
    url=titiler_tiles,
    name="Elevation & Bathymetry",
    attribution="TiTiler",
)

# ---------------------------------------------------------
# Heatmap
# ---------------------------------------------------------

m.add_heatmap(
    filepath,
    latitude="latitude",
    longitude="longitude",
    value="pop_max",
    name="Heat map",
    radius=20,
)

# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

m.to_streamlit(height=700)
