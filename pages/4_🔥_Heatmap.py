# pages/4_🔥_Heatmap.py

import ast
import io
import json

import folium
import geopandas as gpd
import leafmap.foliumap as leafmap
import requests
import streamlit as st

from PIL import Image
from streamlit_folium import st_folium


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Fish Records Heatmap",
    layout="wide",
)

st.title("🐟 Fish Records Heatmap")


# ============================================================
# DATA URLS
# ============================================================

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

species_json_url = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/Photos_and_Metadata_v3.JSON"
)

github_raw_base = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/"
)


# ============================================================
# FIELD DISPLAY NAMES
# ============================================================

FIELD_ALIASES = {
    "max_elevation": "Maximum Elevation / Depth",
    "min_elevation": "Minimum Elevation / Depth",
    "dom_condition": "Dominant Bottom Condition",
    "hab_group": "Habitat Group",
    "SAL_HIGH": "Salinity (High)",
    "SAL_LOW": "Salinity (Low)",
    "areaname": "Area Name",
    "CSU_Descriptor": "CSU Description",
}


# Fields that should not be displayed to the user.
HIDDEN_HEX_FIELDS = {
    "fid",
    "id",
    "left",
    "top",
    "right",
    "bottom",
    "row_index",
    "col_index",
    "CSU_ID",
    "Species_Array",
    "Species_List",
    "_layer_type",
}


# ============================================================
# LOAD VECTOR DATA
# ============================================================

@st.cache_data
def load_vector_data(url):
    """
    Load a vector dataset and reproject it to WGS84.
    """
    gdf = gpd.read_file(url)

    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


# ============================================================
# LOAD SPECIES METADATA
# ============================================================

