import requests
import streamlit as st
import leafmap.foliumap as leafmap
import folium
from folium.plugins import HeatMap


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
# CREATE MAP
# =========================================================

m = leafmap.Map(
    center=[30.9, -88.3],
    zoom=8,
)


# =========================================================
# 1. ELEVATION & BATHYMETRY
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
    shown=True,
    opacity=0.75,
)


# =========================================================
# 2. LOAD FISH RECORDS
# =========================================================

response = requests.get(
    fish_records_url,
    timeout=60,
)

response.raise_for_status()

fish_geojson = response.json()


# =========================================================
# 3. FISH OBSERVATION DENSITY
# =========================================================

heatmap_points = []

for feature in fish_geojson["features"]:

    geometry = feature.get("geometry")

    if geometry and geometry.get("type") == "Point":

        longitude, latitude = geometry["coordinates"][:2]

        heatmap_points.append([
            latitude,
            longitude,
            1,
        ])


fish_heatmap = folium.FeatureGroup(
    name="Fish Observation Density",
    show=True,
)

HeatMap(
    heatmap_points,
    radius=18,
    blur=20,
    min_opacity=0.25,
    max_zoom=12,
).add_to(fish_heatmap)

fish_heatmap.add_to(m)


# =========================================================
# 4. INDIVIDUAL FISH RECORDS
# =========================================================

fish_records_layer = folium.FeatureGroup(
    name="Individual Fish Records",
    show=False,
)

folium.GeoJson(
    fish_geojson,
    name="Individual Fish Records",
    tooltip=folium.GeoJsonTooltip(
        fields=["Scientific Name"],
        aliases=["Species:"],
        localize=True,
        sticky=False,
    ),
).add_to(fish_records_layer)

fish_records_layer.add_to(m)


# =========================================================
# 5. STUDY AREA
# =========================================================

try:

    study_response = requests.get(
        study_area_url,
        timeout=60,
    )

    study_response.raise_for_status()

    study_area_geojson = study_response.json()

    study_area_layer = folium.FeatureGroup(
        name="Study Area",
        show=True,
    )

    folium.GeoJson(
        study_area_geojson,
        name="Study Area",
        style_function=lambda feature: {
            "color": "black",
            "weight": 3,
            "fillOpacity": 0,
        },
    ).add_to(study_area_layer)

    study_area_layer.add_to(m)

except Exception as e:

    st.warning(
        f"Study Area could not be loaded: {e}"
    )


# =========================================================
# 6. HEX BINS
# =========================================================

try:

    hex_response = requests.get(
        hex_bins_url,
        timeout=120,
    )

    hex_response.raise_for_status()

    hex_bins_geojson = hex_response.json()

    hex_bins_layer = folium.FeatureGroup(
        name="Hex Bins",
        show=False,
    )

    folium.GeoJson(
        hex_bins_geojson,
        name="Hex Bins",
        style_function=lambda feature: {
            "color": "black",
            "weight": 0.5,
            "fillColor": "transparent",
            "fillOpacity": 0.0,
        },
    ).add_to(hex_bins_layer)

    hex_bins_layer.add_to(m)

except Exception as e:

    st.warning(
        f"Hex Bins could not be loaded: {e}"
    )


# =========================================================
# DISPLAY
# =========================================================

m.to_streamlit(
    height=750,
    add_layer_control=True,
)
