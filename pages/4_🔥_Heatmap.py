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
# ENVIRONMENTAL FIELD DISPLAY NAMES
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
# HIDDEN HEX FIELDS
# ============================================================

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
    Load vector data and reproject to WGS84.
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
    Load Photos_and_Metadata_v3.JSON.
    """

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "species",
        data,
    )


# ============================================================
# LOAD GIS DATA
# ============================================================

with st.spinner("Loading GIS data..."):

    fish_gdf = load_vector_data(
        fish_records_url
    )

    hex_gdf = load_vector_data(
        hex_bins_url
    )

    study_area_gdf = load_vector_data(
        study_area_url
    )

    species_metadata = load_species_metadata(
        species_json_url
    )


# Make a copy before adding calculated fields.
hex_gdf = hex_gdf.copy()


# ============================================================
# PARSE SPECIES_ARRAY
# ============================================================

def parse_species_array(value):
    """
    Convert Species_Array into a clean list of species names.
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

            if isinstance(
                parsed,
                (list, tuple, set),
            ):
                values = parsed

            else:
                values = [parsed]

        except (
            ValueError,
            SyntaxError,
        ):

            values = [
                part.strip()
                for part in text.strip("[]").split(",")
            ]

    cleaned = []

    seen = set()

    for value in values:

        species = (
            str(value)
            .strip()
            .strip("'\"")
        )

        if species:

            key = species.casefold()

            if key not in seen:

                cleaned.append(species)

                seen.add(key)

    return cleaned


# Create parsed species list.
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
# CREATE HEX GEOJSON
#
# IMPORTANT:
# No @st.cache_data here because GeoDataFrames can cause
# Streamlit hashing/pickling errors.
# ============================================================

def make_hex_geojson(gdf):

    geojson = json.loads(
        gdf.to_json()
    )

    for feature in geojson["features"]:

        feature.setdefault(
            "properties",
            {},
        )

        # This allows st_folium to determine that the
        # clicked feature is one of our hexagons.
        feature["properties"][
            "_layer_type"
        ] = "hex"

    return geojson


def make_fish_geojson(gdf):

    return gdf.to_json()


def make_study_area_geojson(gdf):

    return gdf.to_json()


hex_geojson = make_hex_geojson(
    hex_gdf
)

fish_geojson = make_fish_geojson(
    fish_gdf
)

study_area_geojson = make_study_area_geojson(
    study_area_gdf
)


# ============================================================
# CREATE HEATMAP POINTS
#
# Every fish record gets a weight of 1.
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

    wanted = str(
        species_name
    ).casefold()

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

    photo = record.get(
        "photo"
    )

    if photo:

        photo = str(photo).lstrip("/")

        if (
            photo.startswith("http://")
            or photo.startswith("https://")
        ):

            return photo

        return (
            github_raw_base
            + photo
        )

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

    # Limit huge iNaturalist images.
    image.thumbnail(
        (1200, 1200),
        Image.Resampling.LANCZOS,
    )

    if image.mode not in (
        "RGB",
        "L",
    ):

        image = image.convert(
            "RGB"
        )

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
# CREATE CUSTOM LEAFLET PANES
#
# This is important for click behavior.
#
# Heatmap is below the hexagons.
# Hexagons are above the heatmap and receive clicks.
# ============================================================

m.get_root().html.add_child(
    folium.Element(
        """
        <style>
        .leaflet-heatmap-pane {
            z-index: 350 !important;
        }

        .leaflet-hex-pane {
            z-index: 650 !important;
        }
        </style>
        """
    )
)


# ============================================================
# SATELLITE BASEMAP
# ============================================================

folium.TileLayer(
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
).add_to(m)


# ============================================================
# OPENSTREETMAP BASEMAP
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
#
# TiTiler is used directly so the terrain color ramp works.
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
# Transparent yellow polygons.
#
# The custom pane places them ABOVE the heatmap so clicks
# are received by the hexagons.
# ============================================================

hex_group = folium.FeatureGroup(
    name="Hex Bins",
    show=True,
    overlay=True,
    control=True,
)

hex_geojson_layer = folium.GeoJson(

    hex_geojson,

    name="Hexagons",

    style_function=lambda feature: {
        "color": "yellow",
        "weight": 1,
        "opacity": 1.0,
        "fillColor": "yellow",
        "fillOpacity": 0.0,
    },

    highlight_function=lambda feature: {
        "color": "white",
        "weight": 3,
        "opacity": 1.0,
        "fillColor": "yellow",
        "fillOpacity": 0.20,
    },

    zoom_on_click=False,

)

