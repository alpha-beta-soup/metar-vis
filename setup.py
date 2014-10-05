# /usr/bin/env python
'''
Setup script for bbFreeze

Usage: `python setup.py`

After `setup.py` has created the executable in its directory, there is still work to be done. Just running the executable without this work leads to an error with `Jinja2` being unable to find the `folium/templates` and `folium/plugins` directories. This is because `bbFreeze` seems to ignore them when compiling the Folium Python library to the standalone, as they are not Python scripts, but local `.txt` files.

So, after running `python setup.py`, open `distdir` and find `library.zip`.
1. Copy `library.zip` to the Desktop or other suitable place.
2. Extract (unzip) the files from `library.zip` to the Desktop.
3. Find where Folium is installed on your computer (probably `/usr/local/lib/python2.7/dist-packages/folium/`).
3. In the Folium installation, find `/templates` and `/plugins`. These are the folders that don't contain any `.py` files, so are ignored when bbFreeze does its (sub-optimal) magic. Paste these into the extracted `library` (on the Desktop) at `/Desktop/library/folium/`.
4. Now, you've fixed the only problem with bbFreeze for our purposes. Zip up `/Desktop/library` on the command line with `cd Desktop/library/ && sudo zip -r library.zip .`.
5. Copy this **new** `library.zip` (it will be inside `Desktop/library/library.zip`) and paste over the old one in `\distdir`.
6. You're ready to go! Now when you run the executable, it will be able to find the tile templates and JS plugins it needs to create and display the map! 
'''

from bbfreeze import Freezer
f = Freezer(distdir="metarvis-1.0")
f.addScript("./source/main.py")
f.addScript("./source/metarvis-gui.py")
f()
