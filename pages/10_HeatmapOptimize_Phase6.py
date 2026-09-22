import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import requests
import json
import ast
import copy


# ============================================================
# PAGE SETTINGS
# ============================================================

st.set_page_config(
    page_title="Fish Records Heatmap Optimization Testing",
    layout="wide"
)

st.title("Fish Records Heatmap Optimization Testing")


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
    "max_elevation": "Maximum Elevation",
    "min_elevation": "Minimum Elevation",
    "dom_condition": "Dominant Substrate",
    "hab_group": "Vegetation",
    "SAL_HIGH": "Salinity (High Range)",
    "SAL_LOW": "Salinity (Low Range)",
    "areaname": "Area Name",
    "CSU_Descriptor": "Coastal Segment Unit Description",
}


# ============================================================
# LOAD VECTOR DATA
# ============================================================

@st.cache_data
def load_vector_data(url):
    gdf = gpd.read_file(url)

    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


# ============================================================
# CACHE FISH HEATMAP POINTS
# ============================================================

@st.cache_data
def load_heatmap_points(url):
    """
    Build the heatmap coordinates once and cache them.

    The function accepts the URL rather than a GeoDataFrame so
    Streamlit can cache it without encountering the unhashable
    GeoDataFrame problem.
    """

    gdf = load_vector_data(url)

    points = []

    for geom in gdf.geometry:

        if geom is None:
            continue

        try:
            point = geom.centroid

            points.append([
                float(point.y),
                float(point.x),
                1.0
            ])

        except Exception:
            continue

    return points


# ============================================================
# PHASE 3: CACHE MAP-LAYER SERIALIZATION
# ============================================================
#
# Streamlit reruns this page whenever a hex or species is
# selected.  The GeoDataFrames are already cached, but
# converting them to GeoJSON was still happening on every
# rerun.  These functions cache the serialized browser
# payloads using the URL (a hashable value) instead of a
# GeoDataFrame.
# ============================================================

@st.cache_data
def load_fish_geojson(url):
    gdf = load_vector_data(url)
    return json.dumps(
        json.loads(gdf.to_json()),
        separators=(",", ":")
    )


@st.cache_data
def load_study_area_geojson(url):
    gdf = load_vector_data(url)
    return json.dumps(
        json.loads(gdf.to_json()),
        separators=(",", ":")
    )


@st.cache_data
def load_hex_map_geojson(url):
    gdf = load_vector_data(url)

    # Only the ID and geometry are sent to Leaflet.
    # Environmental fields and Species_Array stay server-side.
    map_gdf = gdf[["id", "geometry"]].copy()

    geojson = json.loads(map_gdf.to_json())

    # Hexagons are small and regular, so 5 decimal places is
    # more than sufficient for display/clicking at this map scale.
    # Reducing coordinate precision substantially reduces the
    # browser payload without changing the visible hex grid.
    def round_coordinates(value):
        if isinstance(value, list):
            return [round_coordinates(item) for item in value]
        if isinstance(value, float):
            return round(value, 5)
        return value

    for feature in geojson["features"]:
        feature.setdefault("properties", {})
        feature["properties"]["_layer_type"] = "hex"
        feature["geometry"]["coordinates"] = round_coordinates(
            feature["geometry"]["coordinates"]
        )

    # Compact separators reduce the amount of HTML/JavaScript
    # that Folium has to send to the browser on each rerun.
    return json.dumps(geojson, separators=(",", ":"))


@st.cache_data
def load_hex_lookup(url):
    gdf = load_vector_data(url)

    # Remove geometry because it is not needed after a click.
    # The resulting dictionary contains all environmental and
    # species attributes needed by the selected-hex panel.
    records = gdf.drop(columns="geometry").to_dict(orient="records")

    # Leaflet sends the hex ID back as a JSON value. Normalize
    # the lookup keys to strings so numeric/string ID differences
    # cannot prevent a clicked hex from being found.
    return {
        str(record["id"]): record
        for record in records
    }


# ============================================================
# LOAD SPECIES METADATA
# ============================================================

