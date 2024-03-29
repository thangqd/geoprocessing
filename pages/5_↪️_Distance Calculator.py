import folium, os
from folium.plugins import Draw, LocateControl
import streamlit as st
from streamlit_folium import st_folium, folium_static
from folium.plugins import MousePosition
import routingpy as rp
import pandas as pd
from datetime import datetime
import geopy.distance
from becalib.distance_const import *
from routingpy import OSRM
import geopandas as gdp
from shapely.geometry import Point, LineString
from shapely import reverse
from folium.plugins import Fullscreen
import streamlit_ext as ste
import geopandas as gpd
# from pykalman import KalmanFilter
import numpy as np
from math import radians, cos, acos, sin, asin, sqrt
import requests, polyline
from keplergl import KeplerGl
from streamlit_keplergl import keplergl_static

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
st.title("Distance Calculator")
st.write('Distance Calculator for GPS Track Logs')
# start_time = '2023-01-01 00:00:00'
start_time = '2023-01-01 00:00:00'
end_time = '2025-12-30 00:00:00'
MAX_ALLOWED_TIME_GAP = 300  # seconds
MAX_ALLOWED_DISTANCE_GAP = 500  # meters for 1 minute interval
# MAX_ALLOWED_DISTANCE_GAP = 1000  # meters for 5 minute interval

col1, col2 = st.columns(2)

route_geometries = []
shortestpath_dict = {"time": [], "distance": [], "duration": [], "speed": []}
mapmatching_dict = {"time": [], "distance": []}


def style_function(feature):
    return {
        'fillColor': '#b1ddf9',
        'fillOpacity': 0.5,
        'color': 'blue',
        'weight': 2,
        # 'dashArray': '5, 5'
    }

