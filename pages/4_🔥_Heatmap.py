import json
import html
import re
import requests

import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import folium


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Fish Records Heatmap",
    page_icon="🔥",
    layout="wide",
)

st.title("🔥 Fish Records & Environmental Heatmap")

st.markdown(
    """
    Click a hexagon to explore environmental conditions and the
    fish species recorded within that hexagon.
    """
)


# ============================================================
# GITHUB DATA URLS
# ============================================================

BASE_RAW = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/main"
)

dem_filepath = (
    f"{BASE_RAW}/data/"
    "Elevation_and_Bathymertry_Study_Area.tiff.tif"
)

fish_records_url = f"{BASE_RAW}/data/Fish_Records.geojson"

hex_bins_url = f"{BASE_RAW}/data/Hex_Bins.geojson"

study_area_url = f"{BASE_RAW}/data/StudyArea.geojson"

species_metadata_url = (
    f"{BASE_RAW}/Photos_and_Metadata_v3.JSON"
)

# Photos are stored in this GitHub folder.
photos_base_url = f"{BASE_RAW}/photos/"


# ============================================================
# USER-FRIENDLY FIELD ALIASES
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


# Fields that should never appear in the visitor-facing popup.
HIDDEN_FIELDS = {
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
}


# ============================================================
# LOAD VECTOR DATA
# ============================================================

@st.cache_data(ttl=3600)
def load_vector_data(url):
    gdf = gpd.read_file(url)

    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


