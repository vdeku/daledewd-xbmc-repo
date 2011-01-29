import os
import xbmc

# You may need to change this path according your XBMC setup.
script_path = xbmc.translatePath(os.path.join(os.getcwd(),'..','addons','plugin.video.greader.ddl.video','httpserver.py'))
xbmc.executescript(script_path)
