# save this file as ......| test1.py
# run this file this way..| python  test1.py
import sys
import os
import urllib2
import time
import webbrowser
import shutil

import easygui as eg # Import the GUI library, based on Qt
import main as m # Import main.py, the workhorse


# Parameters (all of these need defaults, and type constraints)
# String name (and path) to database (or just force the use of the given one...)
# Coastline JSON (if I can get this to work...)
# Then open output in browser, and tell user

def getMetarStations(metarValues):
    '''
    Takes the user-supplied and (hopefully) comma-delimited string of METAR
    stations that they're interested in, and returns a list of strings of possible
    stations. These are constrained to be four characters long, are forced to
    upper case, and checked to only contain alphanumeric characters. If an error
    is raised during the process, False is returned, along with a (possibly
    blank) additional error message.
    '''
    metars = metarValues.strip().upper().split(',')
    for m in metars:
        m = m.strip()
        if m.isalnum() == False:
            return False, '' # There is a non-alphanumeric character
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
    msg = "Enter the METAR stations you are interested in collecting information for as a comma-separated list below."
    title = "METAR-vis"
    default = 'NZWN,NZAA,NZCH'
    metarValues = eg.enterbox(msg=msg,title=title,default=default)

    # Error check the user input
    while 1: # Loop continuosly, until all values are acceptable
        
        if metarValues is None:
            cancel()
        errmsg = ""
        
        # Check the validity of user-suppled METAR values
        metarstations = getMetarStations(metarValues)
        if metarstations[0] == False:
            note = ""
            # The metar stations were not listed correctly or at least one does not exist
            if metarstations[1] != '': # If there's an additional note
                note = '\n\n' + metarstations[1]
            errmsg = msg + errmsg + ('\n\nERROR: This must be comma-separated list of four-character and extant METAR identification codes. These must be alphanumeric. See http://weather.noaa.gov/pub/data/observations/metar/decoded/ for the list of possibilities.%s\n' % note)
        
        if errmsg == "": 
            break # no problems found
        else:
            # show the box again, with the errmsg as the message    
            metarValues = eg.enterbox(errmsg, title, default, metarValues)
            
    return metarstations
    
def userOutdir():
    '''
    Asks the user to point to a directory indicating where the output file should
    be created. Returns a string path to the directory if given. If the user
    chooses to cancel, the program closes. The output is not checked for any
    form of vallidty, as it only becomes a default in a later window that the
    user can overwrite: the error checking is performed then.
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
               #"Stamen Terrain", # This option does not seem to load
               "Stamen Toner"]
    choice = eg.choicebox(msg,title,choices)
    if choice == None:
        # User cancelled
        cancel()
    return choice.split('(')[0].strip() # Remove the additional note from the Mapbox options
    
def userOutput(outDir,defaultOutput='METAR-vis.html'):
    '''
    Asks the user what they want to call the map. This is an HTML document that
    will be saved to the directory they specified in the previous step.
    '''
    default = outDir+"/"+defaultOutput
    msg = "Set the name and location of output leaflet map.\n\nDefault: %s" % default
    title = "METAR-vis"
    output = eg.enterbox(msg=msg,title=title,default=default)
    
    # Error check the user input
    while 1: # Loop continuosly, until all values are acceptable
        if output == None:
            # User cancelled
            cancel()
        errmsg = ""
        
        # Check that the directory exists
        checkDir = '/'.join(output.split('/')[0:-1])
        if not os.path.isdir(checkDir):
            # The user has not specified an existing directory
            note = '%s is not an existing directory' % checkDir
            errmsg = msg + "\n\nERROR: " + note + "\n"
        
        # Check that the suggested output file is an HTML
        # If not, just silently overwrite it
        if output.split('.')[-1] != 'html':
            output = output.split('.')[0] + '.html'
        if errmsg == "":
            break
        else:
            output = eg.enterbox(msg=errmsg,title=title,default=default)
               
    return output
    
def cancel():
    '''What happens whena user presses cancel: the program exits'''
    sys.exit(0)
    
def run(stations,output,tiles,verbose=False):
    '''
    Once the GUI has gathered the required parameters, this function runs main.py
    with them, which scrapes the information from NOAA, adds it to the bundled
    spatialite database, creates a leaflet map using Folium, and then opens it.
    
    Parameters:
    stations -- A list of METAR stations
    outpath -- A string representing the path for the output and the name of the output file
    tiles -- A string (from a constrained list) of tiles that the map can be made with
    '''
    # Create MetarTxtFile objects from the stations, which also adds to the database
    metardb = m.metarsqlite3db('./data/metar.db')
    for station in stations:
        metar = m.METARTxtFile(station, metardb)
        if verbose: print(station)
    
    # Instantiate the map object, and make the map (loops through adding collected points)
    fmap = m.foliumMap(metardb,output,tiles,restrict=stations,coastline=None)
    
    # Make the map
    fmap.makeMap(point=False)
    while 1:
        webbrowser.open_new_tab(output)
        time.sleep(2) # Allow time to open the map, then return control
        break
    return None
    
def copyMarkers(outdir,markers='leaflet-dvf.markers.min.js'):
    '''
    If the user opts for a non-default destination for their output map, 
    they also need the marker style to be alongside the HTML. This function
    copies it from ./source (where it is created with each run) to the output
    directory `outdir`.
    '''
    try:
        shutil.copyfile(markers,outdir+'/'+markers)
    except:
        # They're the same file, or the directory is not writable
        pass
    time.sleep(1) # give time for the markers to copy before continuing
    return None
            
def main():
    # Easygui is *not* an event-based gui, so it's a lot easier to program, and extend
    # Here we basically just use it to gather a bunch of parameters to feed into main.py
    metars = userMetar() # List of metar values
    outdir = userOutdir() # Output path
    output = userOutput(outdir)
    tiles = userTiles() # Tiles for Folium basemap
    # Copy leaflet-dvf.markers.min.js to the same dir as the HTML will be
    copyMarkers(outdir)
    # Retrieve, store, query and display the data
    run(metars,output,tiles,False)
    
    
if __name__ == '__main__':
    main()



