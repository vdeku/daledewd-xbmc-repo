import sys
import urllib
import xbmc
import xbmcgui
from pprint import pprint


class GUI( xbmcgui.WindowXMLDialog ):
    ACTION_EXIT_SCRIPT = ( 9, 10, )

    #
    # Init
    #
    def __init__( self, *args, **kwargs ):
        xbmcgui.WindowXML.__init__( self )
        # Parse plugin parameters...
        self.params = dict(part.split('=') for part in sys.argv[ 2 ][ 1: ].split( '&' ))

        # Prepare parameter values...
        self.title        = unicode( xbmc.getInfoLabel( "ListItem.Title" ), "utf-8" )
        self.dateTime     = unicode( xbmc.getInfoLabel( "ListItem.Date" ), "utf-8" )
        self.author       = unicode( xbmc.getInfoLabel( "ListItem.Writer" ), "utf-8" )
        self.content      = unicode( xbmc.getInfoLabel( "ListItem.Plot" ), "utf-8" )
                
        # Show dialog window...
        self.doModal()        


    #
    # onInit handler
    #
    def onInit( self ):
        self.getControl( 10 ).setLabel( self.title )
        self.getControl( 20 ).setLabel( self.dateTime )
        self.getControl( 30 ).setLabel( self.author )
        self.getControl( 40 ).setText ( self.content )
        self.getControl( 50 ).setLabel( 'OK' )

    #
    # onClick handler
    #
    def onClick( self, controlId ):
        # OK
        if (controlId == 50) :
            self.close()

    #
    # onFocus handler
    #
    def onFocus( self, controlId ):
        pass

    #
    # onAction handler
    #
    def onAction( self, action ):
        if ( action in self.ACTION_EXIT_SCRIPT ):
            self.close()
