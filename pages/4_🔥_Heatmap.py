import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import folium
from folium.plugins import HeatMap

st.set_page_config(layout="wide")

st.title("Fish Records Heatmap")


# ---------------------------------------------------------
# DATA URLS
# ---------------------------------------------------------

dem_filepath = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
    "data/Elevation_and_Bathymertry_Study_Area.tiff.tif"
)

fish_records_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
    "data/Fish_Records.geojson"
)

hex_bins_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
    "data/Hex_Bins.geojson"
)

study_area_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
    "data/StudyArea.geojson"
)


# ---------------------------------------------------------
# LOAD VECTOR DATA
# ---------------------------------------------------------

@st.cache_data
def load_vector_data(url):
    gdf = gpd.read_file(url)

    # Leaflet/Folium expects geographic coordinates
    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


fish_gdf = load_vector_data(fish_records_url)
hex_gdf = load_vector_data(hex_bins_url)
study_area_gdf = load_vector_data(study_area_url)


# ---------------------------------------------------------
# CREATE MAP
# ---------------------------------------------------------

m = leafmap.Map(
    center=[30.9, -88.3],
    zoom=8,
    tiles=None,
)


# ---------------------------------------------------------
# BASEMAP
# ---------------------------------------------------------

# Esri World Imagery
folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}"
    ),
    attr="Esri World Imagery",
    name="Satellite Imagery",
    overlay=False,
    control=True,
    show=True,
).add_to(m)


# Optional OpenStreetMap basemap
folium.TileLayer(
    tiles="OpenStreetMap",
    name="OpenStreetMap",
    overlay=False,
    control=True,
    show=False,
).add_to(m)


# ---------------------------------------------------------
# ELEVATION / BATHYMETRY RASTER
# ---------------------------------------------------------

titiler_tiles = (
    "https://titiler.opengeos.org/cog/tiles/WebMercatorQuad/"
    "{z}/{x}/{y}.png"
    "?url=" + dem_filepath
    + "&bidx=1"
    + "&rescale=-19.212,57.122"
    + "&colormap_name=terrain"
)

folium.TileLayer(
    tiles=titiler_tiles,
    attr="TiTiler",
    name="Elevation & Bathymetry",
    overlay=True,
    control=True,
    show=False,
    opacity=0.75,
).add_to(m)

# ---------------------------------------------------------
# FISH OBSERVATION DENSITY HEATMAP
# ---------------------------------------------------------

heatmap_points = []

for geometry in fish_gdf.geometry:

    if geometry is not None and geometry.geom_type == "Point":
        heatmap_points.append([
            geometry.y,   # latitude
            geometry.x,   # longitude
            1             # one observation = one unit of density
        ])


# Make sure we actually have points
st.write(f"Fish observations used for heatmap: {len(heatmap_points):,}")


m.add_heatmap(
    heatmap_points,
    latitude="latitude",
    longitude="longitude",
    value="value",
    name="Fish Observation Density",
    radius=30,
    blur=25,
    min_opacity=0.35,
    max_zoom=12,
    gradient={
        0.20: "blue",
        0.40: "cyan",
        0.60: "lime",
        0.80: "yellow",
        1.00: "red",
    },
)


# ---------------------------------------------------------
# INDIVIDUAL FISH RECORDS
# ---------------------------------------------------------

fish_group = folium.FeatureGroup(
    name="Individual Fish Records",
    show=False,
)

folium.GeoJson(
    fish_gdf.to_json(),
    name="Individual Fish Records",
    tooltip=folium.GeoJsonTooltip(
        fields=[
            field
            for field in fish_gdf.columns
            if field != "geometry"
        ],
        aliases=[
            field
            for field in fish_gdf.columns
            if field != "geometry"
        ],
        localize=True,
        sticky=False,
    ),
    marker=folium.CircleMarker(
        radius=3,
        fill=True,
        fill_opacity=0.8,
        opacity=0.8,
    ),
).add_to(fish_group)

fish_group.add_to(m)


# ---------------------------------------------------------
# STUDY AREA
# ---------------------------------------------------------

study_group = folium.FeatureGroup(
    name="Study Area",
    show=True,
)

folium.GeoJson(
    study_area_gdf.to_json(),
    name="Study Area",
    style_function=lambda feature: {
        "color": "white",
        "weight": 3,
        "fillColor": "white",
        "fillOpacity": 0.0,
    },
).add_to(study_group)

study_group.add_to(m)


# ---------------------------------------------------------
# HEX BINS
# ---------------------------------------------------------

hex_group = folium.FeatureGroup(
    name="Hex Bins",
    show=True,
)

folium.GeoJson(
    hex_gdf.to_json(),
    name="Hex Bins",
    style_function=lambda feature: {
        "color": "yellow",
        "weight": 0.25,
        "fillColor": "yellow",
        "fillOpacity": 0.0,
    },
).add_to(hex_group)

hex_group.add_to(m)


# ---------------------------------------------------------
# LAYER CONTROL
# ---------------------------------------------------------

folium.LayerControl(
    position="topright",
    collapsed=False,
).add_to(m)


# ---------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------

m.to_streamlit(
    height=750,
    add_layer_control=False,
)
