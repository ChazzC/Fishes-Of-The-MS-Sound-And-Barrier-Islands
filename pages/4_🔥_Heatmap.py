import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import requests
import json
import ast


st.set_page_config(layout="wide")

st.title("Fish Records Heatmap")


# ---------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------

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

species_json_url = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
    "Photos_and_Metadata_v3.JSON"
)

github_raw_base = (
    "https://raw.githubusercontent.com/ChazzC/"
    "Fishes-Of-The-MS-Sound-And-Barrier-Islands/main/"
)


# ---------------------------------------------------------------------
# Hexagon field labels
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------

@st.cache_data
def load_vector_data(url):
    gdf = gpd.read_file(url)

    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


@st.cache_data
def load_species_metadata(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    # Photos_and_Metadata_v3.JSON contains a "species" dictionary.
    return data.get("species", data)


fish_gdf = load_vector_data(fish_records_url)
hex_gdf = load_vector_data(hex_bins_url)
study_area_gdf = load_vector_data(study_area_url)
species_metadata = load_species_metadata(species_json_url)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def parse_species_array(value):
    """
    Convert Species_Array into a clean list of unique scientific names.

    Handles:
      - Python lists
      - strings representing Python lists
      - comma-separated strings
      - empty/null values
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


def species_photo_url(record):
    """
    Convert the photo path in the species JSON into the
    corresponding raw GitHub URL.
    """

    photo = record.get("photo")

    if photo:

        photo = str(photo).lstrip("/")

        if photo.startswith("http://") or photo.startswith("https://"):
            return photo

        return github_raw_base + photo

    return record.get("source_image_url")


def find_species_metadata(species_name):
    """
    Find species metadata case-insensitively.
    """

    wanted = species_name.casefold()

    for name, record in species_metadata.items():

        if str(name).casefold() == wanted:
            return record

    return None


# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------

if "selected_hex" not in st.session_state:
    st.session_state.selected_hex = None

if "selected_species" not in st.session_state:
    st.session_state.selected_species = None


# ---------------------------------------------------------------------
# Create map
# ---------------------------------------------------------------------

m = leafmap.Map(
    center=[30.9, -88.3],
    zoom=8,
    tiles=None,
)


# ---------------------------------------------------------------------
# Basemaps
# ---------------------------------------------------------------------

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


folium.TileLayer(
    tiles="OpenStreetMap",
    name="OpenStreetMap",
    overlay=False,
    control=True,
    show=False,
).add_to(m)


# ---------------------------------------------------------------------
# Elevation / bathymetry raster
#
# Direct TiTiler tiles are used because this successfully rendered
# the terrain colors when add_cog_layer() did not.
# ---------------------------------------------------------------------

titiler_tiles = (
    "https://titiler.opengeos.org/cog/tiles/WebMercatorQuad/"
    "{z}/{x}/{y}.png"
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
    show=False,
    opacity=0.75,
).add_to(m)


# ---------------------------------------------------------------------
# Fish observation heatmap
# ---------------------------------------------------------------------

fish_heatmap = fish_gdf[
    fish_gdf.geometry.notna()
].copy()


heatmap_points = []


for geom in fish_heatmap.geometry:

    try:

        point = geom.centroid

        heatmap_points.append(
            [
                float(point.y),
                float(point.x),
                1.0,       # Every fish record has weight = 1
            ]
        )

    except Exception:
        continue


m.add_heatmap(
    heatmap_points,
    name="Fish Observation Density",
    radius=30,
    blur=25,
    min_opacity=0.35,
    max_zoom=12,
)


# ---------------------------------------------------------------------
# Individual fish records
# ---------------------------------------------------------------------

fish_group = folium.FeatureGroup(
    name="Individual Fish Records",
    show=False,
)


fish_fields = [
    field
    for field in fish_gdf.columns
    if field != "geometry"
]


folium.GeoJson(
    fish_gdf.to_json(),

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


# ---------------------------------------------------------------------
# Study Area
# ---------------------------------------------------------------------

study_group = folium.FeatureGroup(
    name="Study Area",
    show=True,
)


folium.GeoJson(
    study_area_gdf.to_json(),

    style_function=lambda feature: {
        "color": "white",
        "weight": 3,
        "fillColor": "white",
        "fillOpacity": 0.0,
    },

).add_to(study_group)


study_group.add_to(m)


# ---------------------------------------------------------------------
# Hex bins
#
# Important:
# We preserve ALL hexagon properties in the GeoJSON. This allows
# streamlit-folium to return the environmental fields and Species_Array
# when a hexagon is clicked.
# ---------------------------------------------------------------------

hex_geojson = json.loads(
    hex_gdf.to_json()
)


for feature in hex_geojson["features"]:

    feature.setdefault(
        "properties",
        {}
    )

    # Identifies this as a selectable hexagon when it comes back
    # through streamlit-folium.
    feature["properties"]["_layer_type"] = "hex"


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

    tooltip=folium.GeoJsonTooltip(
        fields=["id"],
        aliases=["Hexagon ID"],
        sticky=False,
    ),

).add_to(hex_group)


hex_group.add_to(m)


# ---------------------------------------------------------------------
# Layer control
# ---------------------------------------------------------------------

layer_control = folium.LayerControl(
    position="topright",
    collapsed=False,
)

layer_control.add_to(m)


# ---------------------------------------------------------------------
# Display interactive map
# ---------------------------------------------------------------------
#
# st_folium is important here. Unlike m.to_streamlit(), it sends
# information about clicked map features back to Streamlit.
# ---------------------------------------------------------------------

map_data = st_folium(
    m,
    height=750,
    width=None,
    returned_objects=[
        "last_active_drawing",
    ],
    layer_control=layer_control,
)


# ---------------------------------------------------------------------
# Detect selected hexagon
# ---------------------------------------------------------------------

active = None

if map_data:
    active = map_data.get(
        "last_active_drawing"
    )


if (
    active
    and active.get("properties", {}).get("_layer_type")
    == "hex"
):

    st.session_state.selected_hex = (
        active["properties"]
    )

    # A new hexagon was selected, so clear the previously
    # selected species photo.
    st.session_state.selected_species = None


selected_hex = st.session_state.selected_hex


# ---------------------------------------------------------------------
# Selected hexagon information
# ---------------------------------------------------------------------

if selected_hex:

    species = parse_species_array(
        selected_hex.get("Species_Array")
    )

    st.divider()

    left, right = st.columns(
        [1, 1.4]
    )


    # ---------------------------------------------------------------
    # LEFT: Hexagon information + species list
    # ---------------------------------------------------------------

    with left:

        st.subheader(
            "Selected Hexagon"
        )


        for field, label in FIELD_ALIASES.items():

            value = selected_hex.get(
                field
            )

            if (
                value is not None
                and str(value).strip()
                not in {
                    "",
                    "nan",
                    "None",
                }
            ):

                st.markdown(
                    f"**{label}:** {value}"
                )


        # -----------------------------------------------------------
        # Species count is displayed here.
        #
        # Example:
        # Fish Species (12)
        # -----------------------------------------------------------

        st.subheader(
            f"Fish Species ({len(species)})"
        )


        if species:

            for sp in species:

                if st.button(
                    sp,
                    key=f"species_{sp}",
                    use_container_width=True,
                ):

                    st.session_state.selected_species = sp

        else:

            st.info(
                "No fish species are listed "
                "for this hexagon."
            )


    # ---------------------------------------------------------------
    # RIGHT: Selected species photo
    # ---------------------------------------------------------------

    with right:

        selected_species = (
            st.session_state.selected_species
        )


        if selected_species:

            record = find_species_metadata(
                selected_species
            )


            st.subheader(
                selected_species
            )


            if record:

                image_url = species_photo_url(
                    record
                )


                if image_url:

                    st.image(
                        image_url,
                        use_container_width=True,
                    )


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
                    "No photo metadata was found "
                    "for this species."
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
