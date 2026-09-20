import streamlit as st
import requests

st.set_page_config(layout="wide")

st.title("TiTiler COG Test")

dem_filepath = (
    "https://raw.githubusercontent.com/"
    "ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands/"
    "main/data/Elevation_and_Bathymertry_Study_Area.tiff.tif"
)

st.write("Testing TiTiler...")

try:

    titiler_url = "https://titiler.opengeos.org/cog/preview"

    params = {
        "url": dem_filepath,
        "bidx": 1,
        "rescale": "-19.212,57.122",
        "colormap_name": "terrain",
    }

    response = requests.get(
        titiler_url,
        params=params,
        timeout=30,
    )

    st.write("TiTiler HTTP status:", response.status_code)

    st.write("Response type:", response.headers.get("content-type"))

    if response.ok:

        st.image(
            response.content,
            caption="TiTiler terrain test",
            use_container_width=True,
        )

    else:

        st.error("TiTiler returned an error.")

        st.code(response.text)

except requests.exceptions.Timeout:

    st.error("TiTiler request timed out after 30 seconds.")

except Exception as e:

    st.error("Something went wrong:")
    st.exception(e)
