import numpy as np
import json
import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(layout="wide")

st.sidebar.info("""
    - Web App URL: <https://streamlit.gishub.org>
    - GitHub repository: https://github.com/opengeos/streamlit-geospatial
""")

st.sidebar.title("Contact")
st.sidebar.info("""
    # Chazz Coleman at [wetlands.io](https://wetlands.io) |
    [GitHub](https://github.com/ChazzC) |
    # [Twitter](https://twitter.com/giswqs) |
    # [YouTube](https://youtube.com/@giswqs) |
    [LinkedIn](https://www.linkedin.com/in/chazz-coleman)
""")

st.title("Heatmap")

with st.expander("See source code"):
    with st.echo():

        filepath = (
            "https://raw.githubusercontent.com/"
            "giswqs/leafmap/master/examples/data/us_cities.csv"
        )

        dem_filepath = (
            "https://raw.githubusercontent.com/"
            "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
            "main/data/Elevation_and_Bathymertry_Study_Area.tiff.tif"
        )

        m = leafmap.Map(center=[31, -88], zoom=8)
        # Blue → cyan → green → yellow → orange → brown
        custom_colormap = json.dumps([
            [[-19.212, -15], [8, 48, 107, 255]],
            [[-15, -10],     [8, 81, 156, 255]],
            [[-10, -5],      [33, 113, 181, 255]],
            [[-5, 0],        [65, 182, 196, 255]],
            [[0, 2],         [0, 166, 90, 255]],
            [[2, 5],         [127, 207, 63, 255]],
            [[5, 10],        [254, 224, 61, 255]],
            [[10, 20],       [254, 146, 41, 255]],
            [[20, 35],       [244, 109, 67, 255]],
            [[35, 57.122],   [127, 59, 8, 255]],
        ])

        # Add the Cloud Optimized GeoTIFF
        m.add_cog_layer(
            dem_filepath,
            name="Elevation & Bathymetry",
            bands=[1],
            # rescale="-19.212,57.122",
            colormap=custom_colormap,
        )          

        m.add_heatmap(
            filepath,
            latitude="latitude",
            longitude="longitude",
            value="pop_max",
            name="Heat map",
            radius=20,
        )

m.to_streamlit(height=700)
