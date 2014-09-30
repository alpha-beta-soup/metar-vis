# /usr/bin/env python
# -*- coding: utf-8 -*-
'''
METAR-vis
-------

Retrieve, view, store and map METAR meterological information.

Dependencies
-------

pyspatialite (and hence sqlite3 and spatialite): pip install pyspatialite
folium (and hence pandas, numpy and jinja2): pip install folium

See ./requirements.txt

Author
------

Richard Law

Date
------

2014-09-29 -- 2014-09-30

'''

import urllib2 # For acquring station data .TXT files
import re # For matching patterns in the .TXT files to extract useful data
import datetime as dt # For creating a datetime object of the observation time
import calendar # To convert datetime to UNIX timestamp
from pyspatialite import dbapi2 as dbapi # For storage and retrieval of spatial and non-spatial data
import folium # For building a Leaflet tile map


class METARTxtFile:
    '''
    A .TXT file of METAR data, at a particular place and time.
    '''
    def __init__(self, station, metardb):
        # metardb : a metarsqlite3db object
        source = 'http://weather.noaa.gov/pub/data/observations/metar/decoded/'
        self.url = source + station + '.TXT'
        self.station = station
        self.text = urllib2.urlopen(self.url)
        self.dataList = self.text.readlines()
        self.datadict = self.makeDataDict()
        
        locale = self.getLine(0) # Location
        if locale == 'Station name not available':
            self.locale = None
        else:
            self.locale = locale
        # Not all of these are constrained to exist. Nonetype indicates that the attribute does not exist
        self.when = self.getLine(1) # Date and time
        self.wind = self.datadict.get('Wind') # Wind attributes
        self.visibility = self.datadict.get('Visibility') # Visibility attributes
        self.skyconditions = self.datadict.get('Sky conditions') # Sky condition attributes
        self.temperature = self.datadict.get('Temperature') # Temperature attributes
        self.dewpoint = self.datadict.get('Dew Point') # Dew point attributes
        self.relativehumidity = self.datadict.get('Relative Humidity') # Relative humidity attributes
        self.pressure = self.datadict.get('Pressure (altimeter)') # Pressure (altimeter) attributes
        self.ob = self.datadict.get('ob') # "ob" attributes
        self.cycle = self.datadict.get('cycle') # "cycle" attributes
        
        # Each object is associated with a DB where it's data is added if it is missing
        self.metardb = metardb 
        self.addIfMissing() # Adds the data to self.metardb, ignoring data conflicts
        
    def makeDataDict(self):
        # Returns a dictionary of available information
        dataDict = {}
        for i in range(2,len(self.dataList)):
            k,v = self.getLine(i).split(':',1)
            dataDict[k.strip()] = v.strip()
        return dataDict
        
    def displayText(self):
        # Nicely prints the available information
        print self.url
        display = [i.strip() for i in self.dataList]
        for i in display:
            print i
              
    def getLine(self, index):
        # Returns the text of the line n (index)
        return self.dataList[index].strip()
        
    def localeLabel(self):
        # Returns the text in self.locale up to the first comma: this is the label of the location
        # Example: 'Wellington Airport'
        if self.locale == None:
            return None
        pattern = '[\w, ]*,' # regex pattern
        m = re.search(pattern, self.locale)
        if m == None:
            return None
        elif m.start() == 0:
            # The match is at the beginning of the line
            return m.group().replace(',','').strip()
        else:
            # The match is not where we expected
            return None
            
    def localeCountry(self):
        # Returns the text in self.locale after the first comma and up to an open bracket
        # this is the country of the location
        # Example: 'New Zealand'
        if self.locale == None:
            return None
        pattern = ', [\w\s]* \(' # regex pattern
        m = re.search(pattern, self.locale)
        if m == None:
            return None
        else:
            country = m.group()
            for s in [', ', ' (']:
                country = country.replace(s,'').strip()
            return country
    
    def localeXY(self):
        # Returns the latitude and longitude of the station as a tuple of signed floats
        # Example output: (-43.29, 172.33) (from '42-29S 172-33E')
        if self.locale == None:
            return None
        patterns = ['\) \d*-\d*[S,N]', '\d*-\d*[E,W]']
        coords = ()
        for pattern in patterns:
            m = re.search(pattern, self.locale)
            if m == None:
                return None
            else:
                coord = m.group().strip().replace(') ','').replace('-','.')
                hemi = coord[-1]
                if hemi in ['S','W']:
                    negative = True
                elif hemi in ['N','E']:
                    negative = False
                else:
                    print coord
                    raise Exception # Latitude (longitude) not in ['S','N'] (['E','W'])
                coord = float(coord[:-1])
                if negative:
                    coord = coord*-1
            coords = coords + (coord,) # Append the coord to the tuple
        return coords # lat lon tuple
        
    def localeM(self):
        # Returns the M coordinate of the station as an integer
        # Does not handle negative elevations
        if self.locale == None:
            return None
        pattern = '[E,W] \d*M'
        m = re.search(pattern, self.locale)
        if m == None:
            return None
        else:
            m = m.group()
            m = m.replace('E ','').replace('W ','')
            if m[-1] != 'M':
                raise Exception # Elevation not in metres
            return int(m.strip('M'))
            
    def xyzmstring(self):
        # Returns a WKT representation of the XYZM point, where M is UNIX time
        # of the measurement (from the UTC recorded time)
        if self.locale == None:
            # It has not location, only an M value, so we ignore it
            return None
        # NOTE: have to give lon lat
        xyzm = (self.localeXY()[1], self.localeXY()[0], self.localeM(), calendar.timegm(self.whenDatetime().utctimetuple()))
        return 'POINT ZM(%s %s %s %s)' % (str(xyzm[0]),str(xyzm[1]),str(xyzm[2]),str(xyzm[3]))
            
    def whenDatetime(self):
        # Returns a datetime.datetime object representing the date and time of
        # the data represents, in UTC.
        pattern = '\d\d\d\d.\d\d.\d\d \d\d\d\d UTC'
        m = re.search(pattern, self.when)
        if m == None:
            return None
        else:
            dtobj = dt.datetime.strptime(m.group(), '%Y.%m.%d %H%M %Z')
            return dtobj
            
    def windSpeed(self, MPH=True):
        # Returns the wind speed
        # if MPH: returns an integer in miles per hour (MPH)
        # else: returns an integer in knots (KT)
        if MPH == True:
            pattern = '\d* MPH'
        else:
            pattern = '\d* KT'
        m = re.search(pattern, self.wind)
        if m == None:
            return None
        else:
            return int(m.group().split(' ')[0])
    
    def windDirection(self):
        # Returns the wind direction in degrees, as an integer
        # Example input (self.wind): "Wind: from the SE (130 degrees) at 12 MPH (10 KT):0"
        # Example output: 130
        pattern = '\d* degrees'
        m = re.search(pattern, self.wind)
        if m == None:
            return None
        else:
            return int(m.group().strip(' degrees'))
    
    def temperatureTemp(self, celsius=True):
        # Returns the temperature
        # if celsius: returns an integer in degrees Celsius
        # else: returns an integer in degrees fahrenheit
        if celsius == True:
            pattern = '\d* C'
        else:
            pattern = '\d* F'
        m = re.search(pattern, self.temperature)
        if m == None:
            return None
        else:
            return int(m.group().split(' ')[0])
            
    def addIfMissing(self):
        # Adds the data from self into metardb, if the data does not exist in the DB
        # NOTE: on conflict ignore
        sql = '''INSERT OR IGNORE INTO tableName (label, station, country, utc,
        windspeed_mph, windspeed_kts, winddirection, temperature_c, temperature_f, geom)
        VALUES ('''.replace('tableName', self.metardb.tableName)
        vals = (self.localeLabel(), self.station, self.localeCountry(), str(self.whenDatetime()), self.windSpeed(), self.windSpeed(False), self.windDirection(), self.temperatureTemp(), self.temperatureTemp(False), self.xyzmstring())
        if self.locale is not None:
            # If there's a location, geom will be populated
            self.metardb.cur.execute(sql+'?,?,?,?,?,?,?,?,?,GeomFromText(?, 4326))', vals)
        else:
            # If there isn't a location, geom will be None
            sql = sql.replace(', geom','')
            vals = vals[:-1]
            self.metardb.cur.execute(sql+'?,?,?,?,?,?,?,?,?)', vals)
        self.metardb.conn.commit()
        return None
            
