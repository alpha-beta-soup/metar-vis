# /usr/bin/env python
'''
METAR-vis
-------

Retrieve, view, store and map METAR meterological information.

Dependencies
-------
This module requires SQLlite/Spatialite to store, manage and retrieve data,
and a Python API to it: pyspatialite.
It also requires Folium, a neat Python library for creating Leaflet maps.
Finally we need wxPython, for making a GUI.

pyspatialite (and hence sqlite3 and spatialite): pip install pyspatialite
folium (and hence pandas, numpy and jinja2): pip install folium

Other imported modules are all standard libraries

See ./requirements.txt for versions used when writing

Author
------
Richard Law

Date
------
2014-09-29 -- 2014-10-04

'''

import urllib2 # For acquring station data .TXT files
import webbrowser # To see output
import re # For matching patterns in the .TXT files to extract useful data
import datetime as dt # For creating a datetime object of the observation time
import calendar # To convert datetime to UNIX timestamp
import os
import time

from pyspatialite import dbapi2 as dbapi # For storage and retrieval of spatial and non-spatial data
import folium # For building a Leaflet tile map
from bs4 import BeautifulSoup

class METARTxtFile:
    '''
    A .TXT file of METAR data, at a particular place and time.
    '''
    def __init__(self, station, metardb):
        '''
        Input:
        station -- The four-character station code of the station.
        metardb -- a metarsqlite3db object representing the SQLite/Spatialite
                   database where the data will be stored if it does not already
                   exist.'''
        source = 'http://weather.noaa.gov/pub/data/observations/metar/decoded/'
        self.url = source + station + '.TXT'
        self.station = station
        try:
            self.text = urllib2.urlopen(self.url)
        except urllib2.HTTPError, e:
            
            if 'Error 403: Forbidden' in str(e):
                # Restricted site, do nothing
                print 'Cannot process {station}: {forbidden}'.format(station=self.station,
                                                                     forbidden=str(e))
                return None
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
    
    def __repr__(self):
        '''Nicely prints the available information.'''
        print self.url
        display = [i.strip() for i in self.dataList]
        for i in display:
            print i
        
    def makeDataDict(self):
        '''Returns a dictionary of available information from the METAR txt file'''
        dataDict = {}
        for i in range(2,len(self.dataList)):
            k,v = self.getLine(i).split(':',1)
            dataDict[k.strip()] = v.strip()
        return dataDict
            
    def getLine(self, index):
        '''Returns the text of the line n (index) from the raw METAR TXT record'''
        return self.dataList[index].strip()
        
    def localeLabel(self):
        '''Returns the text in self.locale up to the first comma: this is the label of the location
        Example: 'Wellington Airport'
        '''
        if self.locale == None:
            return None
        pattern = '[\w,\s]+,' # regex pattern
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
        '''Returns the text in self.locale after the first comma and up to an open bracket
        this is the country of the location
        Example: 'New Zealand'
        '''
        if self.locale == None:
            return None
        pattern = ',\s\w+\s\(' # regex pattern
        m = re.search(pattern, self.locale)
        if m == None:
            return None
        else:
            country = m.group()
            for s in [', ', ' (']:
                country = country.replace(s,'').strip()
            return country
    
    def localeXY(self):
        '''Returns the latitude and longitude of the station as a tuple of
        signed floats. Handles any combination of hemispheres.
        Example:
            input: '42-29S 172-33E'
            output: (-43.29, 172.33)'''
        if self.locale == None:
            return None
        patterns = ['\)\s\d+-\d+[S,N]', '\s\d+-\d+[E,W]']
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
        
    def localeZ(self):
        '''Returns the Z coordinate of the station as an integer
        Does not handle negative elevations'''
        if self.locale == None:
            return None
        pattern = '[E,W]\s\d+M'
        m = re.search(pattern, self.locale)
        if m == None:
            return None
        m = m.group()
        m = m.replace('E ','').replace('W ','')
        if m[-1] != 'M':
            raise Exception # Elevation not in metres
        m = m.strip('M')
        return int(m)
            
    def xyzmstring(self):
        '''Returns a WKT representation of the XYZM point, where M is UNIX time
        of the measurement (from the UTC recorded time).'''
        if self.locale is None or self.localeXY() is None:
            # It has no location, only an M value, so we don't populate its location
            return None
        # NOTE: have to give lon lat
        xyzm = (self.localeXY()[1], self.localeXY()[0], max(self.localeZ(),0), calendar.timegm(self.whenDatetime().utctimetuple()))
        return 'POINT ZM(%s %s %s %s)' % (str(xyzm[0]),str(xyzm[1]),str(xyzm[2]),str(xyzm[3]))
            
    def whenDatetime(self):
        '''Returns a datetime.datetime object representing the date and time of
        the data represents, in UTC.'''
        pattern = '\d\d\d\d.\d\d.\d\d \d\d\d\d UTC'
        m = re.search(pattern, self.when)
        if m == None:
            return None
        else:
            try:
                m = dt.datetime.strptime(m.group(), '%Y.%m.%d %H%M %Z')
            except ValueError, e:
                if '2400' in m.group():
                    # Ugh, 2400 is not a time!
                    m = m.group()
                    m = m.split(' ')[0]
                    m = dt.datetime.strptime(m,'%Y.%m.%d')
                    m = m + dt.timedelta(days=1)
                else:
                    print "Station {station}: cannot parse date/time {date}".format(station=self.station,date=self.when)
                    return None    
            return m
            
    def windSpeed(self, MPH=True):
        '''Returns the wind speed
        if MPH: returns an integer in miles per hour (MPH)
        else: returns an integer in knots (KT)'''
        if self.wind is None:
            return None
        if MPH == True:
            pattern = '\d+\sMPH'
        else:
            pattern = '\d+\sKT'
        m = re.search(pattern, self.wind)
        if m == None:
            if 'calm' in self.wind.lower():
                return 0
            else:
                return None
        else:
            return int(m.group().split(' ')[0])
    
    def windDirection(self):
        '''Returns the wind direction in degrees, as an integer
        Example input (self.wind): "Wind: from the SE (130 degrees) at 12 MPH (10 KT):0"
        Example output: 130'''
        if self.wind is None:
            return None
        pattern = '\d+\sdegrees'
        m = re.search(pattern, self.wind)
        if m == None:
            if 'calm' in self.wind.lower():
                return 0
            else:
                return None
        else:
            return int(m.group().strip(' degrees'))
    
    def temperatureTemp(self, celsius=True):
        '''Returns the temperature
        if celsius: returns an integer in degrees Celsius
        else: returns an integer in degrees fahrenheit'''
        if self.temperature is None:
            return None
        if celsius == True:
            pattern = '\d+\sC'
        else:
            pattern = '\d+\sF'
        m = re.search(pattern, self.temperature)
        if m == None:
            return None
        else:
            return int(m.group().split(' ')[0])
            
    def addIfMissing(self):
        '''Adds the data from self into metardb, if the data does not exist in
        the DB.
        NOTE: ON CONFLICT IGNORE and a primary key on the station code and the
        UTC time record control for repeated runs of the script and ensures data
        is not duplicated'''
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
    A class for a SQLite3/Spatialite database that will hold METAR data.
    '''
    def __init__(self, connstring, verbose=False):
        '''
        A SQLite3/Spatialite database connection and cursor. Handles database
        transactions for MetarTxtFile and foliumMap objects in such a way
        that the user should not even know they exists, unless they go looking for
        them and want to explore the data in depth (including harvested data
        that does not get displayed on the HTML map.
        
        Input:
        connstring -- path to database and name of database, e.g. './data/metar.sqlite'
        '''
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
        self.verbose = verbose # Verbose SELECT queries
        
    def tableCreate(self):
        '''Checks whether the table self.tableName exists, and creates it if it
        does not exist.
        If the table already exists, nothing happens.
        Also checks for the existence of spatialite metadata, and adds it if it
        does not exist.
        Then adds an XYZM point geometry column to self.tableName.'''
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
        '''Returns a string of the sqlite version number'''
        r = self.cur.execute('SELECT sqlite_version()')
        for l in r:
            return l[0]
    
    def getSpatialiteVersion(self):
        '''Returns a string of the spatialite version number'''
        r = self.cur.execute('SELECT spatialite_version()')
        for l in r:
            return l[0]
            
    def returnMostRecent(self, restrict=None, returnDict=False):
        '''Returns the most recent METAR record of all unique stations,
        provided that the data is not more than 24 hours old, by default as the
        output of self.cur.fetchall() (a list of tuples).
        X and Y coordinates (floats) are returned in EPSG:4326 coordinates (from
        the XYZM geom)
        
        Input:
        restrict -- Optionally, include a list of (string) stations for which
                    you are interested in, and the query will be restricted to
                    them.
        returnDict -- Optionally, return the values as a list of dictionaries,
                      with the column headers used as keys, rather than the
                      default output of self.cur.fetchall(). This is useful to 
                      be able to get values fro, the result using column names
                      rather than index positions from self.cur.fetchall(), 
                      which is harder to read and more fragile.'''
        if restrict != None:
            # Limit to given stations
            restriction = "AND station IN ("
            for s in restrict:
                restriction = restriction + "'" + s + "',"
            restriction = restriction[:-1] + ")"
        else:
            restriction = ""
        sql = '''SELECT X(geom) AS X, Y(geom) AS Y,
        station, label, country, utc, windspeed_mph, windspeed_kts, winddirection,
        temperature_c, temperature_f FROM metarvals
        WHERE rowid IN
	        (SELECT rowid FROM metarvals 
	        WHERE station = station
	        ORDER BY utc DESC)
	    %s
        AND CAST(M(geom) AS INTEGER) >= '%s' --M coordinate is time, so check currency
        GROUP BY station
        ORDER BY utc DESC;
        ''' % (restriction, str(nDaysAgo(1)))
        if self.verbose: print sql
        self.cur.execute(sql)
        if returnDict == False:
            return self.cur.fetchall()
        elif returnDict == True:
            # Return a list of dictionaries
            result, retval = self.cur.fetchall(), []
            for vals in result:
                retval.append({'X': vals[0], 'Y': vals[1], 'station': str(vals[2]),
                        'label': str(vals[3]), 'country': str(vals[4]),
                        'utc': str(vals[5]), 'windspeed_mph': vals[6],
                        'windspeed_kts': vals[7], 'winddirection': vals[8],
                        'temperature_c': vals[9], 'temperature_f': vals[10]})
            return retval
            
    def returnBoundingBox(self, restrict=None):
        '''Returns the bounding box of the points to be mapped, in EPSG:4326 coordinates
        Calls self.returnMostRecent(restrict)
        
        Input:
        restrict -- default None, a list of strings of METAR station names to
                    restrict the determination of the boounding box from.
        Output: 
        A tuple of tuples, containing a pair of floats representing coordinates
        of the form: lower left corner XY, upper right corner XY: ((X,Y),(X,Y))'''
        xs,ys = [],[]
        for pt in self.returnMostRecent(restrict=restrict):
            xs.append(pt[0]), ys.append(pt[1])
        return ((min(xs),min(ys)),(max(xs),max(ys)))
            
class foliumMap():
    '''
    A class for a Folium Map object, with methods to access the database and display
    the most recent weather information.
    '''
    def __init__(self, metardb, mapName, tiles, restrict=None, coastline=None):
        '''
        A new Folium.Map object, also requiring a database to link to, a name for
        the output HTML page, the tilles to use as a basemap. Can optionally
        be restricted to a subset of database's recorded stations, and (when a
        bug in Folium is addressed) include a GeoJSON overlay coastline.
        
        Inputs:
        metardb -- A metarsqlite3db object from this module
        mapName -- A string for what the map should be called, including the path.
                   must have an '.html' suffix to work correctly.
        tiles -- Folium tiles (Stamen, OSM, Mapbox, and others coming). It is also
                 possible for Folium to use custom (local) tiles, but this is not
                 implemented here. Give the string name, from the following list:
                 ["OpenStreetMap", "Mapbox Bright", "Mapbox Control Room",
                  "Stamen Toner"]
        restrict -- default None, a list of strings of METAR station names to
                    restrict the map to.
        coastline -- default None, a path to a GeoJSON overlay. This parameter is
                     is currently ignored, due to a bug in Folium.
        '''
        self.metardb = metardb
        self.mapName = mapName
        self.restrict = restrict
        self.coastline = coastline
        self.geoJSONbug = True # Disables the coastline overlay
        self.zoom_start = 6
        self.width = '100%'
        self.height = '100%'
        self.tiles = tiles
        self.bbox = metardb.returnBoundingBox(self.restrict)
        self.centrelat = (self.bbox[0][0]+self.bbox[1][0])/2.
        self.centrelon = (self.bbox[0][1]+self.bbox[1][1])/2.
        self.location = [self.centrelon,self.centrelat] # Centre of the map
        self.map = folium.Map(location=self.location,width=self.width,height=self.height,zoom_start=self.zoom_start,tiles=self.tiles)
        self.map.lat_lng_popover() # Will return the lat lon of a click on the map
        
    def addPoint(self, x, y, popup, point=True, rotation=None, fill_colour=None, radius=None):
        '''Adds a point (location and attributes) to self.map
        There are more style options than those used at present,
        try print(self.map.simple_marker.__doc__)
        
        Input:
        popup -- The text to be used on popup. Note that it must escape special
                 characters with a double backslash, and uses in-line HTML
                 formatting (e.g. bold tags <b></b> and linebreaks <br>
        point -- default True, use point markers (pins). If False, uses circle
                 markers.'''
        if point == True:
            # Add a point symbol
            self.map.simple_marker(location=[float(x),float(y)],
                popup=popup,
                popup_on=True
                )
        elif point == False:
            if radius == 0 and rotation == 0:
                # If there's no wind, plot a circle marker
                self.map.circle_marker(location=[x,y],popup=popup,radius=70000,line_color=fill_colour,fill_color=fill_colour)
            else:
                # If there's some wind, plot a triangle, rotated in the appropriate direction
                self.map.polygon_marker(location=[x,y],popup=popup,num_sides=3,rotation=rotation+30,radius=radius,fill_color=fill_colour)
        return None
        
    def tempColour(self, temp):
        '''Returns a hex colour value, drawn from a hardcoded classification,
        to display the temperature information.
        The classification is made from colorbrewer2, diverging classification,
        with 8 classes.
        
        Input:
        temp -- The temperature value (integer)
        '''
        if temp < 0:
            return '#2166AC'
        elif temp > 19:
            return '#B2182B'
        else:
            colours = {'#4393C3': range(0,4),
                       '#92C5DE': range(4,7),
                       '#D1E5F0': range(7,10),
                       '#FDDBC7': range(10,13),
                       '#F4A582': range(13,16),
                       '#D6604D': range(16,19)}
            for k in colours:
                if temp in colours[k]:
                    return k
                     
    def addOverlay(self):
        '''Adds a GeoJSON overlay to the Folium map.
        This seems to be causing errors in the Folium installed using Pip, and 
        also when compiled from source.'''
        self.map.geo_json(geo_path=self.coastline,
            line_color='black',
            line_weight=10,
            fill_opacity=0.6,
            reset=True
            )
        return None
        
    def makeMap(self, point=True):
        '''Makes the folium map, adding points and their popups, the overlay,
        and saving the map to disk as an HTML document, using parameters from
        self.__init__().
        
        Input:
        point -- Boolean, if True, makes point symbols with popup weather
                 information. If False, makes polygon markers that respond to
                 some of the weather attributes in their symbology (and still
                 have the same popups.
        '''
        for row in self.metardb.returnMostRecent(restrict=self.restrict, returnDict=True):
            try:
                popup = '%s, %s\nUTC %s\nWind speed: <b>%d mph</b>\nDirection: <b>%d degrees</b>\nTemperature: <b>%d C</b>' % (row['station'], row['label'], str(row['utc']), row['windspeed_mph'], row['winddirection'], row['temperature_c'])
            except:
                continue
            # Handle jQuery special characters in the pop-up
            for sc in [':',',','\n','-']:
                if sc == '\n':
                    replace = '<br>'
                else:
                    replace = '\\%s' % sc
                popup = popup.replace(sc,replace)
            self.addPoint(row['Y'],row['X'],str(popup),point=point,rotation=row['winddirection'],radius=row['windspeed_mph'],fill_colour=self.tempColour(row['temperature_c']))
        
        # Add the GeoJSON overlay
        if self.geoJSONbug == False:
            # If the Folium bug is repaired
            self.addOverlay()
        
        # Write the map HTML and JS
        self.map.create_map(path=self.mapName)
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
   
def main(stations=['NZWN','NZAA','NZCH'], metardb='./data/metar.db', output='METAR-vis.html', coastline=r'./data/test.json', tiles='Mapbox Bright', show=False, verbose=True):
    '''If this is run as the primary program, it harvests the data once
    optionally making and then displaying the map. This could be scheudled to 
    run every 30 minutes using cron, if you want to harvest data from particular
    stations, since the data retrieved is persistent in the database.
    
    Adjust the values in main essentially as a config file.
    
    Input (see default values for examples):
    stations -- A list of station names to retrieve/store/dislpay data for.
                Default: ['NZWN','NZAA','NZCH']
    metardb -- A path to the SQLite3 database. If it does not exist, it will be
               created.
    output -- Name and path of the output map
    coastline -- A GeoJSON layer for overlay on the map (at present, ignored due
                 to a bug in Folium)
    tiles -- The Folium-prescribed tiles to use as a basemap
    show -- Boolean controlling whether the map is made or not (False is more
            useful when harvesting)
    verbose -- Boolean (default True), prints the stations retrieved to the terminal.
    '''
    # Create or connect to DB
    metardb = metarsqlite3db(metardb, verbose=False)
    '''
    # Loop through stations we care about, adding their data to the DB if it
    # has not already been collected
    
    for i, station in enumerate(stations):
        if station == 'OMDI':
            index = i
            break
            
    for station in stations[index:]:
        if verbose: print(station)
        metar = METARTxtFile(station, metardb)
    '''
    if show == True:
        # Instantiate the map object and plot the relevant points
        fmap = foliumMap(metardb, output, tiles, stations, coastline)
        fmap.makeMap(point=False)
        while 1:
            webbrowser.open_new_tab(output)
            time.sleep(2) # Allow time to open the map, then return control
            break
    return None

def getStations():
    '''
    Gets all of the available METAR stations, as a list of station code strings.
    '''
    response = urllib2.urlopen('http://weather.noaa.gov/pub/data/observations/metar/decoded/')
    html = response.read()
    soup = BeautifulSoup(html).find_all('a')
    return [str(s.get('href')).split('.')[0] for s in soup if '.TXT' in str(s.get('href'))]
        
if __name__ == '__main__':
    main(stations=getStations(),show=True)