def style_function2(feature):
    return {
        'fillColor': '#b1dda3',
        'fillOpacity': 0.5,
        'color': 'red',
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

def statistics(trackpoints):
    totalDistance = 0
    trackpoints['datetime'] = pd.to_datetime(trackpoints['datetime']).dt.tz_localize(None)
    trackpoints = trackpoints.sort_values('datetime').reset_index().drop('index', axis=1)
    # mask = (trackpoints['datetime'] > start_time) & (trackpoints['datetime'] <= end_time) 
    # trackpoints = trackpoints.loc[mask]
    for i in range (1, len(trackpoints)):
        distance_temp = geopy.distance.geodesic((trackpoints.iloc[i-1].latitude, trackpoints.iloc[i-1].longitude), (trackpoints.iloc[i].latitude, trackpoints.iloc[i].longitude)).m
        totalDistance += distance_temp      
    
    totalDistance =  round(totalDistance/1000, 3)
    st.write ('Total distance without any filters: ', totalDistance, ' km')
    totalTime =  (datetime.strptime(str(trackpoints.iloc[-1].datetime), '%Y-%m-%d %H:%M:%S') - datetime.strptime(str(trackpoints.iloc[0].datetime), '%Y-%m-%d %H:%M:%S')).total_seconds()/60
    st.write ('Total time: ', round(totalTime,2), ' minutes')
    if totalTime > 0 :
        st.write ('Average Speed: ', round(totalDistance/(totalTime/60),2), (' km/h'))
    
    st.write('Number of track points: ', len(trackpoints))  
    st.write('Sessions: ', trackpoints['session'].unique()) 
    trackpoints['date_string'] = pd.to_datetime(trackpoints['datetime']).dt.date.astype(str)
    st.write('Date: ', trackpoints['date_string'].unique() )

    st.write ('Number of duplicate datetime: ', trackpoints.duplicated(subset=["datetime"], keep='last').sum())
    st.write ('Number of duplicate lat and long: ', trackpoints.duplicated(subset=["latitude", "longitude"], keep='last').sum())
    st.write ('Number of duplicate datetime, lat and long: ', trackpoints.duplicated(subset=["datetime", "latitude", "longitude"], keep='last').sum())
    st.write ('Start time:', trackpoints.iloc[0].datetime)
    st.write ('End time:', trackpoints.iloc[-1].datetime)

    st.write(trackpoints)
    st.write('Activity types: ', trackpoints['motionActivity'].unique()) 


# def smooth(points):
#     kf = KalmanFilter(
#         initial_state_mean = points.iloc[0],
#         observation_covariance = np.diag([0.5, 0.5]) ** 2, # TODO: shouldn't be zero
#         transition_covariance = np.diag([0.3, 0.3]) ** 2, # TODO: shouldn't be zero
#         transition_matrices = [[1, 0], [0, 1]] # TODO
#     )
#     kalman_smoothed, _ = kf.smooth(points)
#     df = pd.DataFrame(data=kalman_smoothed, columns=['latitude', 'longitude'])
#     st.write(df)
#     return df

def removejumping(data): 
    filtered = data
    outliers_index = []
    for i in range (1, len(filtered)-1):  #except final jumping point! Ex: WayPoint_20230928142338.csv        
        time_diff = (datetime.strptime(str(data.iloc[i].datetime), '%Y-%m-%d %H:%M:%S') - datetime.strptime(str(data.iloc[i - 1].datetime), '%Y-%m-%d %H:%M:%S')).total_seconds()
        distance_diff = geopy.distance.geodesic((data.iloc[i-1].latitude, data.iloc[i-1].longitude), (data.iloc[i].latitude, data.iloc[i].longitude)).m
        # distance_diff = haversine(data.iloc[i-1].latitude, data.iloc[i-1].longitude, data.iloc[i].latitude, data.iloc[i].longitude)
        if time_diff > 0:
            velocity =  (distance_diff/1000)/(time_diff/3600) #km/h   
            # st.write(data.iloc[i-1].datetime, data.iloc[i].datetime,velocity,' km/h') 
            if velocity >70 : #km/h,
                # filtered = filtered.drop([i])
                st.write('Current Point: ',  data.iloc[i-1].datetime,  data.iloc[i-1]['session'], ' Jumping Point: ', data.iloc[i].datetime, data.iloc[i]['session'], ' Time (seconds): ', round(time_diff, 2) , ' Distance (m): ', round(distance_diff,2), 'Velocity: ', round(velocity,2),' km/h')
                outliers_index.append(data.iloc[i].datetime)            
    # st.write(outliers_index)
    filtered = filtered[filtered.datetime.isin(outliers_index) == False]   
    st.write ('After remove jumping point:', len(filtered)) 
    return filtered


def removejumping_formap(data): 
    filtered = data
    outliers_index = []
    for i in range (1, len(filtered)-1):  #except final jumping point! Ex: WayPoint_20230928142338.csv        
        time_diff = (datetime.strptime(str(data.iloc[i].datetime), '%Y-%m-%d %H:%M:%S') - datetime.strptime(str(data.iloc[i - 1].datetime), '%Y-%m-%d %H:%M:%S')).total_seconds()
        distance_diff = geopy.distance.geodesic((data.iloc[i-1].latitude, data.iloc[i-1].longitude), (data.iloc[i].latitude, data.iloc[i].longitude)).m
        # distance_diff = haversine(data.iloc[i-1].latitude, data.iloc[i-1].longitude, data.iloc[i].latitude, data.iloc[i].longitude)
        if time_diff > 0:
            velocity =  (distance_diff/1000)/(time_diff/3600) #km/h   
            # st.write(data.iloc[i-1].datetime, data.iloc[i].datetime,velocity,' km/h') 
            if velocity >70 : #km/h,
                # filtered = filtered.drop([i])
                # st.write('Current Point: ',  data.iloc[i-1].datetime,  data.iloc[i-1].session, ' Jumping Point: ', data.iloc[i].datetime, data.iloc[i].session, ' Time (seconds): ', round(time_diff, 2) , ' Distance (m): ', round(distance_diff,2), 'Velocity: ', round(velocity,2),' km/h')
                outliers_index.append(data.iloc[i].datetime)            
    # st.write(outliers_index)
    filtered = filtered[filtered.datetime.isin(outliers_index) == False]   
    # st.write ('After remove jumping point:', len(filtered)) 
    return filtered


def preProcessing(data, start_time, end_time, formular):
    filtered = data
    filtered['datetime'] = pd.to_datetime(filtered['datetime'])
    filtered = filtered.sort_values('datetime').reset_index().drop('index', axis=1)
    st.write('Number of original track points: ', len(filtered))   

    timestamp_format = "%Y-%m-%d %H:%M:%S"
    start = datetime.strptime(start_time, timestamp_format)
    #print(start)
    end = datetime.strptime(end_time, timestamp_format)
    #print(end)
    
    
    ##############MotionActivity filter:  may delete "moving" track points
    mask = (filtered['datetime'] > start) & (filtered['datetime'] <= end) & ((filtered['motionActivity'] == 0) | (filtered['motionActivity'] == 1) | (filtered['motionActivity'] == 2) | (filtered['motionActivity'] == 32) | (filtered['motionActivity'] == 64) | (filtered['motionActivity'] == 128))
    if formular == 'old': 
        mask = (filtered['datetime'] > start) & (filtered['datetime'] <= end) & ((filtered['motionActivity'] == 0) | (filtered['motionActivity'] == 1) | (filtered['motionActivity'] == 2))
    filtered = filtered.loc[mask]
    
    st.write('After filter Motion Activity: ', len(filtered))    

    # filtered['datetime'] = pd.to_datetime(filtered['datetime'])
    filtered['datetime'] = pd.to_datetime(filtered['datetime']).dt.tz_localize(None)
    ############## Drop duplicate track points (the same datetime)
    filtered = filtered.drop_duplicates(subset=["driver", "session", "datetime"], keep='last')

    ############## Drop duplicate track points (the same latitude and longitude)
    filtered = filtered.drop_duplicates(subset=["driver", "session","latitude", "longitude"], keep='last') # except last point in case of return to sart point with the same lat long
    # filtered = filtered.drop_duplicates(subset=["latitude", "longitude"], keep='last') # except last point in case of return to sart point with the same lat long
    st.write('After delete duplicates: ', len(filtered))    

    ############## Drop  track points with speed <=5    
    # first_row = filtered.iloc[[0]]
    # last_row = filtered.iloc[[-1]]
    # middle_rows = filtered.iloc[1:-1]
    # filtered_middle_rows = middle_rows[middle_rows['speed'] >5]
    # filtered = pd.concat([first_row, filtered_middle_rows, last_row])
    # st.write('After delete track points with speed <=5: ', len(filtered))    

    filtered['date_string'] = pd.to_datetime(filtered['datetime']).dt.date    
    st.write(filtered)
    return filtered    

def osrm_route(start_lon, start_lat, end_lon, end_lat):       
    #'https://routing.openstreetmap.de/routed-bike/
    # url = f'https://router.project-osrm.org/route/v1/aaaa/{start_lon},{start_lat};{end_lon},{end_lat}?alternatives=false&steps=true&overview=simplified' 
    # url = f'https://api-gw.sovereignsolutions.com/gateway/routing/india/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?alternatives=false&steps=true&overview=simplified&api-key=6bb21ca2-5a4e-4776-b80a-87e2fbd6408d'
    # url= f'https://api-gw.sovereignsolutions.com/gateway/routing/india/match/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?steps=true&api-key=6bb21ca2-5a4e-4776-b80a-87e2fbd6408d'
    url = f'https://router.project-osrm.org/match/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}' 
    # url= f'https://apim.vietbando.vn/gateway/osrm/in/match/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?api-key=ca008f94-f895-4ddd-aa51-470388b7dcb4'
    st.write (url)
    r = requests.get(url,verify=False) 
    if r.status_code!= 200:
        return None
    res = r.json()  
    routes = polyline.decode(res['matchings'][0]['geometry'])
    # start_point = [res['waypoints'][0]['location'][1], res['waypoints'][0]['location'][0]]
    # end_point = [res['waypoints'][1]['location'][1], res['waypoints'][1]['location'][0]]
    
    ##############
    #res['routes'][0]['distance'] for routing
    #res['matchings'][0]['distance'] for map matching
    ##############
    # distance = res['routes'][0]['distance']
    distance = res['matchings'][0]['distance']
    # print('OSRM distance:', distance)
    osrmroute = {'geometry':routes,
           #'start_point':start_point,
           #'end_point':end_point,
           'distance':distance           
          }
    # st.write(osrmroute['geometry'])

    return osrmroute


# def traveledDistance(data):
#     # Remove jumping point groupeb by driver, date, session
#     data = removejumping(data)    
#     totalDistance = 0
#     count = 0
#     shortestpath_index = []
#     shortestpath_distance = []
#     crowfly_distance = []
#     for i in range (1, len(data)):
#         velocity_diff = 0
#         time_diff = (datetime.strptime(str(data.iloc[i].datetime), '%Y-%m-%d %H:%M:%S') - datetime.strptime(str(data.iloc[i - 1].datetime), '%Y-%m-%d %H:%M:%S')).total_seconds()
#         # distance_temp = greatCircle(data.iloc[i].longitude, data.iloc[i].latitude, data.iloc[i - 1].longitude, data.iloc[i - 1].latitude)
#         # distance_temp = haversine((data.iloc[i-1].latitude, data.iloc[i-1].longitude), (data.iloc[i].latitude, data.iloc[i].longitude)).m
#         distance_temp = geopy.distance.geodesic((data.iloc[i-1].latitude, data.iloc[i-1].longitude), (data.iloc[i].latitude, data.iloc[i].longitude)).m
#         if time_diff>0:
#             velocity_diff =  (distance_temp/1000)/(time_diff/3600) #km/h      
#         # # if time_diff > MAX_ALLOWED_TIME_GAP or distance_temp > MAX_ALLOWED_DISTANCE_GAP:
#         #     # #distance_temp = 0
#         #     # st.write(data.iloc[i].datetime)     
    
#         if velocity_diff > 70 or time_diff > MAX_ALLOWED_TIME_GAP or distance_temp> MAX_ALLOWED_DISTANCE_GAP:  # MAX_ALLOWED_TIME_GAP = 300s in case of GPS signals lost for more than MAX_ALLOWED_TIME_GAP seconds
#             if velocity_diff > 5:   
#                 st.write(data.iloc[i-1].datetime)
#                 st.write(data.iloc[i].datetime)
#                 st.write('velocity: ',  velocity_diff)
#                 st.write('time_diff: ', time_diff)
#                 st.write('distance_temp:', distance_temp)            
#                 coor = [[data.iloc[i - 1].longitude, data.iloc[i - 1].latitude], [data.iloc[i].longitude, data.iloc[i].latitude]]
#                 api = OSRM(base_url="https://routing.openstreetmap.de/routed-foot/")
#                 # print(data.iloc[i - 1].longitude, data.iloc[i - 1].latitude, data.iloc[i].longitude, data.iloc[i].latitude, )
#                 route = api.directions(
#                 profile='car',
#                 locations= coor       
#                 )
#                 shortestpath_dict["time"].append(data.iloc[i - 1].datetime)
#                 shortestpath_dict["distance"].append(route.distance)
#                 shortestpath_dict["duration"].append(route.duration)
#                 if (route.duration > 0):
#                     shortestpath_dict["speed"].append((route.distance/1000)/(route.duration/3600)) # km/h
#                 else: shortestpath_dict["speed"].append(0)

#                 crowfly_distance.append(round(distance_temp,2))
#                 if route.distance  > 0:           
#                     shortestpath_distance.append(round(route.distance,2))
#                     shortestpath_index.append(data.iloc[i-1].datetime)  
#                     shortestpath_index.append(data.iloc[i].datetime)                     
#                     route_geometries.append(LineString(route.geometry))
#                     # st.write('shortestpath_geometries: ', route_geometries)
#                     count += 1                    
#                     distance_temp = route.distance    
#         # Access the route properties with .geometry, .duration, .distance                  
#         # print("Loop:", i, "timediff:", time_diff, "Distance Temp:", distance_temp, "Motion Activity:", data.iloc[i].motionActivity)
#         totalDistance += distance_temp
#     st.write('Number of using shortest path in distance calculation: ', count, shortestpath_index,'Crow fly distance: ' , crowfly_distance, 'Shortest Path Distance: ', shortestpath_distance)
#     totalDistance_km = round(totalDistance/1000, 3)
#     return totalDistance_km

def reverse_lat_long_linestring(linestring):
    reversed_coords = [(lng, lat) for lat, lng in linestring.coords]
    return LineString(reversed_coords)

def traveledDistance2(data):
    # Remove jumping point groupeb by driver, date, session
    data = removejumping(data)    
    totalDistance = 0
    count = 0
    mapmatching_index = []
    mapmatching_distance = []
    crowfly_distance = []
    for i in range (1, len(data)):
        velocity_diff = 0
        time_diff = (datetime.strptime(str(data.iloc[i].datetime), '%Y-%m-%d %H:%M:%S') - datetime.strptime(str(data.iloc[i - 1].datetime), '%Y-%m-%d %H:%M:%S')).total_seconds()
        # distance_temp = greatCircle(data.iloc[i].longitude, data.iloc[i].latitude, data.iloc[i - 1].longitude, data.iloc[i - 1].latitude)
        # distance_temp = haversine((data.iloc[i-1].latitude, data.iloc[i-1].longitude), (data.iloc[i].latitude, data.iloc[i].longitude)).m
        distance_temp = geopy.distance.geodesic((data.iloc[i-1].latitude, data.iloc[i-1].longitude), (data.iloc[i].latitude, data.iloc[i].longitude)).m
        if time_diff>0:
            velocity_diff =  (distance_temp/1000)/(time_diff/3600) #km/h      
        # # if time_diff > MAX_ALLOWED_TIME_GAP or distance_temp > MAX_ALLOWED_DISTANCE_GAP:
        #     # #distance_temp = 0
        #     # st.write(data.iloc[i].datetime)     
        
        if velocity_diff > 70 or time_diff > MAX_ALLOWED_TIME_GAP or distance_temp> MAX_ALLOWED_DISTANCE_GAP:  # MAX_ALLOWED_TIME_GAP = 300s in case of GPS signals lost for more than MAX_ALLOWED_TIME_GAP seconds
            if velocity_diff > 5:   
                st.write(data.iloc[i-1].datetime)
                st.write(data.iloc[i].datetime)
                st.write('velocity: ',  velocity_diff)
                st.write('time_diff: ', time_diff)
                st.write('distance_temp:', distance_temp)            
                route = osrm_route(data.iloc[i - 1].longitude, data.iloc[i - 1].latitude, data.iloc[i].longitude, data.iloc[i].latitude)
                # print('distance_temp:', distance_temp)
                if route is not None:
                    mapmatching_dict["time"].append(data.iloc[i - 1].datetime)
                    mapmatching_dict["distance"].append(route['distance'])
                    # # dict_["duration"].append(route['duration'])
                    # if (route['duration'] > 0):
                    #     dict_["speed"].append((route['distance']/1000)/(route['duration']/3600)) # km/h
                    # else: dict_["speed"].append(0)
                    crowfly_distance.append(round(distance_temp,2))

                    if route['distance'] > 0:
                        # print('route distance:',route['distance'])
                        mapmatching_distance.append(round(route['distance'],2))
                        mapmatching_index.append(data.iloc[i-1].datetime)  
                        mapmatching_index.append(data.iloc[i].datetime)                     
                        route_geometries.append(LineString(route['geometry'])) 
                        st.write('mapmatching_geometries: ', route_geometries)
                        count += 1                    
                        distance_temp = route['distance']
            ############# Not calculate walk points
            else:     distance_temp = 0
                # print('distance_temp after if:', distance_temp)    
        # print("Loop:", i, "timediff:", timediff, "Distance Temp:", distance_temp, "Motion Activity:", data.iloc[i].motionActivity)
        # if distance_temp> 100000:
        if distance_temp> 100000 or distance_temp < 84: # if the interval of GPS signal is 1 minutes
        # if distance_temp> 100000 or distance_temp < 420 : # if the interval of GPS signal is 5 minutes
            distance_temp = 0
        totalDistance += distance_temp   
    st.write('Number of using map matching in distance calculation: ', count, mapmatching_index,'Crow fly distance: ' , crowfly_distance, 'Map matching Distance: ', mapmatching_distance)
    totalDistance_km = round(totalDistance/1000, 3)
    return totalDistance_km    

def download_geojson(gdf, layer_name):
    if not gdf.empty:        
        geojson = gdf.to_json()  
        ste.download_button(
            label="Download " + layer_name,
            file_name= layer_name+ '.geojson',
            mime="application/json",
            data=geojson
        ) 

with col1:
    form = st.form(key="distance_calculator")
    layer_name = 'track'
    with form: 
        url = st.text_input(
                "Enter a CSV URL with Latitude and Longitude Columns",
                'https://raw.githubusercontent.com/thangqd/geoprocessing/main/data/csv/gps_noise_2.csv'
            )
        uploaded_file = st.file_uploader("Or upload a CSV file with Latitude and Longitude Columns")
        lat_column_index, lon_column_index = 0,0     

        if url:   
            df = pd.read_csv(url,encoding = "UTF-8")    
            layer_name = url.split("/")[-1].split(".")[0]            
        if uploaded_file:        
            df = pd.read_csv(uploaded_file,encoding = "UTF-8")
            layer_name = os.path.splitext(uploaded_file.name)[0]
        
        # # display timeseries data
        # my_map = KeplerGl(data={"Track": df}, height=600)
        # keplergl_static(my_map, center_map=True)

        m = folium.Map(max_zoom = 21,
                    tiles='cartodbpositron',
                    zoom_start=14,
                    control_scale=True
                    )
        Fullscreen(                                                         
                position                = "topright",                                   
                title                   = "Open full-screen map",                       
                title_cancel            = "Close full-screen map",                      
                force_separate_button   = True,                                         
            ).add_to(m)
        
        colors = [ 'green','blue', 'orange', 'red',
                  'lightblue', 'cadetblue', 'darkblue', 
                  'lightgreen', 'darkgreen',             
                  'purple','darkpurple', 'pink',
                  'beige', 'lightred',
                  'white', 'lightgray', 'gray', 'black','darkred']
        if df['session'].nunique() <20:
            df['session_label'] = pd.Categorical(df["session"]).codes
        else: df['session_label'] = 0

        for index, row in df.iterrows():
            popup = row.to_frame().to_html()
            folium.Marker([row['latitude'], row['longitude']], 
                        popup=popup,
                        icon=folium.Icon(icon='car', color=colors[row.session_label], prefix='fa')
                        # icon=folium.Icon(icon='car', prefix='fa')
                        ).add_to(m)        
            
        m.fit_bounds(m.get_bounds(), padding=(30, 30))
        folium_static(m, width = 600)
        geometry = [Point(xy) for xy in zip(df.longitude, df.latitude)]
        trackpoints_origin = gdp.GeoDataFrame(df, geometry=geometry, crs = 'epsg:4326')        
        download_geojson(trackpoints_origin,layer_name)
        submitted = st.form_submit_button("Calculate Distance")    
    


def CalculateDistance(data, groupBy):        
    grouped = data.groupby(groupBy)
    # result = grouped.apply(traveledDistance)
    result = grouped.apply(traveledDistance2)
    # return result.values[0]
    return result.sum()


if submitted:
    with col1:
        statistics(df)
    with col2:        
        st.write('Step 1/2: Preprocessing')
        # df = smooth(df)
        df = preProcessing(df, start_time, end_time, 'new')   
        df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df['date_string'] = df['date_string'].astype(str)
        st.write('Step 2/2: Distance Calculation')
        groupBy = ['driver', 'date_string', 'session']
        st.write('Distance traveled:', CalculateDistance(df, groupBy), ' km') 

        df_removejumping = removejumping_formap(df)
        geometry = [Point(xy) for xy in zip(df_removejumping.longitude, df_removejumping.latitude)]
        trackpoints_cleaned = gdp.GeoDataFrame(df_removejumping, geometry=geometry, crs = 'epsg:4326')
        trackpoints_cleaned_fields = [ column for column in trackpoints_cleaned.columns if column not in trackpoints_cleaned.select_dtypes('geometry')]

        # aggregate these points with the GrouBy
        # folium.GeoJson(geo_df_cleaned).add_to(m)
        # folium_static(m, width = 800)
        # download_geojson(geo_df_cleaned, 'track_points_cleaned')                
        geo_df = gdp.GeoDataFrame(df_removejumping, geometry=geometry)
        # aggregate these points with the GrouBy
        geo_df = geo_df.groupby(['driver', 'date_string'])['geometry'].apply(lambda x: LineString(x.tolist()))
        track_distance = gdp.GeoDataFrame(geo_df, geometry='geometry', crs = 'EPSG:4326')

        center = track_distance.dissolve().centroid
        center_lon, center_lat = center.x, center.y        
        m = folium.Map(max_zoom = 21,
                        tiles='cartodbpositron',
                        location = [center_lat, center_lon],
                        zoom_start=14,
                        control_scale=True
                        )
        Fullscreen(                                                         
                position                = "topright",                                   
                title                   = "Open full-screen map",                       
                title_cancel            = "Close full-screen map",                      
                force_separate_button   = True,                                         
            ).add_to(m)

        folium.GeoJson(trackpoints_cleaned, name = 'track_points_cleaned',  
                        style_function = style_function, 
                        highlight_function=highlight_function,
                        marker = folium.Marker(icon=folium.Icon(
                                    icon='ok-circle',
                                    color = 'green',
                                    size = 5
                                    )),     
                        # marker =  folium.CircleMarker(fill=True),
                        # zoom_on_click = True,
                        popup = folium.GeoJsonPopup(
                        fields = trackpoints_cleaned_fields
                        )).add_to(m)

        folium.GeoJson(track_distance, name = 'track_distance',  
                        style_function = style_function, 
                        highlight_function=highlight_function,
                        # popup = folium.GeoJsonPopup(
                        # fields = tracpoints_cleaned_fields
                        # )
                        ).add_to(m)

        routes_df = gpd.GeoDataFrame(shortestpath_dict, geometry=route_geometries, crs="EPSG:4326")
        # routes_df = gpd.GeoDataFrame(mapmatching_dict, geometry=route_geometries, crs="EPSG:4326")
        # routes_df['geometry'] = routes_df['geometry'].reverse()
        # st.write(routes_df)
        routes_df['geometry'] = routes_df['geometry'].apply(reverse_lat_long_linestring)
        # st.write('reverse geometry: ', routes_df)

        folium.GeoJson(routes_df, name = 'shortest_path',  
                        style_function = style_function2, 
                        highlight_function=highlight_function,
                        # popup = folium.GeoJsonPopup(
                        # fields = tracpoints_cleaned_fields
                        # )
                        ).add_to(m)
        
        m.fit_bounds(m.get_bounds(), padding=(30, 30))
        folium_static(m, width = 600)
        download_geojson(trackpoints_cleaned, layer_name + '_cleaned')
        download_geojson(track_distance, layer_name + '_track')
        download_geojson(routes_df, layer_name + '_mapmatching')