class metarsqlite3db:
    '''
    A class for a SQLite3/Spatialite database that will hold METAR data
    '''
    def __init__(self, connstring):
        # connstring: path to database and name of database, e.g. './data/metar.sqlite'
        self.conn = dbapi.connect(connstring)
        self.cur = self.conn.cursor()
        self.tableName = 'metarvals' # Only using one table to store everything for this simple application
        self.tableCreate() # Creates table, adds spatial metadata, adds XYZM geometry column
        self.sqlite_version = self.getSQLiteVersion()
        self.spatialite_version = self.getSpatialiteVersion()
        if self.sqlite_version != '3.8.2':
            print 'This code has only been tested with SQLite v.3.8.2; you are using SQLite v.%s' % self.sqlite_version 
        if self.spatialite_version != '4.1.1':
            print 'This code has only been tested with Spatialite v.4.1.1; you are using Spatialite v.%s' % self.spatialite_version
        self.verbose = False # Verbose SELECT queries
        
    def tableCreate(self):
        # Checks whether the table 'tableName' exists, and creates it if it does not
        # If the table already exists, nothing happens
        # Also checks for the existence of spatialite metadata, and adds it if it does not exist
        # Then adds an XYZM point geometry column
        sql = '''CREATE TABLE IF NOT EXISTS tableName (
        station TEXT NOT NULL,
        label TEXT,
        country TEXT,
        utc TEXT NOT NULL,
        windspeed_mph INTEGER,
        windspeed_kts INTEGER,
        winddirection INTEGER,
        temperature_c INTEGER,
        temperature_f INTEGER,
        PRIMARY KEY (station, utc));
        '''.replace('tableName', self.tableName)
        self.conn.execute(sql)
        # Check if spatial meta data has been initialised
        check = self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='geometry_columns'")
        for c in check:
            if 'spatial_ref_sys' not in c:
                self.conn.execute("SELECT InitSpatialMetaData();")
        try:
            self.cur.execute("SELECT geom FROM tableName;".replace('tableName', self.tableName))
        except Exception as e:
            if 'no such column' in str(e):
                self.conn.execute("SELECT AddGeometryColumn('tableName', 'geom', 4326, 'POINT', 'XYZM');".replace('tableName', self.tableName))
            else:
                raise e # Did not succeed
        return None
        
    def getSQLiteVersion(self):
        # Returns a string of the sqlite version number
        r = self.cur.execute('SELECT sqlite_version()')
        for l in r:
            return l[0]
    
    def getSpatialiteVersion(self):
        # Returns a string of the spatialite version number
        r = self.cur.execute('SELECT spatialite_version()')
        for l in r:
            return l[0]
            
    def returnMostRecent(self):
        # Returns the most recent METAR record of all unique stations,
        # provided that the data is not more than 24 hours old
        # Additionally returns X and Y in EPSG:4326 coordinates
        sql = '''SELECT X(geom), Y(geom), * FROM metarvals
        WHERE rowid IN
	        (SELECT rowid FROM metarvals 
	        WHERE station = station
	        ORDER BY utc DESC)
        AND CAST(M(geom) AS INTEGER) >= '%s'
        GROUP BY station
        ORDER BY utc DESC;
        ''' % (str(nDaysAgo(1)))
        if self.verbose: print sql
        self.cur.execute(sql)
        return self.cur.fetchall()
            
    def returnBoundingBox(self):
        # Returns the bounding box of the points to be mapped, in EPSG:4326 coordinates
        # Output: lower left corner XY, upper right corner XY: ((X,Y),(X,Y))
        xs,ys = [],[]
        for pt in self.returnMostRecent():
            xs.append(pt[0]), ys.append(pt[1])
        return ((min(xs),min(ys)),(max(xs),max(ys)))
            
