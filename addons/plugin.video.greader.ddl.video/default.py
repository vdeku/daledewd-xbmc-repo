import pickle
from libgreader import GoogleReader, OAuthMethod, ClientAuth, Feed
import html2text
import rarfile
import urllib
import urllib2
from urllib2 import HTTPError,URLError
from urlparse import urlparse
import xbmc, xbmcgui, xbmcaddon, xbmcplugin
import sys
import os
import inspect
import re
import md5
import traceback
import time
from datetime import datetime
from pprint import pprint

from TaskQueue import TaskQueue
from threading import Thread

DEBUG = True

xbmcplugin.setContent(int(sys.argv[1]), 'movies')


#############################################

# addon_path is this plugins path. i.e. plugin://plugin.video.myplugin/
def switchToLibraryMode(addon_path):
    # are we in library mode yet?
    if xbmc.getCondVisibility("[Window.IsActive(videolibrary)]") == 0:
        # on first call the Container.FolderPath will contain the previous windows path. i.e. addons://sources/video/
        # xbcm will call our script again when user tries to back out because it would have loaded our initial index even though
        # we only wanted to change window to video library. so...
        # on second call (user is backing out of script) it will contain this plugins id path. i.e. plugin://plugin.video.myplugin/
        container_folder_path = xbmc.getInfoLabel('Container.FolderPath')
        xbmc.executebuiltin("XBMC.ReplaceWindow(VideoLibrary,%s)" % addon_path)
        """
        if not addon_path in container_folder_path:
            # first time in so switch to library mode.
            # save previous folder path for when user backs out of our plugin.
            __settings__.setSetting('previous_folder_path', container_folder_path)
            doLog("SWITCHING TO LIBRARY MODE")
            xbmc.executebuiltin("XBMC.ActivateWindow(VideoLibrary,%s,return)" % addon_path)
        else:
            # user trying to back out of our plugin so return to previous window
            #xbmc.executebuiltin("XBMC.ReplaceWindow(Home,%s)" % __settings__.getSetting('previous_folder_path'))
            xbmc.executebuiltin("Container.Update(%s,replace)" % __settings__.getSetting('previous_folder_path'))
        """
        
        # do not cacheToDisc cuz we want this code rerun
        xbmcplugin.endOfDirectory( myhandle, succeeded=True, updateListing=False, cacheToDisc=False )
    else:
        doLog("ALREADY IN LIBRARY MODE")

def showBaseIndex():
    global reader
  
    addDir( 'SEARCH', 'SEARCH', 6 )
    #addDir( 'TVCAT', 'user/12746610621246208421/label/TV', 100 )
    #addDir( 'PLAYLIST TEST', 'PLAYLIST TEST', 99 )
    #addDir( 'RAR Play Test', 'RAR_PLAY_TEST', 999 )

    categories = reader.getCategories()
    for category in categories:
        #print 'CATEGORY ID: %s    LABEL: %s' % ( str(category.id), str(category.label) )
        addDir( category.label.encode('utf-8'), category.id, 2 )

      
def showIndex( categoryId ):
    global reader

    category = reader.getCategory( categoryId )
    feeds = category.getFeeds()
    for feed in feeds:
        #print 'FEED ID: %s    TITLE: %s' % ( str(feed.id), str(feed.title) )
        addDir( feed.title.encode('utf-8') + ' (' + str(feed.unread) + '  unread)', feed.id, 3 )
        

# getting all items in a category instead of individual feed
def testGetCategoryContents( categoryId ):
    global reader

    reader.buildSubscriptionList()
    category = reader.getCategory( categoryId )
    items = reader.itemsToObjects( category, reader.getCategoryContent( category, excludeRead=True )['items'] )
    try:
        for item in items:
            itemTitle = item.title.encode('utf-8')
            itemUrl = item.url
            thumbnail = getFeedItemImage( item.content.encode('utf-8') )
            itemPlot = item.content.encode('utf-8')
            addDir( itemTitle, itemUrl, 4, thumbnail=thumbnail, plot_text=itemPlot, feed_item=item )
    except TypeError, e:
        traceback.print_exc()
        pass

