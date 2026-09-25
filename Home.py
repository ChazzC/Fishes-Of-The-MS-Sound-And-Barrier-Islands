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
    
    """)


st.title("Fishes of the Mississippi Sound and Barrier Islands - From Lake Borgne to Mobile Bay")

st.markdown("""
    This multi-page web app demonstrates an interactive web app created using [streamlit](https://streamlit.io) and open-source mapping libraries,
    such as [leafmap](https://leafmap.org). Data were initially ingested, processed, and cleaned with the open-source desktop GIS software [QGIS](https://qgis.org/)
    
    There are over 17,000 observations and ~360 species present in this Study Area. The fish records/occurences were compiled from multiple sources and span decades. Efforts were made to update names to current taxonomy. Source attributions are within the "Individual Fish Records" point layer and also listed here:
    - Institution collections on [GBIF](https://www.gbif.org/occurrence/search?occurrenceStatus=present): Mississippi Museum of Natural Science & University of Alabama.
    - Institution collections that were self hosted: [University of Southern Mississippi Ichthyology Collection](https://ichthyology.usm.edu/shiny/map/).
    - [SEAMAP](https://seamapdata.gsmfc.org/pages/download-form.php) Bottom Long Line survey data & Groundfish survey data.
    - Research Grade [iNaturalist](https://www.inaturalist.org/observations) observations.

    The following environmental data were downloaded from NOAA's [NCEI Gulf Data Atlas](https://www.ncei.noaa.gov/maps/gulf-data-atlas/atlas.htm):
    - [Substrate](https://data.noaa.gov/metaview/page?xml=NOAA/NESDIS/ncei/gulf_atlas/iso/xml/USSeabed_GOM_Sediments.xml&view=getDataView&header=none) 
    - [Salinity Ranges](https://data.noaa.gov/metaview/page?xml=NOAA/NESDIS/ncei/gulf_atlas/iso/xml/Gulf_Salinity_5_Season.xml&view=getDataView&header=none)
    - [Submerged Aquatic Vegetation](https://data.noaa.gov/metaview/page?xml=NOAA/NESDIS/ncei/gulf_atlas/iso/xml/USGS_GulfwideSAV_1940_2003.xml&view=getDataView&header=none)
    - [Elevation](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ngdc.mgg.dem:720/html)

    Coastal Ecological Units/Coastal Segment Units were downloaded from [ArcGIS Hub](https://hub.arcgis.com/datasets/esri::ecological-coastal-units-ecus-/about)

    All of the representative fish photos were sourced from iNaturalist users of various Creative Commons Licenses or were from myself. I tried to ensure each photo owner/author is credited according to their photo license as stated on iNaturalist. If I've made a mistake please contact me.  
    """)

st.info("Click on the left sidebar menu to navigate to the different apps.")

st.subheader("Timelapse of Satellite Imagery")
st.markdown("""
    The following timelapse animations were created using the Timelapse web app. Click `Timelapse` on the left sidebar menu to create your own timelapse for any location around the globe.
""")

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    st.image("photos/37F0A380-8729-4B91-8E7B-56CF94ECA801.png")
    st.image("photos/Aerial_Overview.png")

#with row1_col2:
    #st.image("https://github.com/giswqs/data/raw/main/timelapse/goes.gif")
    #st.image("https://github.com/giswqs/data/raw/main/timelapse/fire.gif")