class foliumMap():
    '''
    A class for a folium Map object, with methods to access the database and display
    the most recent weather information.
    '''
    def __init__(self, metardb, width, height, tiles):
        # metardb : A metarsqlite3db object
        # width, height: integers: width and height of map <div> (pixels)
        # tiles: Folium tiles (Stamen, OSM, et al.) or your own tiles (see Folium docs)
        self.metardb = metardb
        self.width = width
        self.height = height
        self.zoom_start = 6
        self.tiles = tiles
        self.bbox = metardb.returnBoundingBox()
        self.centrelat = (self.bbox[0][0]+self.bbox[1][0])/2.
        self.centrelon = (self.bbox[0][1]+self.bbox[1][1])/2.
        self.location = [self.centrelon,self.centrelat] # Centre of the map
        self.map = folium.Map(location=self.location,width=self.width,height=self.height,zoom_start=self.zoom_start,tiles=self.tiles)
        self.map.lat_lng_popover() # Will return the lat lon of a click on the map
    
    def addPoint(self, x, y, popup):
        # Adds a point (location and attributes) to self.map
        # There are more style options: try print(self.map.simple_marker.__doc__)
        self.map.simple_marker(location=[x,y],
            popup=popup,
            popup_on=True,
            #marker_color='red', # These features are not in the current version of folium 
            #marker_icon='info-sign',
            #clustered_marker=False,
            #icon_angle=0
            )
        #TODO self.map.circle_marker(location=[x,y],popup=popup,radius=20000)
        return None
        
    def addOverlay(self, geojsonOverlay):
        # Adds a GeoJSON overlay to the Folium map
        print self.map.geo_json.__doc__
        self.map.geo_json(geo_path=geojsonOverlay,
            topojson='objects.collection',
            line_color='blue',
            line_weight=3,
            fill_color='blue',
            fill_opacity=0.6)
            #key_on='feature.name')
        return None
        
    def makeMap(self, mapName, coastline):
        # Makes the folium map
        # mapName : a string for the html file name
        # coastline : a path to a GeoJSON feature to be used as an overlay
        
        # Loop through points and build pop-ups and add them to the map as markers
        for pt in self.metardb.returnMostRecent():
            #TODO This must not rely on indexes in production
            #TODO Instead, one can either:
                # Make the objects again (kinda weird, as it'd go off to the internet and not actually look at the DB, just record them if they're new
                # Get the database query to also return a dictionary of column headers and corresponding index positions
                # Or just get the database query to optionally return a dictionary representation, and use that here instead of the raw
            popup = '%s, %s\nUTC %s\n Wind speed: %d mph\nDirection: %d degrees\nTemperature: %d C' % (pt[2], pt[3], str(pt[5]), pt[6], pt[8], pt[9])
            # TODO popup = 'sim,ple %sp:opup\nnext%s: %d\nyeah: %d\n%s' % ('hi', ' line,', 76, pt[6], str(pt[5]))
            # TODO popup = '%s, %s' % (pt[2], pt[3])
            # Handle jQuery special characters in the pop-up
            for sc in [':',',','\n','-']:
                if sc == '\n':
                    replace = '<br>'
                else:
                    replace = '\\%s' % sc
                popup = popup.replace(sc,replace)
            self.addPoint(pt[1],pt[0],str(popup))
        
        # Add the GeoJSON overlay TODO
        #print coastline
        #self.addOverlay(coastline)
        
        # Write the map HTML and JS
        self.map.create_map(path=mapName+'.html')
        return None