def getTVComId( content ):
    try:
        return re.search(r'www.tv.com/(.+/?)/show/(\d+)/', content, re.I|re.S).group(1)
    except:
        return None

def getImdbId( content ):
    try:
        return re.search(r'imdb.com/title/(tt\d+)', content, re.I|re.S).group(1)
    except:
        return None

def showFeedItems( feedId ):
    global reader

    feed = reader.getFeed( feedId )
    feed.loadItems( excludeRead=True )
    items = feed.getItems()

    try:
        for item in items:
            #print "ITEM ID: %s \nTITLE: %s \nURL: %s" % ( str(item.id), str(item.title), str(item.url) )
            #pprint( item.data['enclosure'][0]['href'] )

            title = item.title.encode('utf-8')
            thumbnail = getFeedItemImage( item.content )
            imdb_id = getImdbId( item.content )
            if not imdb_id: # maybe its a tv show. TODO CHANGE NAME imdb_id CUZ WE MIGHT HAVE A TV.COM LINK!
                imdb_id = getTVComId( item.content )
            itemPlot = item.content

            # prepare to test type of feed item. lot of try's to be thorough
            try:
                item_enclosure_url = item.data['enclosure'][0]['href']
            except:
                try:
                    item_enclosure_url = item.data['alternate'][0]['href']
                except:
                    item_enclosure_url = ''

            try:
                item_enclosure_type = item.data['enclosure'][0]['type']
            except:
                try:
                    item_enclosure_type = item.data['alternate'][0]['type']
                except:
                    item_enclosure_type = ''

            try:
                item_enclosure_size = int(item.data['enclosure'][0]['length'])
            except:
                try:
                    item_enclosure_size = int(item.data['alternate'][0]['length'])
                except:
                    item_enclosure_size = 0
            
            # is this an nzb?
            if item_enclosure_url.lower().endswith('.nzb') or item_enclosure_type.lower() == 'application/x-nzb':
                # yes it is so send to sabnzb addon
                url = 'plugin://plugin.program.SABnzbd/?download_nzb="""%s!?!%s!?!%s!?!%s"""' % ( urllib.quote_plus(item_enclosure_url), title, '', 'movies' )
                addLink( name=title, url=url, thumbnail=thumbnail, plot_text=itemPlot, size=item_enclosure_size )
            else:
                # no it isnt
                addDir( title, item.url, 4, thumbnail=thumbnail, plot_text=itemPlot, feed_item=item, imdb_id=imdb_id )
                
    except TypeError:
        traceback.print_exc()
        pass

# specific to direct download sites.
def showFeedItemLinks( url ):
    global hotfile_user, hotfile_pass

    doLog( "showFeedItemLinks: getUrl for url: " + str( url ) )
    dp = xbmcgui.DialogProgress()
    parsed_url = urlparse(url)
    dp.create("Retrieving web page:", parsed_url[1], parsed_url[2].split("/")[-1])
    page = getUrl( url )
    dp.update(100, "Done.")
    del dp
    doLog( "showFeedItemLinks: getUrl returned" )
    if not page:
        return False

    singleFileLinks = getSingleFileLinks( page )
    doLog( "showFeedItemLinks: getSingleFileLinks returned: %s" % "\n".join(singleFileLinks) )
    multiPartLinks = getMultiPartLinks( page )
    doLog( "showFeedItemLinks: getMultiPartLinks returned: %s" % multiPartLinks )

    if not singleFileLinks and not multiPartLinks:
        # check for iframes for metasites such as katz:
        iframes = re.findall(r'<iframe.+?src=["|\'](.+?)["|\'].*?>', page, re.I)
        if iframes:
            ret = showFeedItemLinks( iframes[0] )
            if ret:
                return ret

        errorNotice = 'XBMC.Notification("VALID LINKS NOT FOUND!","No DDL links found on this page or were removed.", 5000)'
        xbmc.executebuiltin( errorNotice )
        return False

    if singleFileLinks:
        for link in singleFileLinks:
            name = link.split("/")[-1]
            addLink( name=name, url=link )

    if multiPartLinks:
        for name in multiPartLinks:
            link = multiPartLinks[name][0]
            video_name = "%s (%d rars)" % (name, len(multiPartLinks[name]))
            addDir( video_name, link, 44 )

    return True


