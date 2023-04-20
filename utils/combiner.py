from sklearn.base import BaseEstimator, TransformerMixin
import geopandas as gpd
import pandas as pd

rooms_ix, bedrooms_ix, population_ix, households_ix = 3, 4, 5, 6
class CombinedAttributesAdder(BaseEstimator, TransformerMixin):

    DISTANCE_CRS = 32643
    CRS = 4326

    def __init__(self, add_bedrooms_per_room = True): # no *args or **kargs 
        self.add_bedrooms_per_room = add_bedrooms_per_room

        # nearest cities
        california_cities = pd.read_csv('utils/cal_cities_lat_long.csv')
        geometry_cal = gpd.points_from_xy(california_cities['Longitude'], california_cities['Latitude'])
        self.points_cal = gpd.GeoDataFrame(california_cities, geometry=geometry_cal)
        self.points_cal.set_crs(self.CRS, inplace=True)
        self._feature_names_out = None

        # coastline
        self.coastline = gpd.read_file('data/coastline/US_Westcoast.shp')[['geometry']]
        self.coastline = self.coastline.to_crs(crs=self.CRS)

    @staticmethod
    def dataframe_to_geo(data: pd.DataFrame):
        print(data)
        geometry = gpd.points_from_xy(data['lon'], data['lat'])
        data = gpd.GeoDataFrame(data).set_geometry(geometry).set_crs(CombinedAttributesAdder.CRS)

        return data
    
    def add_nearest_cities(self, data):

        if not isinstance(data, gpd.GeoDataFrame):
            data = self.dataframe_to_geo(data)
    
        nearest_cities = gpd.sjoin_nearest(
            data.to_crs(crs=self.DISTANCE_CRS), 
            self.points_cal.to_crs(crs=self.DISTANCE_CRS), 
            how='left', distance_col='distance_nearest_city'
        ).to_crs(self.CRS).drop(columns=['index_right'])
        nearest_cities = nearest_cities.rename(columns={'Name': 'nearest_city'})

        nearest_cities = nearest_cities[~nearest_cities.index.duplicated(keep='first')]


        return nearest_cities
    
    def add_ocean_distance(self, data):

        if not isinstance(data, gpd.GeoDataFrame):
            data = self.dataframe_to_geo(data)

        nearest_coastline = gpd.sjoin_nearest(
            data.to_crs(crs=self.DISTANCE_CRS), 
            self.coastline.to_crs(crs=self.DISTANCE_CRS), 
            distance_col='distance_to_ocean'
        ).to_crs(self.CRS).drop(columns='index_right')

        nearest_coastline = nearest_coastline[~nearest_coastline.index.duplicated(keep='first')]

        return nearest_coastline

    def fit(self, X, y=None):
        return self

    def transform(self, X, y=None):
        data = self.dataframe_to_geo(X)

        joined_data = self.add_nearest_cities(data).to_crs(self.DISTANCE_CRS)
    
        # performance drops a lot when distance to the ocean is added
        #joined_data = self.add_ocean_distance(joined_data)

        X = joined_data.drop(columns=['geometry','lat','lon','Latitude','Longitude','population'])
        X = X.assign(
            rooms_per_household=X.total_rooms / X.households,
            bedrooms_per_room=X.total_bedrooms / X.total_rooms if self.add_bedrooms_per_room else None
        )

        self._feature_names_out = X.columns.to_list()

        return X
    
    def get_feature_names_out(self, input_feature = None):
        return self._feature_names_out