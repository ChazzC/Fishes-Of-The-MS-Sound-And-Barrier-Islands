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
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/data/"
    "Elevation_and_Bathymertry_Study_Area.tiff.tif"
)

fish_records_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/data/"
    "Fish_Records.geojson"
)

hex_bins_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/data/"
    "Hex_Bins.geojson"
)

study_area_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/data/"
    "StudyArea.geojson"
)

species_json_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
    "Photos_and_Metadata_v3.JSON"
)

github_raw_base = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
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


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data(show_spinner="Loading GIS data...")
def load_vector_data(url):
    """Load a vector dataset and convert it to WGS84."""
    gdf = gpd.read_file(url)

    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


@st.cache_data(show_spinner="Loading species metadata...")
def load_species_metadata(url):
    """Load species metadata JSON."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    return data.get("species", data)


fish_gdf = load_vector_data(fish_records_url)
hex_gdf = load_vector_data(hex_bins_url)
study_area_gdf = load_vector_data(study_area_url)
species_metadata = load_species_metadata(species_json_url)


# ============================================================
# SPECIES ARRAY PARSING
# ============================================================

def parse_species_array(value):
    """
    Convert Species_Array into a clean list of scientific names.
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


# ============================================================
# PREPROCESS HEX DATA
# ============================================================

# Parse Species_Array ONCE instead of every time a hex is clicked.
if "Species_List" not in hex_gdf.columns:

    hex_gdf["Species_List"] = hex_gdf["Species_Array"].apply(
        parse_species_array
    )


# Create a very fast dictionary lookup:
#
#     hex_lookup["1234"]
#
# instead of filtering the entire GeoDataFrame every click.

hex_lookup = {
    str(row["id"]): row
    for _, row in hex_gdf.iterrows()
}


# ============================================================
# CACHE GEOJSON SERIALIZATION
# ============================================================

@st.cache_data
def make_hex_geojson(gdf):

    geojson = json.loads(gdf.to_json())

    for feature in geojson["features"]:

        feature.setdefault("properties", {})

        # Used by st_folium to distinguish hex clicks
        # from other map layers.
        feature["properties"]["_layer_type"] = "hex"

    return geojson


@st.cache_data
def make_fish_geojson(gdf):

    return gdf.to_json()


@st.cache_data
def make_study_area_geojson(gdf):

    return gdf.to_json()


hex_geojson = make_hex_geojson(hex_gdf)
fish_geojson = make_fish_geojson(fish_gdf)
study_area_geojson = make_study_area_geojson(study_area_gdf)


# ============================================================
# CACHE HEATMAP POINT GENERATION
# ============================================================

@st.cache_data
def make_heatmap_points(gdf):

    points = []

    valid_geometries = gdf[gdf.geometry.notna()]

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


heatmap_points = make_heatmap_points(fish_gdf)


# ============================================================
# SPECIES HELPERS
# ============================================================

def find_species_metadata(species_name):

    wanted = species_name.casefold()

    for name, record in species_metadata.items():

        if str(name).casefold() == wanted:
            return record

    return None


def species_display_name(species_name):
    """
    Display:
        Scientific name, Common Name

    while retaining the scientific name internally.
    """

    record = find_species_metadata(species_name)

    if record:

        common_name = record.get("common_name")

        if common_name:
            return f"{species_name}, {common_name}"

    return species_name


def species_photo_url(record):

    if not record:
        return None

    photo = record.get("photo")

    if photo:

        photo = str(photo).lstrip("/")

        if photo.startswith("http://") or photo.startswith("https://"):
            return photo

        return github_raw_base + photo

    return record.get("source_image_url")


# ============================================================
# CACHE / RESIZE SPECIES PHOTOS
# ============================================================

@st.cache_data(
    max_entries=100,
    show_spinner=False,
)
def load_species_photo(url):
    """
    Download a species photo once, resize it for the web,
    and cache the resulting bytes.

    This prevents repeatedly downloading large original
    photographs during Streamlit reruns.
    """

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    image = Image.open(
        io.BytesIO(response.content)
    )

    # Keep enough resolution for the web application
    # without unnecessarily sending huge originals.
    image.thumbnail(
        (1200, 1200),
        Image.Resampling.LANCZOS,
    )

    # Convert formats such as PNG to RGB JPEG.
    if image.mode not in ("RGB", "L"):
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
    center=[30.9, -88.3],
    zoom=8,
    tiles=None,
)


# ============================================================
# BASEMAP — SATELLITE
# ============================================================

folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/"
        "ArcGIS/rest/services/World_Imagery/"
        "MapServer/tile/{z}/{y}/{x}"
    ),
    attr="Esri World Imagery",
    name="Satellite Imagery",
    overlay=False,
    control=True,
    show=True,
).add_to(m)


# ============================================================
# BASEMAP — OPEN STREET MAP
# ============================================================

folium.TileLayer(
    tiles="OpenStreetMap",
    name="OpenStreetMap",
    overlay=False,
    control=True,
    show=False,
).add_to(m)


# ============================================================
# ELEVATION / BATHYMETRY
# ============================================================