# show video files within rars
def showRarVideos( url ):
    VIDEO_EXTENTIONS = xbmc.getSupportedMedia('video').split('|')
    # remove some archive extensions
    VIDEO_EXTENTIONS.remove(".rar")
    VIDEO_EXTENTIONS.remove(".001")
    VIDEO_EXTENTIONS.remove(".url")

    found_video_file = False

    dp = xbmcgui.DialogProgress()
    dp.create("Finding video files in rar. Be Patient!")

    def info_callback(raritem):
        try:
            currently_reading_rar_volume_file = raritem.volume_file.split('/')[-1]
            completed = (raritem.volume+1 * 100) / 15
            dp.update(completed, 'Reading rar data for the following rar file...', currently_reading_rar_volume_file, 'VOLUME #%s' % raritem.volume)
            doLog("%s\n%s\n%s" % (raritem.file_offset, raritem.volume_file.split('/')[-1], raritem.type))
        except:
            pass

    rar_file = rarfile.RarFile( url, crc_check=False, info_callback=info_callback )
    if rar_file.needs_password():
        errorNotice = 'XBMC.Notification("RAR IS PASSWORD PROTECTED!","Cannot handle a password protected archive.", 5000)'
        xbmc.executebuiltin( errorNotice )
        dp.close()
        return False

    for filename in rar_file.namelist():
        file_info = rar_file.getinfo(filename)
        doLog( "\tRAR INFO needs_password: %s - volume: %s - volume_file: %s - compress_type: %s" % (file_info.needs_password(), file_info.volume, file_info.volume_file, file_info.compress_type))

        filename = filename.replace('\\','/')
        dp.update(0, filename)
        doLog( "FILENAME FOUND: %s" % filename )

        # test for an extension otherwise skip
        try:
            file_ext_lower = "." + filename.lower().split('.')[-1]
            doLog( "Checking Extension: %s" % file_ext_lower )
            if file_ext_lower in (".rar",".001"):
                errorNotice = 'XBMC.Notification("Archive within archive detected!","Cannot handle double packed archives.", 2000)'
                xbmc.executebuiltin( errorNotice )
            if file_ext_lower in VIDEO_EXTENTIONS:
                # use the rar volume_file which holds the actual url to where this video file starts in the set.
                # otherwise videos further in the set won't play. SWEET!
                video_url = urllib.quote( file_info.volume_file ).replace("-", "%2d").replace(".", "%2e").replace("/", "%2f")
                video_url = "rar://" + video_url + "/" + filename
                found_video_file = True
                doLog( "addLink( name=%s, url=%s)" % (filename, video_url))
                addLink( name=filename, url=video_url)
        except:
            pass
    dp.close()
    return found_video_file


# feedId will allow searching specific feeds using the context menu at a later time.
def doSearch( feedId ):
    global reader
    
    searchTerm = get_keyboard()
    searchResults = reader.doSearch( searchTerm )
    #print "searchResults: " + str(type(searchResults))
    #pprint( searchResults )
    
    # cannot handle unicode mixed just yet so "try"
    try:
        for searchResult in searchResults:
            searchResultThumbnail = ''
            searchResultTitle = ''
            searchResultFeedTitle = ''
            searchResultUrl = searchResult['alternate'][0]['href']

            if searchResult.has_key( 'content' ):
                searchResultThumbnail = getFeedItemImage( searchResult['content']['content'] )
            if searchResult.has_key( 'title' ):
                searchResultTitle = searchResult['title'].encode('utf-8')
            if searchResult.has_key( 'origin' ):
                if searchResult['origin'].has_key( 'title' ):
                    searchResultFeedTitle = searchResult['origin']['title'].encode('utf-8')

            addDir( searchResultTitle + ' : ' + searchResultFeedTitle, searchResultUrl, 4, thumbnail=searchResultThumbnail )
    except TypeError:
        pass

    