@st.cache_data
def load_species_metadata(url):
    """
    Load the species metadata JSON.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    return data.get("species", data)


# ============================================================
# LOAD DATA
# ============================================================

with st.spinner("Loading GIS data..."):

    fish_gdf = load_vector_data(fish_records_url)

    hex_gdf = load_vector_data(hex_bins_url)

    study_area_gdf = load_vector_data(study_area_url)

    species_metadata = load_species_metadata(species_json_url)


# Make a separate copy before modifying the GeoDataFrame.
# This avoids modifying the cached object in-place.
hex_gdf = hex_gdf.copy()


# ============================================================
# PARSE SPECIES_ARRAY
# ============================================================

def parse_species_array(value):
    """
    Convert the Species_Array field into a clean Python list.
    """

    if value is None:
        return []

    if isinstance(value, list):
        values = value

    else:

        text = str(value).strip()

        if not text or text.lower() in {
            "none",
            "null",
            "nan",
            "[]",
        }:
            return []

        try:

            parsed = ast.literal_eval(text)

            if isinstance(parsed, (list, tuple, set)):
                values = parsed
            else:
                values = [parsed]

        except (ValueError, SyntaxError):

            values = [
                part.strip()
                for part in text.strip("[]").split(",")
            ]

    cleaned = []

    seen = set()

    for value in values:

        species = str(value).strip().strip("'\"")

        if species:

            key = species.casefold()

            if key not in seen:

                cleaned.append(species)

                seen.add(key)

    return cleaned


# Add parsed species list.
if "Species_List" not in hex_gdf.columns:

    hex_gdf["Species_List"] = (
        hex_gdf["Species_Array"]
        .apply(parse_species_array)
    )


# ============================================================
# FAST HEX LOOKUP
# ============================================================

hex_lookup = {
    str(row["id"]): row
    for _, row in hex_gdf.iterrows()
}


# ============================================================
# GEOJSON CONVERSION
#
# IMPORTANT:
# These functions intentionally DO NOT use @st.cache_data.
#
# GeoDataFrames contain objects that Streamlit's caching system
# may not be able to hash/pickle.
# ============================================================

def make_hex_geojson(gdf):

    geojson = json.loads(
        gdf.to_json()
    )

    for feature in geojson["features"]:

        feature.setdefault(
            "properties",
            {}
        )

        feature["properties"]["_layer_type"] = "hex"

    return geojson


def make_fish_geojson(gdf):

    return gdf.to_json()


def make_study_area_geojson(gdf):

    return gdf.to_json()


hex_geojson = make_hex_geojson(hex_gdf)

fish_geojson = make_fish_geojson(fish_gdf)

study_area_geojson = make_study_area_geojson(
    study_area_gdf
)


# ============================================================
# CREATE HEATMAP POINTS
#
# Each fish record receives a weight of 1.
# ============================================================

def make_heatmap_points(gdf):

    points = []

    valid_geometries = gdf[
        gdf.geometry.notna()
    ]

    for geom in valid_geometries.geometry:

        try:

            point = geom.centroid

            points.append(
                [
                    float(point.y),
                    float(point.x),
                    1.0,
                ]
            )

        except Exception:

            continue

    return points


heatmap_points = make_heatmap_points(
    fish_gdf
)


# ============================================================
# SPECIES METADATA FUNCTIONS
# ============================================================

def find_species_metadata(species_name):

    wanted = species_name.casefold()

    for name, record in species_metadata.items():

        if str(name).casefold() == wanted:

            return record

    return None


def species_display_name(species_name):

    record = find_species_metadata(
        species_name
    )

    if record:

        common_name = record.get(
            "common_name"
        )

        if common_name:

            return (
                f"{species_name}, "
                f"{common_name}"
            )

    return species_name


def species_photo_url(record):

    if not record:

        return None

    photo = record.get("photo")

    if photo:

        photo = str(photo).lstrip("/")

        if (
            photo.startswith("http://")
            or photo.startswith("https://")
        ):

            return photo

        return github_raw_base + photo

    return record.get(
        "source_image_url"
    )


# ============================================================
# LOAD / RESIZE SPECIES PHOTO
# ============================================================

@st.cache_data(
    max_entries=100,
    show_spinner=False,
)
def load_species_photo(url):

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    image = Image.open(
        io.BytesIO(
            response.content
        )
    )

    # Keep the web application from trying to
    # display enormous original images.
    image.thumbnail(
        (1200, 1200),
        Image.Resampling.LANCZOS,
    )

    if image.mode not in (
        "RGB",
        "L",
    ):

        image = image.convert("RGB")

    output = io.BytesIO()

    image.save(
        output,
        format="JPEG",
        quality=88,
        optimize=True,
    )

    return output.getvalue()


# ============================================================
# SESSION STATE
# ============================================================

if "selected_hex" not in st.session_state:

    st.session_state.selected_hex = None


if "selected_species" not in st.session_state:

    st.session_state.selected_species = None


# ============================================================
# CREATE MAP
# ============================================================

m = leafmap.Map(
    center=[
        30.9,
        -88.3,
    ],
    zoom=8,
    tiles=None,
)


# ============================================================
# BASEMAP: SATELLITE
# ============================================================

satellite = folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/"
        "ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/"
        "{z}/{y}/{x}"
    ),
    attr="Esri World Imagery",
    name="Satellite Imagery",
    overlay=False,
    control=True,
    show=True,
)

satellite.add_to(m)


# ============================================================
# BASEMAP: OPENSTREETMAP
# ============================================================

osm = folium.TileLayer(
    tiles="OpenStreetMap",
    name="OpenStreetMap",
    overlay=False,
    control=True,
    show=False,
)

osm.add_to(m)


# ============================================================
# ELEVATION / BATHYMETRY
#
# We use TiTiler directly instead of leafmap's add_cog_layer()
# because the direct TiTiler tile URL correctly applies the
# terrain color ramp to this particular COG.
# ============================================================

titiler_tiles = (
    "https://titiler.opengeos.org/cog/tiles/"
    "WebMercatorQuad/{z}/{x}/{y}.png"
    "?url="
    + dem_filepath
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
    show=True,
    opacity=0.75,
).add_to(m)


# ============================================================
# HEX BINS
#
# Added BEFORE the heatmap so the fish heatmap appears above
# the hexagon outlines.
#
# Transparent fill, yellow outline.
# ============================================================

hex_group = folium.FeatureGroup(
    name="Hex Bins",
    show=True,
)

folium.GeoJson(
    hex_geojson,

    style_function=lambda feature: {
        "color": "yellow",
        "weight": 1,
        "fillColor": "yellow",
        "fillOpacity": 0.0,
    },

    highlight_function=lambda feature: {
        "color": "white",
        "weight": 3,
        "fillColor": "yellow",
        "fillOpacity": 0.15,
    },

).add_to(hex_group)

hex_group.add_to(m)


# ============================================================
# FISH OBSERVATION HEATMAP
# ============================================================

m.add_heatmap(
    heatmap_points,
    name="Fish Observation Density",
    radius=30,
    blur=25,
    min_opacity=0.35,
    max_zoom=12,
)


# ============================================================
# INDIVIDUAL FISH RECORDS
#
# Hidden by default because the heatmap is the primary display.
# The user can turn this layer on from the layer control.
# ============================================================

fish_group = folium.FeatureGroup(
    name="Individual Fish Records",
    show=False,
)

folium.GeoJson(
    fish_geojson,

    tooltip=folium.GeoJsonTooltip(
        fields=[
            field
            for field in [
                "Scientific Name",
                "Common Name",
            ]
            if field in fish_gdf.columns
        ],
        aliases=[
            "Scientific Name",
            "Common Name",
        ],
        localize=True,
        sticky=False,
        labels=True,
    ),

    marker=folium.CircleMarker(
        radius=4,
        fill=True,
        fill_opacity=0.8,
        weight=1,
    ),

).add_to(fish_group)

fish_group.add_to(m)


# ============================================================
# STUDY AREA
# ============================================================

study_group = folium.FeatureGroup(
    name="Study Area",
    show=True,
)

folium.GeoJson(
    study_area_geojson,

    style_function=lambda feature: {
        "color": "white",
        "weight": 2,
        "fillColor": "white",
        "fillOpacity": 0.0,
    },

).add_to(study_group)

study_group.add_to(m)


# ============================================================
# LAYER CONTROL
#
# IMPORTANT:
# Only ONE LayerControl is added.
# ============================================================

folium.LayerControl(
    position="topright",
    collapsed=False,
).add_to(m)


# ============================================================
# DISPLAY MAP
#
# st_folium is used instead of m.to_streamlit() because we need
# to receive clicks from the Leaflet map.
# ============================================================

map_data = st_folium(
    m,
    height=750,
    width=None,

    returned_objects=[
        "last_active_drawing",
        "last_object_clicked",
        "last_object_clicked_tooltip",
        "last_object_clicked_popup",
    ],
)


# ============================================================
# PROCESS HEXAGON CLICK
# ============================================================

active = (
    map_data.get("last_active_drawing")
    if map_data
    else None
)


if active:

    properties = active.get(
        "properties",
        {},
    )

    # Only react to clicks on our hexagon layer.
    if properties.get(
        "_layer_type"
    ) == "hex":

        active_hex_id = properties.get(
            "id"
        )

        current_hex_id = None

        if st.session_state.selected_hex:

            current_hex_id = (
                st.session_state.selected_hex
                .get("id")
            )

        # Only update Streamlit state when the
        # user actually selected a different hex.
        if str(active_hex_id) != str(
            current_hex_id
        ):

            selected_row = hex_lookup.get(
                str(active_hex_id)
            )

            if selected_row is not None:

                st.session_state.selected_hex = (
                    selected_row.to_dict()
                )

                # Selecting a new hex resets
                # the selected species.
                st.session_state.selected_species = None


# ============================================================
# SELECTED HEX / SPECIES PANEL
# ============================================================

st.divider()

selected_hex = (
    st.session_state.selected_hex
)


if selected_hex is not None:

    left_column, right_column = st.columns(
        [1, 1],
        gap="large",
    )


    # ========================================================
    # LEFT COLUMN — ENVIRONMENTAL DATA + SPECIES
    # ========================================================

    with left_column:

        st.subheader(
            "Environmental Data"
        )

        # Display environmental information.
        for field, label in FIELD_ALIASES.items():

            if field not in selected_hex:
                continue

            value = selected_hex.get(
                field
            )

            # Skip blank values.
            if (
                value is None
                or str(value).strip() == ""
                or str(value).lower() == "nan"
            ):
                continue

            st.markdown(
                f"**{label}:** {value}"
            )


        # ====================================================
        # SPECIES LIST
        # ====================================================

        species_list = selected_hex.get(
            "Species_List",
            [],
        )

        if not isinstance(
            species_list,
            list,
        ):

            species_list = parse_species_array(
                species_list
            )


        st.subheader(
            "Fish Species"
        )

        if species_list:

            st.caption(
                f"{len(species_list)} species "
                "recorded in this hexagon"
            )

            for species in species_list:

                display_name = species_display_name(
                    species
                )

                if st.button(
                    display_name,
                    key=(
                        "species_"
                        + str(selected_hex.get("id"))
                        + "_"
                        + species
                    ),
                    use_container_width=True,
                ):

                    st.session_state.selected_species = (
                        species
                    )

                    st.rerun()

        else:

            st.info(
                "No fish species are associated "
                "with this hexagon."
            )


    # ========================================================
    # RIGHT COLUMN — SPECIES PHOTO
    # ========================================================

    with right_column:

        selected_species = (
            st.session_state.selected_species
        )

        if selected_species:

            record = find_species_metadata(
                selected_species
            )

            st.subheader(
                species_display_name(
                    selected_species
                )
            )

            photo_url = species_photo_url(
                record
            )

            if photo_url:

                try:

                    image_bytes = (
                        load_species_photo(
                            photo_url
                        )
                    )

                    st.image(
                        image_bytes,
                        use_container_width=True,
                    )

                except Exception as e:

                    st.warning(
                        "The species photo could "
                        "not be loaded."
                    )

                    st.caption(
                        str(e)
                    )

            else:

                st.info(
                    "No photo is available for "
                    "this species."
                )


            # =================================================
            # PHOTO ATTRIBUTION
            # =================================================

            if record:

                attribution = record.get(
                    "attribution"
                )

                author = record.get(
                    "author"
                )

                license_name = record.get(
                    "license"
                )

                source_url = record.get(
                    "source_url"
                )

                if attribution:

                    st.markdown(
                        f"**Attribution:** "
                        f"{attribution}"
                    )

                elif author:

                    st.markdown(
                        f"**Author:** "
                        f"{author}"
                    )

                if license_name:

                    st.markdown(
                        f"**License:** "
                        f"{license_name}"
                    )

                if source_url:

                    st.markdown(
                        f"**Source:** "
                        f"[iNaturalist]({source_url})"
                    )

        else:

            st.info(
                "Click a species name to view "
                "its photo and attribution."
            )


else:

    st.info(
        "Click a hexagon to view its "
        "environmental data and fish species."
    )
