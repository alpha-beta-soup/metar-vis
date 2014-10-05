# METAR-vis

Retrieve, view, store and map METAR meterological information.

METAR data are routine weather reports provided at fixed intervals.
This is a minimal module to scrape METAR the most recent METAR information
for a set of user-defined stations, store it in a SQLite/Spatialite database
for posterity, and display the most recent reports on a Leaflet map.

## Usage

One can use the standalone Linux GUI, or execute the source code.

For the former, at the commandline enter the following:
`./metarvis-1.0/metarvis-gui` for the graphical version, and `./metarvis-1.0/main`
for the automatic version (which has constrained stations to retrieve data from).

For the latter option, you can execute `python source/main.py` to execute `main.py`
for a non-GUI option (tweak the paramets in `main.py`'s `main()` method. You can
also still run the GUI as `python source/metarvis-gui`. This may be useful if you
want to extend the GUI with some new functionality.

## Installation

If opting for the standalone executable, it's a standalone executable for a reason. You just have to run it.

Of course, if not opting for the standalone GUI, you must also install dependencies, which are
listed in `requirements.txt`. With Python 2.7, You should be able to get away with doing
`pip install pyspatialite` and `pip install folium` (and possibly also `pip install easygui` if you also want the GUI),
although these have their own dependcies (including numpy and pandas) which may not be resolved. That's why the standalone executable could be useful.

## Roll-your-own GUI

If you make changes to the source and then want to make a new standalone version, best of luck. It actually took twice as long to make this executable than it did to write the actual program.

Still if you want to try, I used `bbFreeze` to make one on Linux. This largely requires that you appropriately edit `setup.py`, and then run `python setup.py`.

After `setup.py` has created the executable in its directory, there is still work to be done. Just running the executable without this work leads to an error with `Jinja2` being unable to find the `folium/templates` and `folium/plugins` directories. This is because `bbFreeze` seems to ignore them when compiling the Folium Python library to the standalone, as they are not Python scripts, but local `.txt` files.

So, after running `python setup.py`, open `distdir` and find `library.zip`.

1. Copy `library.zip` to the Desktop or other suitable place.
2. Extract (unzip) the files from `library.zip` to the Desktop.
3. Find where Folium is installed on your computer (probably `/usr/local/lib/python2.7/dist-packages/folium/`).
3. In the Folium installation, find `/templates` and `/plugins`. These are the folders that don't contain any `.py` files, so are ignored when bbFreeze does its (sub-optimal) magic. Paste these into the extracted `library` (on the Desktop) at `/Desktop/library/folium/`.
4. Now, you've fixed the only problem with bbFreeze for our purposes. Zip up `/Desktop/library` on the command line with `cd Desktop/library/ && sudo zip -r library.zip .`.
5. Copy this **new** `library.zip` (it will be inside `Desktop/library/library.zip`) and paste over the old one in `\distdir`.
6. You're ready to go! Now when you run the executable, it will be able to find the tile templates and JS plugins it needs to create and display the map! 