@st.cache_data(ttl=3600)
def load_species_metadata(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


# ------------------------------------------------------------
# Load GIS data
# ------------------------------------------------------------

fish_gdf = load_vector_data(fish_records_url)
hex_gdf = load_vector_data(hex_bins_url)
study_area_gdf = load_vector_data(study_area_url)


# ------------------------------------------------------------
# Load species/photo metadata
# ------------------------------------------------------------

try:
    species_metadata = load_species_metadata(species_metadata_url)

except Exception as e:
    species_metadata = None

    st.warning(
        "The species photo metadata could not be loaded from GitHub. "
        "The environmental map will still work."
    )

    st.caption(str(e))


# ============================================================
# SPECIES METADATA HELPERS
# ============================================================

def normalize_species_name(value):
    """
    Normalize species names so that small differences in
    capitalization or whitespace don't prevent matching.
    """
    if value is None:
        return ""

    value = str(value).strip()

    value = re.sub(r"\s+", " ", value)

    return value.casefold()


def find_species_records(data):
    """
    Convert the various possible JSON layouts into a simple
    list of dictionaries.

    This intentionally avoids assuming that the top-level JSON
    object has only one particular structure.
    """

    if data is None:
        return []

    if isinstance(data, list):
        return [
            item for item in data
            if isinstance(item, dict)
        ]

    if isinstance(data, dict):

        # Common structure:
        # {"species": [...]}
        for key in [
            "species",
            "Species",
            "records",
            "Records",
            "data",
            "Data",
            "photos",
            "Photos",
        ]:

            value = data.get(key)

            if isinstance(value, list):

                return [
                    item for item in value
                    if isinstance(item, dict)
                ]

        # Another common structure is:
        # {"Aetobatus narinari": {...}, ...}
        records = []

        for key, value in data.items():

            if isinstance(value, dict):

                record = value.copy()

                if not any(
                    k.lower() in {
                        "species",
                        "scientific_name",
                        "scientific name",
                        "scientificname",
                    }
                    for k in record.keys()
                ):
                    record["species"] = key

                records.append(record)

        return records

    return []


def get_record_value(record, possible_keys):
    """
    Find the first matching value from a list of possible
    metadata field names.
    """

    if not isinstance(record, dict):
        return None

    lowered = {
        str(k).casefold(): v
        for k, v in record.items()
    }

    for key in possible_keys:

        value = lowered.get(key.casefold())

        if value not in [None, ""]:
            return value

    return None


def build_species_lookup(data):

    records = find_species_records(data)

    lookup = {}

    for record in records:

        species = get_record_value(
            record,
            [
                "scientific_name",
                "scientific name",
                "scientificname",
                "species",
                "Species",
                "taxon_name",
                "taxon",
            ],
        )

        if not species:
            continue

        species = str(species).strip()

        normalized = normalize_species_name(species)

        photo_filename = get_record_value(
            record,
            [
                "photo_filename",
                "photo filename",
                "filename",
                "file_name",
                "image_filename",
                "image filename",
                "photo",
                "image",
            ],
        )

        author = get_record_value(
            record,
            [
                "author",
                "owner",
                "photographer",
                "creator",
                "username",
                "inat_author",
            ],
        )

        license_name = get_record_value(
            record,
            [
                "license",
                "license_code",
                "license name",
            ],
        )

        attribution = get_record_value(
            record,
            [
                "attribution",
                "credit",
                "photo_attribution",
            ],
        )

        source_url = get_record_value(
            record,
            [
                "source_url",
                "source url",
                "inat_url",
                "inaturalist_url",
                "url",
                "source",
            ],
        )

        image_url = get_record_value(
            record,
            [
                "image_url",
                "image url",
                "source_image_url",
                "source image url",
            ],
        )

        # If the metadata contains only a filename,
        # build the GitHub photo URL.
        if not image_url and photo_filename:

            filename = str(photo_filename).strip()

            image_url = (
                photos_base_url
                + requests.utils.quote(filename)
            )

        lookup[normalized] = {
            "species": species,
            "photo_filename": photo_filename,
            "image_url": image_url,
            "author": author,
            "license": license_name,
            "attribution": attribution,
            "source_url": source_url,
        }

    return lookup


species_lookup = build_species_lookup(species_metadata)


# ============================================================
# SPECIES ARRAY HANDLING
# ============================================================

def parse_species_array(value):

    if value is None:
        return []

    # Already a Python list.
    if isinstance(value, list):

        result = []

        for item in value:

            if item is None:
                continue

            item = str(item).strip()

            if item:
                result.append(item)

        return sorted(set(result), key=str.casefold)

    # JSON string representation of a list.
    if isinstance(value, str):

        value = value.strip()

        if not value:
            return []

        try:

            parsed = json.loads(value)

            if isinstance(parsed, list):
                return parse_species_array(parsed)

        except Exception:
            pass

        # Fallback for comma-separated values.
        parts = [
            x.strip()
            for x in value.split(",")
        ]

        return sorted(
            set(x for x in parts if x),
            key=str.casefold,
        )

    return []


# ============================================================
# HTML HELPERS
# ============================================================

def safe_text(value):

    if value is None:
        return ""

    if isinstance(value, float):

        if value != value:
            return ""

    return html.escape(str(value))


def create_species_photo_html(species):

    normalized = normalize_species_name(species)

    record = species_lookup.get(normalized)

    species_display = safe_text(species)

    if record is None:

        return f"""
        <div class="species-photo-panel">
            <h4>{species_display}</h4>
            <p><em>No photo metadata found.</em></p>
        </div>
        """

    image_url = record.get("image_url")

    author = safe_text(record.get("author"))
    license_name = safe_text(record.get("license"))
    attribution = safe_text(record.get("attribution"))
    source_url = record.get("source_url")

    if image_url:

        image_html = f"""
        <img
            src="{html.escape(str(image_url), quote=True)}"
            style="
                width:100%;
                max-height:260px;
                object-fit:contain;
                border-radius:6px;
                margin-top:8px;
            "
        >
        """

    else:

        image_html = """
        <p><em>No photograph available.</em></p>
        """

    source_html = ""

    if source_url:

        source_html = f"""
        <p style="margin-top:6px;">
            <a
                href="{html.escape(str(source_url), quote=True)}"
                target="_blank"
            >
                View original iNaturalist record
            </a>
        </p>
        """

    credit_parts = []

    if attribution:
        credit_parts.append(attribution)

    elif author:
        credit_parts.append(f"Photo: {author}")

    if license_name:
        credit_parts.append(f"License: {license_name}")

    credit_html = ""

    if credit_parts:

        credit_html = f"""
        <div
            style="
                font-size:11px;
                color:#555;
                margin-top:5px;
            "
        >
            {"<br>".join(credit_parts)}
        </div>
        """

    return f"""
    <div class="species-photo-panel">

        <h4
            style="
                margin-bottom:5px;
                font-style:italic;
            "
        >
            {species_display}
        </h4>

        {image_html}

        {credit_html}

        {source_html}

    </div>
    """


# ============================================================
# HEX POPUP
# ============================================================

def create_hex_popup(row, hex_index):

    species = parse_species_array(
        row.get("Species_Array")
    )

    # --------------------------------------------------------
    # Environmental information
    # --------------------------------------------------------

    environmental_rows = []

    for field, label in FIELD_ALIASES.items():

        if field not in row:
            continue

        value = row.get(field)

        if value is None:
            continue

        if isinstance(value, float) and value != value:
            continue

        value = str(value).strip()

        if not value:
            continue

        environmental_rows.append(
            f"""
            <tr>
                <td
                    style="
                        font-weight:600;
                        padding:3px 8px 3px 0;
                        vertical-align:top;
                    "
                >
                    {html.escape(label)}
                </td>

                <td
                    style="
                        padding:3px 0;
                        vertical-align:top;
                    "
                >
                    {html.escape(value)}
                </td>
            </tr>
            """
        )

    environmental_html = "".join(environmental_rows)

    if not environmental_html:

        environmental_html = """
        <tr>
            <td colspan="2">
                No environmental information available.
            </td>
        </tr>
        """

    # --------------------------------------------------------
    # Species list
    # --------------------------------------------------------

    if species:

        species_buttons = []

        for i, species_name in enumerate(species):

            species_display = safe_text(species_name)

            photo_html = create_species_photo_html(
                species_name
            )

            # Escape the HTML so it can safely be embedded
            # inside the JavaScript string.
            photo_html_js = json.dumps(photo_html)

            button = f"""
            <button
                type="button"
                onclick='showSpeciesPhoto(
                    "hex_{hex_index}",
                    {json.dumps(species_name)},
                    {photo_html_js}
                )'
                style="
                    display:block;
                    width:100%;
                    text-align:left;
                    border:none;
                    background:none;
                    padding:4px 0;
                    color:#1464a0;
                    cursor:pointer;
                    font-style:italic;
                    font-size:13px;
                "
            >
                {species_display}
            </button>
            """

            species_buttons.append(button)

        species_html = "".join(species_buttons)

    else:

        species_html = """
        <p>
            <em>No fish species recorded in this hexagon.</em>
        </p>
        """

    # --------------------------------------------------------
    # Final popup
    # --------------------------------------------------------

    popup_html = f"""
    <div
        id="popup_hex_{hex_index}"
        style="
            width:340px;
            max-height:520px;
            overflow-y:auto;
            font-family:Arial,sans-serif;
            font-size:13px;
        "
    >

        <h3
            style="
                margin-top:0;
                margin-bottom:10px;
                border-bottom:1px solid #ccc;
                padding-bottom:6px;
            "
        >
            Hexagon {safe_text(row.get("id", hex_index))}
        </h3>


        <h4
            style="
                margin-bottom:5px;
            "
        >
            Environmental Information
        </h4>

        <table
            style="
                width:100%;
                border-collapse:collapse;
                margin-bottom:12px;
            "
        >
            {environmental_html}
        </table>


        <h4
            style="
                margin-top:10px;
                margin-bottom:5px;
            "
        >
            Fish Species
        </h4>

        <div>
            {species_html}
        </div>


        <div
            id="species_photo_hex_{hex_index}"
            style="
                margin-top:12px;
                padding-top:10px;
                border-top:1px solid #ccc;
            "
        >
            <p style="color:#777;">
                Click a species above to view its photograph.
            </p>
        </div>

    </div>
    """

    return popup_html


# ============================================================
# JAVASCRIPT FOR SPECIES PHOTOS
# ============================================================

species_photo_js = """
<script>

function showSpeciesPhoto(hexId, speciesName, photoHtml) {

    var panel = document.getElementById(
        "species_photo_" + hexId
    );

    if (!panel) {
        return;
    }

    panel.innerHTML = photoHtml;

}

</script>
"""


# ============================================================
# CREATE MAP
# ============================================================

m = leafmap.Map(
    center=[30.9, -88.3],
    zoom=8,
    tiles=None,
)


# ============================================================
# BASEMAPS
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


folium.TileLayer(
    tiles="OpenStreetMap",
    name="OpenStreetMap",
    overlay=False,
    control=True,
    show=False,
).add_to(m)


# ============================================================
# ELEVATION / BATHYMETRY RASTER
# ============================================================

titiler_tiles = (
    "https://titiler.opengeos.org/"
    "cog/tiles/WebMercatorQuad/"
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


# ============================================================
# FISH OBSERVATION HEATMAP
# ============================================================

fish_heatmap = fish_gdf.copy()

fish_heatmap = fish_heatmap[
    fish_heatmap.geometry.notna()
].copy()


if fish_heatmap.crs is not None:

    fish_heatmap = fish_heatmap.to_crs(
        "EPSG:4326"
    )


heatmap_points = []


for geom in fish_heatmap.geometry:

    try:

        point = geom.centroid

        heatmap_points.append(
            [
                float(point.y),
                float(point.x),
                1.0,
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


# ============================================================
# INDIVIDUAL FISH RECORDS
# ============================================================

fish_group = folium.FeatureGroup(
    name="Individual Fish Records",
    show=False,
)


tooltip_fields = [
    field
    for field in fish_gdf.columns
    if field != "geometry"
]


folium.GeoJson(
    fish_gdf.to_json(),
    name="Individual Fish Records",

    tooltip=folium.GeoJsonTooltip(
        fields=tooltip_fields,
        aliases=tooltip_fields,
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


# ============================================================
# HEX BINS
# ============================================================

hex_group = folium.FeatureGroup(
    name="Hex Bins",
    show=True,
)


for hex_index, row in hex_gdf.iterrows():

    geometry = row.geometry

    if geometry is None:
        continue

    # --------------------------------------------------------
    # Make a single-feature GeoJSON object.
    # --------------------------------------------------------

    feature = {
        "type": "Feature",
        "geometry": geometry.__geo_interface__,
        "properties": {},
    }

    popup_html = create_hex_popup(
        row,
        hex_index,
    )

    popup = folium.Popup(
        popup_html,
        max_width=380,
    )

    folium.GeoJson(
        feature,

        name=f"Hex {row.get('id', hex_index)}",

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

        popup=popup,

    ).add_to(hex_group)


hex_group.add_to(m)


# ============================================================
# JAVASCRIPT
# ============================================================

m.get_root().html.add_child(
    folium.Element(species_photo_js)
)


# ============================================================
# LAYER CONTROL
# ============================================================

folium.LayerControl(
    position="topright",
    collapsed=False,
).add_to(m)


# ============================================================
# DISPLAY
# ============================================================

m.to_streamlit(
    height=750,
    add_layer_control=False,
)