@st.cache_data
def load_species_metadata(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    # Your JSON contains a "species" dictionary.
    # This also works if the dictionary itself is returned.
    return data.get("species", data)


@st.cache_data
def load_species_lookup(url):
    """Build a case-insensitive species metadata lookup once."""

    metadata = load_species_metadata(url)

    return {
        str(name).casefold(): record
        for name, record in metadata.items()
    }


@st.cache_data
def load_species_photo(image_url):
    """Download a species photo once and cache the image bytes."""

    if not image_url:
        return None

    response = requests.get(image_url, timeout=30)
    response.raise_for_status()

    return response.content


# ============================================================
# LOAD DATA
# ============================================================

try:
    fish_gdf = load_vector_data(fish_records_url)
    hex_gdf = load_vector_data(hex_bins_url)
    study_area_gdf = load_vector_data(study_area_url)
    species_metadata = load_species_metadata(species_json_url)
    species_lookup = load_species_lookup(species_json_url)

except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()


# ============================================================
# PARSE SPECIES ARRAY
# ============================================================

def parse_species_array(value):
    """
    Convert the Species_Array field into a clean list of
    scientific names.
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
            "[]"
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


# ============================================================
# FIND SPECIES PHOTO
# ============================================================

def species_photo_url(record):
    """
    Convert the photo path in the species JSON into a
    usable GitHub raw URL.
    """

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

    return record.get("source_image_url")


# ============================================================
# FIND SPECIES METADATA
# ============================================================

def find_species_metadata(species_name):
    return species_lookup.get(str(species_name).casefold())
def species_display_name(species_name):
    """
    Return scientific name followed by common name.
    Example:
        Etropus crossotus, Fringed Flounder
    """

    record = find_species_metadata(species_name)

    if record:
        common_name = record.get("common_name")

        if common_name:
            return f"{species_name}, {common_name}"

    return species_name

# ============================================================
# STREAMLIT SESSION STATE
# ============================================================

if "selected_hex" not in st.session_state:
    st.session_state.selected_hex = None

if "selected_species" not in st.session_state:
    st.session_state.selected_species = None


# ============================================================
# PHASE 3: GET CACHED MAP DATA
# ============================================================

fish_geojson = load_fish_geojson(fish_records_url)
study_area_geojson = load_study_area_geojson(study_area_url)


# ============================================================
# PHASE 5B: CACHE THE COMPLETE MAP RESOURCE
# ============================================================

@st.cache_resource
def build_map():
    fish_geojson = load_fish_geojson(fish_records_url)
    study_area_geojson = load_study_area_geojson(study_area_url)
    hex_geojson = load_hex_map_geojson(hex_bins_url)
    heatmap_points = load_heatmap_points(fish_records_url)

    m = leafmap.Map(
        center=[30.9, -88.3],
        zoom=8,
        tiles=None,
        prefer_canvas=True,
    )

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

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
        show=False,
    ).add_to(m)

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

    m.add_heatmap(
        heatmap_points,
        name="Fish Observation Density",
        radius=20,
        blur=15,
        min_opacity=0.35,
        max_zoom=12,
    )

    fish_group = folium.FeatureGroup(
        name="Individual Fish Records",
        show=False,
    )

    fish_fields = [
        field for field in fish_gdf.columns if field != "geometry"
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
            radius=1,
            fill=True,
            fill_opacity=0.8,
            opacity=0.8,
        ),
    ).add_to(fish_group)
    fish_group.add_to(m)

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
        interactive=False,
    ).add_to(study_group)
    study_group.add_to(m)

    hex_group = folium.FeatureGroup(
        name="Hex Bins",
        show=True,
    )

    folium.GeoJson(
        hex_geojson,
        style_function=lambda feature: {
            "color": "white",
            "weight": 0.15,
            "fillColor": "yellow",
            "fillOpacity": 0.001,
        },
        highlight_function=lambda feature: {
            "color": "white",
            "weight": 3,
            "fillColor": "yellow",
            "fillOpacity": 0.15,
        },
    ).add_to(hex_group)
    hex_group.add_to(m)

    folium.LayerControl(
        position="topright",
        collapsed=False,
    ).add_to(m)

    return m


st.markdown(
    '''
    <style>
    .leaflet-heatmap-layer {
        pointer-events: none !important;
    }
    </style>
    ''',
    unsafe_allow_html=True,
)


@st.fragment(key="heatmap_selection")
def heatmap_selection():
    m = build_map()
    hex_lookup = load_hex_lookup(hex_bins_url)

    map_data = st_folium(
        m,
        height=750,
        width=None,
        key="heatmap_folium_map",
        returned_objects=["last_active_drawing"],
    )

    active = map_data.get("last_active_drawing") if map_data else None

    if active:
        properties = active.get("properties", {})

        if properties.get("_layer_type") == "hex":
            active_hex_id = properties.get("id")
            current_hex_id = None

            if st.session_state.selected_hex:
                current_hex_id = st.session_state.selected_hex.get("id")

            if active_hex_id != current_hex_id:
                selected_row = hex_lookup.get(str(active_hex_id))

                if selected_row is not None:
                    st.session_state.selected_hex = selected_row
                    st.session_state.selected_species = None

    selected_hex = st.session_state.selected_hex

    if not selected_hex:
        st.info(
            "Click a hexagon to view its environmental data and fish species."
        )
        return

    species = parse_species_array(selected_hex.get("Species_Array"))

    st.divider()
    left, right = st.columns([1, 1.4])

    with left:
        st.subheader("Selected Hexagon")

        for field, label in FIELD_ALIASES.items():
            value = selected_hex.get(field)

            if value is not None:
                value_text = str(value).strip()

                if value_text not in {"", "nan", "None"}:
                    st.markdown(f"**{label}:** {value}")

        st.subheader(f"Fish Species ({len(species)})")

        if species:
            for sp in species:
                display_name = species_display_name(sp)

                if st.button(
                    display_name,
                    key=f"species_{sp}",
                    use_container_width=True,
                ):
                    st.session_state.selected_species = sp

    with right:
        selected_species = st.session_state.selected_species

        if selected_species:
            record = find_species_metadata(selected_species)
            st.subheader(selected_species)

            if record:
                image_url = species_photo_url(record)

                if image_url:
                    try:
                        image_bytes = load_species_photo(image_url)

                        if image_bytes:
                            st.image(
                                image_bytes,
                                use_container_width=True,
                            )
                        else:
                            st.info("No photo is available for this species.")
                    except Exception as e:
                        st.warning(
                            "The species photo could not be loaded: "
                            f"{e}"
                        )
                else:
                    st.info("No photo is available for this species.")

                if record.get("attribution"):
                    st.caption(record["attribution"])

                if record.get("license"):
                    st.write(f"**License:** {record['license']}")

                if record.get("author"):
                    st.write(
                        f"**Photographer / Author:** {record['author']}"
                    )

                if record.get("source_url"):
                    st.markdown(
                        "[View source on iNaturalist]"
                        f"({record['source_url']})"
                    )
            else:
                st.info("No photo metadata was found for this species.")
        else:
            st.info(
                "Click a species name to view its photo and attribution."
            )


heatmap_selection()
