import urllib2 # For acquring station data .TXT files
import re # For matching patterns in the .TXT files to extract useful data
from datetime import datetime # For creating a datetime object of the observation time

class METARTxtFile:
    '''
    A .TXT file of METAR data, at a particular place and time.
    '''
    def __init__(self, station):
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
        
        # TODO: Add a method to add it to a SQLite database, upon creation,
        #       if it has not already been written to it. Later, we can just display
        #       the most recent that is recorded, but still keep the others on file.
        
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
        return coords # YX tuple
        
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
            
    def whenDatetime(self):
        # Returns a datetime.datetime object representing the date and time of
        # the data represents, in UTC.
        pattern = '\d\d\d\d.\d\d.\d\d \d\d\d\d UTC'
        m = re.search(pattern, self.when)
        if m == None:
            return None
        else:
            dt = datetime.strptime(m.group(), '%Y.%m.%d %H%M %Z')
            return dt
            
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
            
def main():
    stations = ['NZWN', 'NZAA', 'NZCH', 'EQBI']
    for station in stations:
        metar = METARTxtFile(station)
        metar.displayText()
        print metar.station
        print metar.localeLabel()
        print metar.localeCountry()
        print metar.localeXY()
        print metar.localeM()
        print metar.whenDatetime()
        print metar.windSpeed()
        print metar.windSpeed(False)
        print metar.windDirection()
        print metar.temperatureTemp()
        print metar.temperatureTemp(False)
        print "\n"
        
if __name__ == '__main__':
    main()
