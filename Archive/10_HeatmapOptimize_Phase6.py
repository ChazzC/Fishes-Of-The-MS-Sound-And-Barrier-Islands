import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import folium
from streamlit_folium import (
    _component_func,
    generate_js_hash,
    _get_html,
    _get_header,
    _get_map_string,
    get_full_id,
)
import requests
import json
import ast


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
# HEATMAP CLICK BEHAVIOR
# ============================================================

# Make the fish heatmap visual-only so it cannot intercept clicks.
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


# ============================================================
# PHASE 6A: CACHE THE ENTIRE FOLIUM MAP RENDER
# ============================================================
#
# The map itself is static.  Only the Streamlit selection panel
# changes when a hex is clicked.  st_folium() normally rebuilds
# the Folium HTML/Leaflet JavaScript on every Streamlit rerun.
# With 5,833 hexagons, that is expensive.
#
# Phase 6A renders the static map ONCE and caches the resulting
# component payload.  Subsequent reruns reuse the exact same
# Leaflet script instead of walking all 5,833 hexagons again.
#
# This uses the rendering primitives from streamlit-folium rather
# than changing the visual map or the click-handling logic.
# ============================================================

@st.cache_data(show_spinner=False)
def build_cached_map_payload():
    """Build and render the static Folium map exactly once."""

    # Reuse the already-defined map object from the current script
    # construction.  This function intentionally builds its own map
    # so the cached payload is independent of later Streamlit state.
    cached_map = leafmap.Map(
        center=[30.9, -88.3],
        zoom=8,
        tiles=None,
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
    ).add_to(cached_map)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
        show=False,
    ).add_to(cached_map)

    cached_titiler_tiles = (
        "https://titiler.opengeos.org/cog/tiles/"
        "WebMercatorQuad/{z}/{x}/{y}.png"
        "?url=" + dem_filepath
        + "&bidx=1"
        + "&rescale=-19.212,57.122"
        + "&colormap_name=terrain"
    )

    folium.TileLayer(
        tiles=cached_titiler_tiles,
        attr="TiTiler",
        name="Elevation & Bathymetry",
        overlay=True,
        control=True,
        show=False,
        opacity=0.75,
    ).add_to(cached_map)

    cached_heatmap_points = load_heatmap_points(fish_records_url)

    cached_map.add_heatmap(
        cached_heatmap_points,
        name="Fish Observation Density",
        radius=20,
        blur=15,
        min_opacity=0.35,
        max_zoom=12,
    )

    cached_fish_group = folium.FeatureGroup(
        name="Individual Fish Records",
        show=False,
    )

    cached_fish_fields = [
        field for field in fish_gdf.columns if field != "geometry"
    ]

    folium.GeoJson(
        fish_geojson,
        tooltip=folium.GeoJsonTooltip(
            fields=cached_fish_fields,
            aliases=cached_fish_fields,
            localize=True,
            sticky=False,
        ),
        marker=folium.CircleMarker(
            radius=1,
            fill=True,
            fill_opacity=0.8,
            opacity=0.8,
        ),
    ).add_to(cached_fish_group)

    cached_fish_group.add_to(cached_map)

    cached_study_group = folium.FeatureGroup(
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
    ).add_to(cached_study_group)

    cached_study_group.add_to(cached_map)

    cached_hex_geojson = load_hex_map_geojson(hex_bins_url)
    cached_hex_group = folium.FeatureGroup(
        name="Hex Bins",
        show=True,
    )

    folium.GeoJson(
        cached_hex_geojson,
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
    ).add_to(cached_hex_group)

    cached_hex_group.add_to(cached_map)

    folium.LayerControl(
        position="topright",
        collapsed=False,
    ).add_to(cached_map)

    # Render the map once, then extract the same payload that
    # st_folium would normally generate on every rerun.
    cached_map.get_root().render()
    cached_map.render()

    html = _get_html(cached_map)
    header = _get_header(cached_map)
    leaflet = _get_map_string(cached_map)

    m_id = get_full_id(cached_map)

    # st_folium's frontend expects the JavaScript/CSS dependency
    # lists that Folium elements declare.  Recreate that small part
    # of st_folium's renderer here.
    import branca

    css_links = []
    js_links = []

    def walk(fig):
        if isinstance(fig, branca.colormap.ColorMap):
            yield fig
        if isinstance(fig, folium.plugins.DualMap):
            yield from walk(fig.m1)
            yield from walk(fig.m2)
        if isinstance(fig, folium.elements.JSCSSMixin):
            yield fig
        if hasattr(fig, "_children"):
            for child in fig._children.values():
                yield from walk(child)

    for elem in walk(cached_map):
        if isinstance(elem, branca.colormap.ColorMap):
            js_links.insert(
                0,
                "https://cdnjs.cloudflare.com/ajax/libs/d3/3.5.5/d3.min.js",
            )
            js_links.insert(0, "https://d3js.org/d3.v4.min.js")
        css_links.extend([href for _, href in getattr(elem, "default_css", [])])
        js_links.extend([src for _, src in getattr(elem, "default_js", [])])

    css_links = list(dict.fromkeys(css_links))
    js_links = list(dict.fromkeys(js_links))

    # This must remain stable across reruns or Streamlit may remount
    # the component.  The Leaflet script itself is cached, so the hash
    # is also stable.
    component_key = generate_js_hash(
        leaflet,
        "fish_heatmap_map",
        False,
    )

    return {
        "script": leaflet,
        "header": header,
        "html": html,
        "id": m_id,
        "css_links": css_links,
        "js_links": js_links,
        "component_key": component_key,
    }


