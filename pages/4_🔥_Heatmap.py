import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd


st.set_page_config(layout="wide")

st.title("Fish Records Heatmap")


# =========================================================
# DATA URLS
# =========================================================

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

hex_bins_url = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/data/Hex_Bins.geojson"
)

study_area_url = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/data/StudyArea.geojson"
)


# =========================================================
# LOAD VECTOR DATA
# =========================================================

@st.cache_data
def load_vector_data(url):

    gdf = gpd.read_file(url)

    # Convert everything to WGS84 for Leaflet
    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


fish_gdf = load_vector_data(fish_records_url)
study_area_gdf = load_vector_data(study_area_url)
hex_gdf = load_vector_data(hex_bins_url)


# =========================================================
# CREATE MAP
# =========================================================

m = leafmap.Map(
    center=[30.9, -88.3],
    zoom=8,
    tiles=None,
)


# =========================================================
# BASEMAP
# =========================================================

m.add_basemap(
    "Esri.WorldImagery",
    show=True,
)


# =========================================================
# ELEVATION & BATHYMETRY
# =========================================================

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
    overlay=True,
    control=True,
    shown=False,
    opacity=0.75,
)


# =========================================================
# FISH OBSERVATION DENSITY
# =========================================================

heatmap_points = []

for geometry in fish_gdf.geometry:

    if geometry is not None and geometry.geom_type == "Point":

        heatmap_points.append(
            [
                geometry.y,
                geometry.x,
                1,
            ]
        )


m.add_heatmap(
    heatmap_points,
    name="Fish Observation Density",
    radius=18,
)


# =========================================================
# INDIVIDUAL FISH RECORDS
# =========================================================

m.add_gdf(
    fish_gdf,
    layer_name="Individual Fish Records",
    zoom_to_layer=False,
    info_mode="on_hover",
    opacity=0.8,
    style={
        "color": "#0066cc",
        "fillColor": "#0066cc",
        "radius": 4,
    },
)


# =========================================================
# STUDY AREA
# =========================================================

m.add_gdf(
    study_area_gdf,
    layer_name="Study Area",
    zoom_to_layer=False,
    info_mode="on_click",
    style={
        "color": "#ffffff",
        "weight": 3,
        "fillColor": "#ffffff",
        "fillOpacity": 0.0,
    },
)


# =========================================================
# HEX BINS
# =========================================================

m.add_gdf(
    hex_gdf,
    layer_name="Hex Bins",
    zoom_to_layer=False,
    info_mode="on_click",
    opacity=0.7,
    style={
        "color": "#ffff00",
        "weight": 1,
        "fillColor": "#ffff00",
        "fillOpacity": 0.0,
    },
)


# =========================================================
# LAYER CONTROL
# =========================================================

m.add_layer_control()


# =========================================================
# DISPLAY
# =========================================================

m.to_streamlit(
    height=750,
)