def viewFeedItem( feedId ):
    global reader

    print "VIEWFEEDITEM: " + str( feedId )
    import MovieInfoGUI
    gui = MovieInfoGUI.GUI( "MovieInfoGUI.xml", os.getcwd(), "default" )
    del gui

def markFeedRead( feedId ):
    global reader

    dp = xbmcgui.DialogProgress()
    dp.create("Marking feed read", feedId)
    feed = reader.getFeed( feedId )
    if feed is None:
        feed = reader.getFeed( feedId + '/' )

    feed.markAllRead()
    del dp
        

def getFeedItemImage( content ):
    try:
        imgUrls = re.findall( 'img .*?src="(.*?)"', content, re.M|re.S )
    except TypeError:
        imgUrls = None

    if imgUrls:
        for imgUrl in imgUrls:
            if imgUrl.lower().endswith('.jpeg') or \
                imgUrl.lower().endswith('.jpg') or \
                imgUrl.lower().endswith('.gif') or \
                imgUrl.lower().endswith('.png'):
                return imgUrl

    return None

def hotfileapicall(action, user, pas, params):
        pwmd5= md5.new(pas).hexdigest()
        #print pwmd5
        url = 'http://api.hotfile.com/'
        data={'action': action,'username': user, 'passwordmd5': pwmd5}
        for par in params:
               data[par]=params[par]
        data=urllib.urlencode(data)
        req = urllib2.Request(url+"?"+data)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.8.1.14) Gecko/20080404 Firefox/2.0.0.14')
        try:
            response = urllib2.urlopen(req)
        except:
            return ""
        return response.read()

def getHFLink(user,pas,url):
    link = hotfileapicall("getdirectdownloadlink",user,pas,{"link":url}).strip()
    if ( link[0:4] == "http" ):
        return link
    return ""


# find single video file links
def getSingleFileLinks( text ):
    links = []
  
    doLog( "getSingleFileLinks start" )
    dp = xbmcgui.DialogProgress()
    dp.create("Searching for single file links", "")

    doLog( "getSingleFileLinks finding matches" )
    link_matches = re.findall( r'(http://hotfile.com/[^"]+/([^"]+).(flv|mpg|mpeg|mov|avi|mkv).html)', text, re.M|re.S )

    if not link_matches:
        doLog( "getSingleFileLinks no links found" )
        dp.update(100,"None found")
        del dp
        return links

    dp.update(0, "Removing duplicate links")
    link_matches[:] = dedupeList( link_matches, 0 )

    num_fetch_threads = 4
    url_queue = TaskQueue()
    def validateUrlsThread(i, q):
        """This is the worker thread function.
        It processes items in the queue one after
        another.  These daemon threads go into an
        infinite loop, and only exit when
        the main thread ends.
        """
        while True:
            url = q.get()
            valid_link = getHFLink( hotfile_user, hotfile_pass, url )
            if valid_link:
                links.append( valid_link )
            else:
                doLog( "getSingleFileLinks NOT ADDING: " + url )
            q.task_done()

    # Set up some threads to validate the urls
    for i in range(num_fetch_threads):
        worker = Thread(target=validateUrlsThread, args=(i, url_queue,))
        worker.setDaemon(True)
        worker.start()

    if link_matches:
        doLog( "getSingleFileLinks iterate over link matches" )
        for link,name,extension in link_matches:
            parsed_url = urlparse(link)
            dp.update(0, "Validating link:", parsed_url[1], parsed_url[2].split("/")[-1])
            doLog( "getSingleFileLinks appending:\nLINK: %s\nNAME: %s\nEXT: %s" % ( link, name, extension ) )
            url_queue.put(link)
        # wait for queue to empty which means all urls validated
        url_queue.join()

    doLog( "getSingleFileLinks done" )
    dp.update(100, "Done getting single file links!")
    del dp
    return links


