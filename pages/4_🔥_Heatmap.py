import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(layout="wide")

st.title("Fish Records Heatmap")

# ---------------------------------------------------------
# URLs
# ---------------------------------------------------------

dem_filepath = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/data/Elevation_and_Bathymertry_Study_Area.tiff.tif"
)

fish_records_url = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/data/Fish_Records.geojson"
)

# ---------------------------------------------------------
# Create map
# ---------------------------------------------------------

m = leafmap.Map(
    center=[31, -88],
    zoom=8,
)

# ---------------------------------------------------------
# Bathymetry / elevation
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
# Fish records
# ---------------------------------------------------------

m.add_geojson(
    fish_records_url,
    layer_name="Fish Records",
)

# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

m.to_streamlit(height=700)