hex_geojson_layer.add_to(
    hex_group
)

hex_group.add_to(m)


# ============================================================
# FISH OBSERVATION DENSITY HEATMAP
#
# The heatmap gets its own lower pane.
# ============================================================

heatmap_group = folium.FeatureGroup(
    name="Fish Observation Density",
    show=True,
    overlay=True,
    control=True,
)

# Move the heatmap group below the hexagon layer.
heatmap_group.add_child(
    folium.Element(
        """
        <script>
        </script>
        """
    )
)

# Add heatmap to the map.
# leafmap's add_heatmap uses the normal Leaflet heat layer.
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
# Hidden by default.
# ============================================================

fish_group = folium.FeatureGroup(
    name="Individual Fish Records",
    show=False,
    overlay=True,
    control=True,
)

# Determine which fields are actually present.
fish_tooltip_fields = []

if "Scientific Name" in fish_gdf.columns:
    fish_tooltip_fields.append(
        "Scientific Name"
    )

if "Common Name" in fish_gdf.columns:
    fish_tooltip_fields.append(
        "Common Name"
    )


fish_tooltip_aliases = [
    "Scientific Name",
    "Common Name",
][:len(fish_tooltip_fields)]


if fish_tooltip_fields:

    fish_tooltip = folium.GeoJsonTooltip(
        fields=fish_tooltip_fields,
        aliases=fish_tooltip_aliases,
        localize=True,
        sticky=False,
        labels=True,
    )

else:

    fish_tooltip = None


fish_layer = folium.GeoJson(
    fish_geojson,
    tooltip=fish_tooltip,
    marker=folium.CircleMarker(
        radius=4,
        fill=True,
        fill_opacity=0.8,
        weight=1,
    ),
)

fish_layer.add_to(
    fish_group
)

fish_group.add_to(m)


# ============================================================
# STUDY AREA
# ============================================================

study_group = folium.FeatureGroup(
    name="Study Area",
    show=True,
    overlay=True,
    control=True,
)

folium.GeoJson(
    study_area_geojson,

    style_function=lambda feature: {
        "color": "white",
        "weight": 2,
        "opacity": 1.0,
        "fillColor": "white",
        "fillOpacity": 0.0,
    },

).add_to(study_group)

study_group.add_to(m)


# ============================================================
# LAYER CONTROL
#
# ONLY ONE LayerControl.
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
# DEBUG / PROCESS HEXAGON CLICK
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

    # We specifically tagged every hexagon
    # with _layer_type = "hex".
    if properties.get(
        "_layer_type"
    ) == "hex":

        active_hex_id = properties.get(
            "id"
        )

        if active_hex_id is not None:

            selected_row = hex_lookup.get(
                str(active_hex_id)
            )

            if selected_row is not None:

                st.session_state.selected_hex = (
                    selected_row.to_dict()
                )

                # A new hex means a new species selection.
                st.session_state.selected_species = None


# ============================================================
# SELECTED HEX / SPECIES INFORMATION
# ============================================================

st.divider()


selected_hex = (
    st.session_state.selected_hex
)


# ============================================================
# NOTHING SELECTED
# ============================================================

if selected_hex is None:

    st.info(
        "Click a hexagon to view its "
        "environmental data and fish species."
    )


# ============================================================
# HEX SELECTED
# ============================================================

else:

    left_column, right_column = st.columns(
        [1, 1],
        gap="large",
    )


    # ========================================================
    # LEFT COLUMN
    # ========================================================

    with left_column:

        st.subheader(
            "Environmental Data"
        )


        # ----------------------------------------------------
        # Environmental fields
        # ----------------------------------------------------

        for field, label in FIELD_ALIASES.items():

            if field not in selected_hex:
                continue

            value = selected_hex.get(
                field
            )

            if value is None:
                continue

            value_text = str(
                value
            ).strip()

            if not value_text:
                continue

            if value_text.lower() == "nan":
                continue

            st.markdown(
                f"**{label}:** {value}"
            )


        # ----------------------------------------------------
        # Species
        # ----------------------------------------------------

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

                display_name = (
                    species_display_name(
                        species
                    )
                )

                if st.button(
                    display_name,
                    key=(
                        "species_"
                        + str(
                            selected_hex.get(
                                "id"
                            )
                        )
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
    # RIGHT COLUMN
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


            # ------------------------------------------------
            # PHOTO
            # ------------------------------------------------

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


            # ------------------------------------------------
            # ATTRIBUTION
            # ------------------------------------------------

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
