import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(layout="wide")

st.sidebar.title("About")
st.sidebar.info("""
    - Web App URL: <https://fishes-of-the-ms-sound-and-barrier-islands.streamlit.app/>
    - GitHub repository: <https://github.com/ChazzC/Fishes-Of-The-MS-Sound-And-Barrier-Islands>
    """)

st.sidebar.title("Contact")
st.sidebar.info("""
    Chazz Coleman at [Personal Website](https://chazzccoleman.wixsite.com/ccc-geospatial) | [GitHub](https://github.com/ChazzC) | [LinkedIn](linkedin.com/in/chazz-coleman)
    """)

st.sidebar.title("Support")
st.sidebar.info("""
    If you want to reward my work, I'd love a cup of coffee from you. Thanks!
    [buymeacoffee.com/giswqs](http://buymeacoffee.com/giswqs)
    """)


st.title("Fishes of the Mississippi Sound and Barrier Islands")

st.markdown("""
    This multi-page web app demonstrates an interactive web app created using [streamlit](https://streamlit.io) and open-source mapping libraries,
    such as [leafmap](https://leafmap.org). The fish records/occurences were compiled from multiple sources and span decades. Source attributions are within the fish point layer and also listed here.
    Institution collections on GBIF: Mississippi Museum of Natural Science & University of Alabama.
    Institution collections that were self hosted: University of Southern Mississippi Ichthyology Collection.
    SEAMAP Bottom Long Line survey data.
    SEAMAP Groundfish survey data.
    Research Grade iNaturalist observations.
    """)

st.info("Click on the left sidebar menu to navigate to the different apps.")

st.subheader("Timelapse of Satellite Imagery")
st.markdown("""
    The following timelapse animations were created using the Timelapse web app. Click `Timelapse` on the left sidebar menu to create your own timelapse for any location around the globe.
""")

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    st.image("https://github.com/giswqs/data/raw/main/timelapse/spain.gif")
    st.image("https://github.com/giswqs/data/raw/main/timelapse/las_vegas.gif")

with row1_col2:
    st.image("https://github.com/giswqs/data/raw/main/timelapse/goes.gif")
    st.image("https://github.com/giswqs/data/raw/main/timelapse/fire.gif")