# Build/read the cached static map payload.
map_payload = build_cached_map_payload()


# ============================================================
# DISPLAY CACHED MAP AND CAPTURE CLICKS
# ============================================================

# We call the underlying Streamlit component directly so the
# already-rendered Leaflet payload can be reused without calling
# st_folium()'s Folium rendering pipeline again.
map_data = _component_func(
    script=map_payload["script"],
    header=map_payload["header"],
    html=map_payload["html"],
    id=map_payload["id"],
    key=map_payload["component_key"],
    height=750,
    width=None,
    returned_objects=["last_active_drawing"],
    default={
        "last_active_drawing": None,
    },
    zoom=None,
    center=None,
    feature_group=None,
    return_on_hover=False,
    layer_control=None,
    pixelated=False,
    css_links=map_payload["css_links"],
    js_links=map_payload["js_links"],
    on_change=None,
    wrap_longitude=False,
)


# ============================================================
# DISPLAY MAP AND CAPTURE CLICKS
#
# IMPORTANT:
# Do not add another LayerControl through st_folium().
# ============================================================

map_data = st_folium(
    m,
    height=750,
    width=None,
    key="fish_heatmap_map",
    # Only return the object used by the hex-click handler.
    # This avoids sending unused click payloads back to Streamlit.
    returned_objects=[
        "last_active_drawing",
    ],
)


# ============================================================
# PROCESS CLICKED HEXAGON
# ============================================================

active = None

if map_data:
    active = map_data.get("last_active_drawing")


if active:

    properties = active.get(
        "properties",
        {}
    )

    if properties.get("_layer_type") == "hex":

        # Identify the hexagon.
        active_hex_id = properties.get("id")

        current_hex_id = None

        if st.session_state.selected_hex:
            current_hex_id = (
                st.session_state.selected_hex.get("id")
            )

        # Only reset the species selection if the user
        # actually selected a DIFFERENT hexagon.
        #
        # This is important because clicking a Streamlit
        # species button causes the page to rerun.
        if active_hex_id != current_hex_id:

            # Retrieve the complete record from the Python-side
            # lookup instead of relying on browser-side attributes.
            selected_row = hex_lookup.get(str(active_hex_id))

            if selected_row is not None:

                st.session_state.selected_hex = selected_row

                st.session_state.selected_species = None


# ============================================================
# GET CURRENT SELECTED HEX
# ============================================================

selected_hex = st.session_state.selected_hex


# ============================================================
# DISPLAY SELECTED HEX INFORMATION
# ============================================================

if selected_hex:

    species = parse_species_array(
        selected_hex.get("Species_Array")
    )

    st.divider()

    left, right = st.columns(
        [1, 1.4]
    )


    # ========================================================
    # LEFT COLUMN
    # ========================================================

    with left:

        st.subheader(
            "Selected Hexagon"
        )


        # ----------------------------------------------------
        # Environmental information
        # ----------------------------------------------------

        for field, label in FIELD_ALIASES.items():

            value = selected_hex.get(field)

            if value is not None:

                value_text = str(value).strip()

                if value_text not in {
                    "",
                    "nan",
                    "None",
                }:

                    st.markdown(
                        f"**{label}:** {value}"
                    )


        # ----------------------------------------------------
        # Species list
        # ----------------------------------------------------

        st.subheader(
            f"Fish Species ({len(species)})"
        )


        if species:

            for sp in species:
        
                display_name = species_display_name(sp)
        
                if st.button(
                    display_name,
                    key=f"species_{sp}",
                    use_container_width=True,
                ):

                    # Keep the scientific name as the internal value.
                    st.session_state.selected_species = sp


    # ========================================================
    # RIGHT COLUMN
    # ========================================================

    with right:

        selected_species = (
            st.session_state.selected_species
        )


        # ----------------------------------------------------
        # Species selected
        # ----------------------------------------------------

        if selected_species:

            record = find_species_metadata(
                selected_species
            )

            st.subheader(
                selected_species
            )


            # ------------------------------------------------
            # Photo and metadata
            # ------------------------------------------------

            if record:

                image_url = species_photo_url(
                    record
                )


                # --------------------------------------------
                # Photo
                # --------------------------------------------

                if image_url:

                    try:

                        image_bytes = load_species_photo(image_url)

                        if image_bytes:
                            st.image(
                                image_bytes,
                                use_container_width=True
                            )
                        else:
                            st.info(
                                "No photo is available "
                                "for this species."
                            )

                    except Exception as e:

                        st.warning(
                            "The species photo could "
                            f"not be loaded: {e}"
                        )


                else:

                    st.info(
                        "No photo is available "
                        "for this species."
                    )


                # --------------------------------------------
                # Attribution
                # --------------------------------------------

                if record.get("attribution"):

                    st.caption(
                        record["attribution"]
                    )


                # --------------------------------------------
                # License
                # --------------------------------------------

                if record.get("license"):

                    st.write(
                        f"**License:** "
                        f"{record['license']}"
                    )


                # --------------------------------------------
                # Photographer / Author
                # --------------------------------------------

                if record.get("author"):

                    st.write(
                        f"**Photographer / Author:** "
                        f"{record['author']}"
                    )


                # --------------------------------------------
                # iNaturalist source
                # --------------------------------------------

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


        # ----------------------------------------------------
        # No species selected yet
        # ----------------------------------------------------

        else:

            st.info(
                "Click a species name to view "
                "its photo and attribution."
            )


# ============================================================
# NOTHING SELECTED YET
# ============================================================

else:

    st.info(
        "Click a hexagon to view its "
        "environmental data and fish species."
    )