def nDaysAgo(n):
    '''
    Returns a UNIX time stamp (integer seconds) of the time exactly n days ago
    from the current time. Used to check the currency of stored data and ignore
    old information, even if that information is the most recent in the database
    for a particular station.
    '''
    nago = dt.datetime.utcnow() - dt.timedelta(days=n) # Now, n days ago
    nago = calendar.timegm(nago.utctimetuple()) # Now, n days ago, as UNIX timestamp
    return nago
   
def main(verbose=False):
    # Create or connect to DB
    metardb = metarsqlite3db('./data/metar.db')
    # Loop through stations we care about, adding their data to the DB if it
    # has not already been collected
    stations = ['NZWN', 'NZAA', 'NZCH']
    for station in stations:
        metar = METARTxtFile(station, metardb)
        if verbose: print(metar.station)
    # Instantiate the map object, and make the map (loops through collected points)
    w=1300 # Width of map <div>
    fmap = foliumMap(metardb, w, w*0.66, 'Mapbox Bright')
    # TODO: Add note about download as GPKG, ogr2ogr to geojson
    # ogr2ogr -f GeoJSON -t_srs 'EPSG:4326' ./data/test.json ./data/lds-nz-mainland-coastlines-topo-1250k-GPKG/nz-mainland-coastlines-topo-1250k.gpkg
    coastline = './data/test_topo.json'
    fmap.makeMap('testmap', coastline) # TODO Add these as parameters in __init__
    return None
        
if __name__ == '__main__':
    main()
