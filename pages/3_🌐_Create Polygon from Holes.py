import folium
from streamlit_folium import folium_static
import streamlit as st
import streamlit_ext as ste
import geopandas as gpd
import fiona, os
from shapely.geometry import shape, Point, LineString, Polygon, LinearRing
import pyproj
import numpy as np
import shapely
from shapely.ops import transform


st.set_page_config(layout="wide")
st.sidebar.info(
    """
    - Web: [Geoprocessing Streamlit](https://geoprocessing.streamlit.app)
    - GitHub: [Geoprocessing Streamlit](https://github.com/thangqd/geoprocessing) 
    """
)

st.sidebar.title("Contact")
st.sidebar.info(
    """
    Thang Quach: [My Homepage](https://thangqd.github.io) | [GitHub](https://github.com/thangqd) | [LinkedIn](https://www.linkedin.com/in/thangqd)
    """
)
st.title("Create Polygons from Holes")
st.write('Create Polygons from Holes')
col1, col2 = st.columns(2)    

def download_geojson(gdf, layer_name):
    if not gdf.empty:        
        geojson = gdf.to_json()  
        with col2:
            ste.download_button(
                label="Download GeoJSON",
                file_name= 'antipodes_' + layer_name+ '.geojson',
                mime="application/json",
                data=geojson
            ) 

def area_meter(wgs84_geom):
    wgs84 = pyproj.CRS('EPSG:4326')
    utm = pyproj.CRS('EPSG:3857')
    project = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
    return transform(project, wgs84_geom).area
    
def remove_holes_features(f):
    coords_exterior = f.exterior.coords
    linearing_interior = []
    for interior in f.interiors:
        if (area_meter(Polygon(interior)) > 1000 ):
            linearing_interior.append(interior)
    Polygon_Removed_Holes = Polygon(coords_exterior, holes = [interior for interior in linearing_interior])
    # return Polygon_Removed_Holes
    return Polygon(coords_exterior)

def create_holes_features(f): 
    holes = Polygon([(0,0),(0,0),(0,0)])
    if (f != Polygon(f.exterior)): 
        holes = f.symmetric_difference(Polygon(f.exterior)) 
    return holes

def remove_holes_polygon(source):   
    if (source.geometry.type == 'Polygon').all():
        target = source
        target['geometry'] = target.geometry.map(remove_holes_features) 
        return target  

    elif (source.geometry.type == 'MultiPolygon').all():
        source = source.explode(index_parts=False)
        target = source
        target['geometry'] = target.geometry.map(remove_holes_features) 
        target = target.dissolve(by = target.index)
        return target  
    
    else:
        st.warning('Cannot remove holes in polygon!')
        return source

def create_holes_polygon(source):   
    if (source.geometry.type == 'Polygon').all():
        target = source
        target['geometry'] = target.geometry.map(create_holes_features) 
        return target  

    elif (source.geometry.type == 'MultiPolygon').all():
        source = source.explode(index_parts=False)
        target = source
        target['geometry'] = target.geometry.map(create_holes_features) 
        target = target.dissolve(by = target.index)
        return target  
    
    else:
        st.warning('Cannot remove holes in polygon!')
        return source

@st.cache_data
def save_uploaded_file(file_content, file_name):
    """
    Save the uploaded file to a temporary directory
    """
    import tempfile
    import os
    import uuid

    _, file_extension = os.path.splitext(file_name)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(tempfile.gettempdir(), f"{file_id}{file_extension}")

    with open(file_path, "wb") as file:
        file.write(file_content.getbuffer())

    return file_path

def style_function(feature):
    return {
        'fillColor': '#b1ddf9',
        'fillOpacity': 0.5,
        'color': 'blue',
        'weight': 2,
        # 'dashArray': '5, 5'
    }

def highlight_function(feature):   
    return {
    'fillColor': '#ffff00',
    'fillOpacity': 0.8,
    'color': '#ffff00',
    'weight': 4,
    # 'dashArray': '5, 5'
}


form = st.form(key="latlon_calculator")
with form:   
    url = st.text_input(
            "Enter a URL to a vector dataset",
            "https://raw.githubusercontent.com/thangqd/geoprocessing/main/data/csv/polygon.geojson",
        )

    uploaded_file = st.file_uploader(
            "Upload a vector dataset", type=["geojson", "kml", "zip", "tab"]
        )

    if  url or uploaded_file:
        if url:
            file_path = url
            layer_name = url.split("/")[-1].split(".")[0]
        if uploaded_file:
            file_path = save_uploaded_file(uploaded_file, uploaded_file.name)
            layer_name = os.path.splitext(uploaded_file.name)[0]    

        if file_path.lower().endswith(".kml"):
            fiona.drvsupport.supported_drivers["KML"] = "rw"
            gdf = gpd.read_file(file_path, driver="KML")
        else:
            gdf = gpd.read_file(file_path)
        
        center = gdf.dissolve().centroid
        center_lon, center_lat = center.x, center.y
          
        with col1:   
            fields = [ column for column in gdf.columns if column not in gdf.select_dtypes('geometry')]
            m = folium.Map(tiles='stamenterrain', location = [center_lat, center_lon], zoom_start=4)           
            folium.GeoJson(gdf, name = layer_name,  
                           style_function = style_function, 
                           highlight_function=highlight_function,
                           marker = folium.Marker(icon=folium.Icon(
                                     icon='ok-circle',
                                     color = 'purple'
                                     )),     
                            # marker =  folium.CircleMarker(fill=True),
                        #    zoom_on_click = True,
                           popup = folium.GeoJsonPopup(
                           fields = fields
                            )).add_to(m)
           
            m.fit_bounds(m.get_bounds(), padding=(30, 30))
            folium_static(m, width = 600)
        
        submitted = st.form_submit_button("Create new Polygons from Polygons' Holes")        
        if submitted:
            target = create_holes_polygon(gdf)
            target = target[target.geometry.area > 0]

            with col2:
                if not target.empty: 
                    center = target.dissolve().centroid
                    center_lon, center_lat = center.x, center.y             
                    fields = [ column for column in target.columns if column not in target.select_dtypes('geometry')]
                    m = folium.Map(tiles='stamentoner', location = [center_lat, center_lon], zoom_start=4)
                    folium.GeoJson(target,  
                                   style_function = style_function, 
                                   highlight_function=highlight_function,
                                   marker = folium.Marker(icon=folium.Icon(
                                     icon='ok-circle',
                                     color = 'purple'
                                     )),  
                                   popup = folium.GeoJsonPopup(
                                   fields = fields
                                    )).add_to(m)
   
                    m.fit_bounds(m.get_bounds(), padding=(30, 30))
                    folium_static(m, width = 600)         
                    download_geojson(target, layer_name)   