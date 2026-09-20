import numpy as np
import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(layout="wide")

st.sidebar.info("""
    - Web App URL: <https://streamlit.gishub.org>
    - GitHub repository: https://github.com/opengeos/streamlit-geospatial
""")

st.sidebar.title("Contact")
st.sidebar.info("""
    Qiusheng Wu at [wetlands.io](https://wetlands.io) |
    [GitHub](https://github.com/giswqs) |
    [Twitter](https://twitter.com/giswqs) |
    [YouTube](https://youtube.com/@giswqs) |
    [LinkedIn](https://www.linkedin.com/in/giswqs)
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

        # Add the Cloud Optimized GeoTIFF
        m.add_cog_layer(
            dem_filepath,
            name="Elevation & Bathymetry",
            bands=[1],
            rescale="-19.212,57.122",
            return_mask=True,
            colormap_name: 'terrain'       
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