# find multirar links. (also single rars cuz cannot disable xbmc insane subtitle search)
# returns a dict of lists.
# index 0 is the filename without the extension.
def getMultiPartLinks( text ):
    link_group = {}
    if not USE_REDIRECT_SERVER:
        return link_group

    doLog( "getMultiPartLinks start" )
    dp = xbmcgui.DialogProgress()
    dp.create("Searching for multi file links", "")


    doLog( "getMultiPartLinks finding matches" )
    link_matches = re.findall( r'(http://hotfile.com/dl/\w+/\w+/([^"<>\n, ]+)(.part(\d+)?).rar(.html)?)', text, re.M|re.S )

    if not link_matches:
        doLog( "getMultiPartLinks no links found" )
        dp.update(100,"None found")
        del dp
        return link_group
    else:
        doLog( "getMultiPartLinks: found %d links" % len(link_matches) )

    dp.update(0, "Removing duplicate links")
    link_matches[:] = dedupeList( link_matches, 0 )

    if link_matches:
        doLog( "getMultiPartLinks iterate over link matches" )
        for link,name,ispart,partNumber,extension in link_matches:
            doLog( "getMultiPartLinks appending:\nLINK: %s\nNAME: %s\nPART #: %s\nEXT: %s" % ( link, name, partNumber, extension ) )
            link_group.setdefault(name, []).append(link)

    # make sure all the links for this video are good
    for name in link_group.keys():
        valid_links = []
        for idx,link in enumerate(link_group[name]):
            parsed_url = urlparse(link)
            dp.update(idx, "Validating link:", parsed_url[1], parsed_url[2].split("/")[-1])
            valid_link = getHFLink( hotfile_user, hotfile_pass, link )
            if not valid_link:
                # found bad link so removing entire group of links
                doLog( "getMultiPartLinks: Not adding group: %s " % name )
                dp.update(idx, "Link is bad:", link)
                del link_group[name]
                break
            else:
                dp.update(idx, "Link is good:", link)
                valid_links.append(valid_link)

            if link_group[name]:
                link_group[name] = valid_links

    def natsort(list_):
        # decorate
        tmp = [ (int(re.search('\d+', i).group(0)), i) for i in list_ ]
        tmp.sort()
        # undecorate
        return [ i[1] for i in tmp ]

    # create new redirects
    for name in link_group:
        req = urllib2.Request( REDIRECT_SERVER_URL, "\n".join(link_group[name]) )
        try:
            response = urllib2.urlopen( req )
        except IOError:
            errorNotice = 'XBMC.Notification("REDIRECT SERVER ERROR!","Couldnt connect to redirect server.", 5000)'
            xbmc.executebuiltin( errorNotice )
            return []
       	# some sites dont have their links sorted so lets do it
        new_urls = natsort(response.read().split("\n"))
        link_group[name] = new_urls

    doLog( "getMultiPartLinks done" )
    dp.update(100, "Done getting multi file links!")
    del dp
    return link_group



def getUrl(url):
    #dont load ad or misc content. some sites use these in iframes which we might check for.
    for bad_url in [ 'http://ad.', 'www.facebook.com' ]:
        if bad_url in url:
            print "getURL: Skipping ad url: %s" % url
            return False

    request = urllib2.Request( url )
    request.add_header( 'User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3' )
    try:
        response = urllib2.urlopen( request )
        content = response.read()
        response.close()
        return content
    except HTTPError, e:
        print e.fp.read()
        errorNotice = 'XBMC.Notification("Feed page not found","Error code: ' + str(e.code) + '", 3000)'
        xbmc.executebuiltin( errorNotice )
        return False
    except URLError, e:
        errorNotice = 'XBMC.Notification("Cannot connect to server","Error reason: %s", 3000)' % e.reason
        print "Cannot connect to server. Error reason: %s" % e.reason
        xbmc.executebuiltin( errorNotice )
        return False



