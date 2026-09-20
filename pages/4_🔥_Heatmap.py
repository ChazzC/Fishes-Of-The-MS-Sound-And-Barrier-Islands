import numpy as np
import json
import streamlit as st
import leafmap.foliumap as leafmap
import requests

st.set_page_config(layout="wide")

st.sidebar.info("""
    - Web App URL: <https://streamlit.gishub.org>
    - GitHub repository: https://github.com/opengeos/streamlit-geospatial
""")

st.sidebar.title("Contact")
st.sidebar.info("""
    # Chazz Coleman at |
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
                # Test TiTiler directly
        titiler_url = "https://titiler.opengeos.org/cog/preview"
        
        params = {
            "url": dem_filepath,
            "bidx": 1,
            "rescale": "-19.212,57.122",
            "colormap_name": "terrain",
            "return_mask": True,
        }
        
        response = requests.get(titiler_url, params=params)
        
        st.write("TiTiler status:", response.status_code)
        
        if response.ok:
            st.image(
                response.content,
                caption="Direct TiTiler test",
                use_container_width=True,
            )
        else:
            st.error("TiTiler returned an error:")
            st.code(response.text)

        m = leafmap.Map(center=[31, -88], zoom=8)
        # Custom bathymetry/elevation color ramp
          
        custom_colormap = json.dumps({
            "0":   "#08306B",
            "14":  "#08519C",
            "31":  "#2171B5",
            "48":  "#41B6C4",
            "64":  "#00A65A",
            "71":  "#7FCF3F",
            "81":  "#D9EF3D",
            "98":  "#FEE08B",
            "131": "#F46D43",
            "181": "#D73027",
            "255": "#7F3B08",
        })  

        # Add the Cloud Optimized GeoTIFF
       # Add the COG
        # m.add_cog_layer(
        #     dem_filepath,
        #     name="Elevation & Bathymetry",
        #     bands=[1],
        #     rescale="-19.212,57.122",
        #     colormap=custom_colormap,
        # )         

        m.add_heatmap(
            filepath,
            latitude="latitude",
            longitude="longitude",
            value="pop_max",
            name="Heat map",
            radius=20,
        )

m.to_streamlit(height=700)