titiler_tiles = (
    "https://titiler.opengeos.org/cog/tiles/"
    "WebMercatorQuad/{z}/{x}/{y}.png"
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


# ============================================================
# HEX BINS
#
# IMPORTANT:
# Add hexes BEFORE the fish heatmap so the heatmap
# draws above them.
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

    # No popup.
    #
    # Environmental information and species information
    # are displayed in the Streamlit panel below the map.

).add_to(hex_group)


hex_group.add_to(m)


# ============================================================
# FISH OBSERVATION DENSITY
#
# Added AFTER hexes so it draws above them.
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
# ============================================================

fish_group = folium.FeatureGroup(
    name="Individual Fish Records",
    show=False,
)

fish_fields = [
    field
    for field in fish_gdf.columns
    if field not in {
        "geometry",
        "Species_List",
    }
]


folium.GeoJson(
    fish_geojson,

    tooltip=folium.GeoJsonTooltip(
        fields=fish_fields,
        aliases=fish_fields,
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
        "weight": 3,
        "fillColor": "white",
        "fillOpacity": 0.0,
    },

).add_to(study_group)


study_group.add_to(m)


# ============================================================
# LAYER CONTROL
# ============================================================

folium.LayerControl(
    position="topright",
    collapsed=False,
).add_to(m)


# ============================================================
# DISPLAY MAP
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
# PROCESS HEX CLICK
# ============================================================

active = None

if map_data:

    active = map_data.get(
        "last_active_drawing"
    )


if active:

    properties = active.get(
        "properties",
        {},
    )

    # Make sure the clicked object is a hex.
    if properties.get("_layer_type") == "hex":

        active_hex_id = properties.get("id")

        current_hex_id = None

        if st.session_state.selected_hex:

            current_hex_id = st.session_state.selected_hex.get(
                "id"
            )

        # Only update Streamlit state when the user
        # actually selected a different hex.
        if str(active_hex_id) != str(current_hex_id):

            # Fast dictionary lookup instead of filtering
            # the entire GeoDataFrame.
            selected_row = hex_lookup.get(
                str(active_hex_id)
            )

            if selected_row is not None:

                st.session_state.selected_hex = (
                    selected_row.to_dict()
                )

                st.session_state.selected_species = None


# ============================================================
# SELECTED HEX
# ============================================================

selected_hex = st.session_state.selected_hex


if selected_hex:

    # Species_List was prepared once when the data loaded.
    species = selected_hex.get(
        "Species_List",
        [],
    )

    st.divider()

    left, right = st.columns(
        [1, 1.4]
    )


    # ========================================================
    # LEFT PANEL — ENVIRONMENT + SPECIES
    # ========================================================

    with left:

        st.subheader(
            "Selected Hexagon"
        )


        # ----------------------------------------------------
        # Environmental information
        # ----------------------------------------------------

        for field, label in FIELD_ALIASES.items():

            value = selected_hex.get(
                field
            )

            if value is not None:

                value_text = str(
                    value
                ).strip()

                if value_text not in {
                    "",
                    "nan",
                    "None",
                }:

                    st.markdown(
                        f"**{label}:** {value}"
                    )


        # ----------------------------------------------------
        # Species
        # ----------------------------------------------------

        st.subheader(
            f"Fish Species ({len(species)})"
        )


        if species:

            for sp in species:

                display_name = species_display_name(
                    sp
                )

                if st.button(
                    display_name,
                    key=f"species_{sp}",
                    use_container_width=True,
                ):

                    st.session_state.selected_species = sp

        else:

            st.info(
                "No fish species are listed for this hexagon."
            )


    # ========================================================
    # RIGHT PANEL — SPECIES PHOTO
    # ========================================================

    with right:

        selected_species = (
            st.session_state.selected_species
        )


        if selected_species:

            record = find_species_metadata(
                selected_species
            )


            # Show scientific + common name here too.
            st.subheader(
                species_display_name(
                    selected_species
                )
            )


            if record:

                image_url = species_photo_url(
                    record
                )


                if image_url:

                    try:

                        photo_bytes = load_species_photo(
                            image_url
                        )

                        st.image(
                            photo_bytes,
                            use_container_width=True,
                        )

                    except Exception as e:

                        st.warning(
                            "The species photo could not be loaded: "
                            f"{e}"
                        )

                else:

                    st.info(
                        "No photo is available for this species."
                    )


                # ------------------------------------------------
                # Attribution
                # ------------------------------------------------

                if record.get("attribution"):

                    st.caption(
                        record["attribution"]
                    )


                if record.get("license"):

                    st.write(
                        f"**License:** "
                        f"{record['license']}"
                    )


                if record.get("author"):

                    st.write(
                        f"**Photographer / Author:** "
                        f"{record['author']}"
                    )


                if record.get("source_url"):

                    st.markdown(
                        "[View source on iNaturalist]"
                        f"({record['source_url']})"
                    )


            else:

                st.info(
                    "No photo metadata was found for this species."
                )


        else:

            st.info(
                "Click a species name to view its photo and attribution."
            )


else:

    st.info(
        "Click a hexagon to view its environmental data and fish species."
    )