def addLink( name, url, thumbnail="default.png", plot_text="None", size=0 ):
        infoLabels = { "Title": name }

        item = xbmcgui.ListItem( name, iconImage="DefaultVideo.png", thumbnailImage=thumbnail )
        
        contextMenuItems = [
                             ('Add to queue', 'XBMC.RunPlugin(%s?queueMe&url=%s)' % (sys.argv[0], url)),
                             ('Download', 'XBMC.RunPlugin(%s?mode=9&url=%s)' % (sys.argv[0], url))
                           ]
        #item.addContextMenuItems( contextMenuItems, replaceItems=True )

        if size:
            infoLabels['Size'] = size
        
        item.setInfo( type="Video", infoLabels=infoLabels )
        ok = xbmcplugin.addDirectoryItem( handle=int( sys.argv[1] ), url=url, listitem=item )
        return ok

def addDir( name, url, mode, thumbnail="default.png", plot_text=None, feed_item=None, imdb_id=None ):
        infoLabels = { "Title": name }

        if imdb_id:
            infoLabels['Overlay'] = 1

        u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)
        if plot_text and re.search('hotfile.com/dl/', plot_text, re.IGNORECASE):
            item = xbmcgui.ListItem('[COLOR=FFFFFFFF]%s[/COLOR]' % name, iconImage="DefaultFolder.png", thumbnailImage=thumbnail)
        else:
            item = xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=thumbnail)

        contextMenuItems = [
                              #('Add to Queue', 'XBMC.Action(Queue)'),
                              ('Mark Feed Read', 'XBMC.RunPlugin(%s?mode=5&url=%s)' % (sys.argv[0], urllib.quote_plus(url))),
                           ]
        if feed_item:
            contextMenuItems.append( ('View Feed Item', 'XBMC.RunPlugin(%s?mode=7&url=%s)' % (sys.argv[0], urllib.quote_plus(feed_item.id))) )
            if feed_item.author:
                infoLabels["Writer"] = feed_item.author
            if feed_item.data['published']:
                infoLabels["Date"] = datetime.fromtimestamp( int( feed_item.data['published'] ) ).strftime( '%d.%m.%Y' )
        item.addContextMenuItems( contextMenuItems, replaceItems=False )

        if plot_text:
            plot_text = html2text.html2text(plot_text.decode('utf-8'))
	    #infoLabels["Trailer"] = "plugin://plugin.video.youtube/?action=play_video&videoid=aVdO-cx-McA"
            infoLabels["Plot"] = plot_text.encode( "utf-8" )

        item.setInfo( type="Video", infoLabels=infoLabels )
        """
        fanarts = ['http://cf1.themoviedb.org/backdrops/9f6/4bc95844017a3c57fe0279f6/avatar-original.jpg',
                    'http://cf1.themoviedb.org/backdrops/348/4bd9dcff017a3c1bfb000348/avatar-original.jpg',
                    'http://cf1.themoviedb.org/backdrops/a2a/4bc9584f017a3c57fe027a2a/avatar-original.jpg',
                    'http://cf1.themoviedb.org/backdrops/a16/4bc9584c017a3c57fe027a16/avatar-original.jpg']
        from random import choice
        item.setProperty('fanart_image', choice(fanarts))
        """
        ok = xbmcplugin.addDirectoryItem( handle=int(sys.argv[1]), url=u, listitem=item, isFolder=True )
        return ok

# dedupe list of links and keep original order they were found in.
def dedupeList( itemList, mainIndex ):
    print "dedupeList deduping start count: %d" % len(itemList)
    knownItems = set()
    newList = []
    for listItem in itemList:
        item = listItem[mainIndex]
        if item in knownItems: continue
        newList.append(listItem)
        knownItems.add(item)
    #link_matches[:] = newlist
    print "dedupeList deduping end count: %d" % len(newList)
    return newList


def get_params():
        param=[]
        paramstring=sys.argv[2]
        if len(paramstring)>=2:
                params=sys.argv[2]
                cleanedparams=params.replace('?','')
                if (params[len(params)-1]=='/'):
                        params=params[0:len(params)-2]
                pairsofparams=cleanedparams.split('&')
                param={}
                for i in range(len(pairsofparams)):
                        splitparams={}
                        splitparams=pairsofparams[i].split('=')
                        if (len(splitparams))==2:
                                param[splitparams[0]]=splitparams[1]
                                
        return param

