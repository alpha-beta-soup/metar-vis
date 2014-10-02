# save this file as ......| test1.py
# run this file this way..| python  test1.py
import easygui as eg
import sys
import main
import urllib2

# Parameters (all of these need defaults, and type constraints)
# String name (and path) to database (or just force the use of the given one...)
# Width of map >> Suggested ratios
# Height of map
# Coastline JSON (if I can get this to work...)
# Name of output

# Then open output in browser, and tell user

# First patch the easygui windowposition determination so the boxes don't move around
from Tkinter import Tk

def getMetarStations(metarValues):
    '''
    Takes the user-supplied and (hopefully) comma-delimited string of METAR
    stations that they're interested in, and returns a list of strings of possible
    stations. These are constrained to be four characters long, are forced to
    upper case, and can only contain letters, or else False is returned, along
    with a (possible blank) additional error message.
    '''
    metars = metarValues.strip().upper().split(',')
    for m in metars:
        m = m.strip()
        if m.isalpha() == False:
            return False, '' # There is a non-alphabetic character
        if len(m) != 4:
            return False, '' # The string is not four letters long
        # Check if they are actually stations
        if checkMetarExists(m) == False:
            return False, 'ERROR: Station %s does not exist' % m
    return metars

def checkMetarExists(metarstation):
    '''
    Checks that a user-suppled METAR station exists before processing it.
    Returns True if it does, False if it does not.
    '''
    source = 'http://weather.noaa.gov/pub/data/observations/metar/decoded/'
    station = source + metarstation + '.TXT'
    try:
        urllib2.urlopen(station)
        return True
    except ValueError, ex:
        return False # URL not well formatted
    except urllib2.URLError, ex:
        return False # URL not active
        
def userMetar():
    '''
    Seeks user input for a list of METAR stations to retrieve, returning a list
    of these stations (strings) only once they have been given without error.
    If the user chooses to cancel, the program closes.
    '''
    # Get the METAR station codes from the user
    msg = "To view the most recent METAR data, complete this form"
    title = "METAR-vis"
    metars = ["METAR Station Codes"]
    metarValues = []  # we start with blanks for the values
    metarValues = eg.multenterbox(msg,title,metars)

    # Error check the user input
    while 1: # Loop continuosly, until all values are acceptable
        
        if metarValues is None:
            cancel()
        errmsg = ""
        
        # Check the validity of user-suppled METAR values
        metarstations = getMetarStations(metarValues[0])
        if metarstations[0] == False:
            # The metar stations were not listed correctly or at least one does not exist
            example, note = "NZAA,NZCH", ""
            if metarstations[1] != '': # If there's an additional note
                note = note + metarstations[1] + '\n'
            errmsg = msg + errmsg + ('\n\nERROR: "%s" must be comma-separated list of four-letter existing METAR identification codes.\nExample: %s\n\n%s' % (metars[0], example, note))
        
        if errmsg == "": 
            break # no problems found
        else:
            # show the box again, with the errmsg as the message    
            metarValues = eg.multenterbox(errmsg, title, metars, metarValues)
            
    return metarstations
    
def userOutdir():
    '''
    Asks the user to point to a directory indicating where the output file should
    be created. Returns a string path to the directory if given. If the user
    chooses to cancel, the program closes. The output is not checked for any
    form of vallidty.
    '''
    dirbox = eg.diropenbox(title="Select output directory for map")
    if dirbox is None:
        cancel()
    return dirbox
    
def userTiles():
    '''
    Presents the user with a list of choices for the tiles to be used as a base
    layer for the output map. The options are from Folium.
    Note that Folium also allows the user to give custom tiles, but this is not
    implemented. Returns the name of the choice if made, or None if the user
    cancelled.
    '''
    msg = "Pick a base layer"
    title = "METAR-vis"
    choices = ["OpenStreetMap",
               "Mapbox Bright (limited levels of zoom)",
               "Mapbox Control Room (limited levels of zoom)",
               "Stamen Terrain",
               "Stamen Toner"]
    choice = eg.choicebox(msg,title,choices)
    if choice == None:
        # User cancelled
        cancel()
    return choice
    
def cancel():
    '''What happens whena user presses cancel: the program exits'''
    sys.exit(0)
            
def main():
    # Easygui isn't that pretty... but it's easy to program for this given it's
    # not event-based.
    metars = userMetar() # List of metar values
    outdir = userOutdir() # Output path
    tiles = userTiles() # Tiles for Folium basemap
    
    print ("Reply was:", metars)
    print ("Outdir: ", outdir)
    print ("Tiles: ", tiles)
    
if __name__ == '__main__':
    main()