def get_keyboard( default="", heading="", hidden=False ):
        """ shows a keyboard and returns a value """
        keyboard = xbmc.Keyboard( default, heading, hidden )
        keyboard.doModal()
        if ( keyboard.isConfirmed() ):
               return unicode( keyboard.getText(), "utf-8" )
        return default

def doLog( logText ):
    if DEBUG:
        print "%s: %s" % ( inspect.stack()[1][3], logText )
        
def removeCachedReaderFiles():
    os.remove(CACHED_CA_FILE)
    os.remove(CACHED_READER_FILE)

########################################
print "START"
succeeded = True
updateListing = False

myhandle = int(sys.argv[1])
ADDON_ID = 'plugin.video.greader.ddl.video'
DATA_DIR = "special://profile/addon_data/" + ADDON_ID
CACHED_CA_FILE = DATA_DIR + '/ca.xbmc'
CACHED_READER_FILE = DATA_DIR + '/reader.xbmc'

__settings__ = xbmcaddon.Addon(id=ADDON_ID)
__language__ = __settings__.getLocalizedString

BASE_RESOURCE_PATH = xbmc.translatePath( os.path.join( os.getcwd(), 'resources') )
sys.path.append (BASE_RESOURCE_PATH)

greader_user = __settings__.getSetting('greader_user')
greader_pass = __settings__.getSetting('greader_pass')
hotfile_user = __settings__.getSetting('hotfile_user')
hotfile_pass = __settings__.getSetting('hotfile_pass')
USE_REDIRECT_SERVER = __settings__.getSetting('use_redirect_server')
REDIRECT_SERVER_URL = 'http://127.0.0.1:' + __settings__.getSetting('redirect_server_port')

#########################
# move this is a method!
if not os.path.isfile(CACHED_CA_FILE) or not os.path.isfile(CACHED_READER_FILE):
    topickle = True
elif ((time.time() - os.path.getmtime(CACHED_CA_FILE))/60) > 10:
    # older than 10 mins so refresh
    topickle = True
else:
    topickle = False

if topickle:
    ca = ClientAuth( greader_user, greader_pass )
    reader = GoogleReader( ca )
    reader.buildSubscriptionList()
    pickle.dump(ca, open(CACHED_CA_FILE,'wb'), -1)
    pickle.dump(reader, open(CACHED_READER_FILE,'wb'), -1)
else:
    ca = pickle.load(open(CACHED_CA_FILE))
    reader = pickle.load(open(CACHED_READER_FILE))
#########################

params=get_params()
url=None
id=None
name=None
mode=None
try:
    url=urllib.unquote_plus(params["url"])
except:
    pass
try:
    name=urllib.unquote_plus(params["name"])
except:
    pass
try:
    mode=int(params["mode"])
except:
    pass
print '==========================PARAMS:\nURL: %s\nNAME: %s\nID: %s\nMODE: %s\nMYHANDLE: %s\nPARAMS: %s' % ( url, name, id, mode, myhandle, params )

if mode==None or url==None or len(url)<1:
    showBaseIndex()
elif mode==2:
    showIndex( url )
elif mode==3:
    showFeedItems( url )
elif mode==4:
    if not showFeedItemLinks( url ):
        succeeded=False
elif mode==44:
    if not showRarVideos( url ):
        succeeded=False
elif mode==5:
    markFeedRead( url )
    removeCachedReaderFiles()
    xbmc.executebuiltin("Container.Refresh")
    updateListing = True
elif mode==6:
    doSearch( url )
elif mode==7:
    viewFeedItem( url )
elif mode==9:
    parsedurl = urlparse(url)
    filename = "/tmp/" + parsedurl[2].split("/")[-1]
    print "FILENAME: " + filename
    DownloaderClass(url,xbmc.translatePath(filename))
elif mode==99:
    playlistTest3( url )
elif mode==999:
    rarPlaylistTest( url )
elif mode==100:
    testGetCategoryContents( url )
else:
    print "NO MODE SET! mode=" + str(mode)


xbmcplugin.endOfDirectory( myhandle, succeeded=succeeded, updateListing=updateListing )


