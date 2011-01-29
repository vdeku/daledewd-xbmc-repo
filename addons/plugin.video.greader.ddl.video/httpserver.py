import re
import BaseHTTPServer
import SocketServer
import md5
import urllib
import traceback
import xbmc
import xbmcaddon


#USE_REDIRECT_SERVER = True
#PORT_NUMBER = 5150
__settings__ = xbmcaddon.Addon(id='plugin.video.greader.ddl.video')
USE_REDIRECT_SERVER = __settings__.getSetting('use_redirect_server')
PORT_NUMBER = int(__settings__.getSetting('redirect_server_port'))
HOST_NAME = '127.0.0.1'
REDIRECTIONS = {}

class RedirectHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(self):
        path = urllib.unquote_plus(self.path)
        print "HTTPSERVER PATH: %s" % path
        try:
            for redirect_path in REDIRECTIONS:
                if redirect_path in path:
                    path_extra = re.split(redirect_path, path)[1]
                    print "REDIRECT SERVER: Redirecting:\nFROM:%s\nTO:%s" % (redirect_path+path_extra,REDIRECTIONS.get(redirect_path)+path_extra)
                    self.send_response(302)
                    self.send_header("Location", REDIRECTIONS.get(redirect_path)+path_extra)
                    self.end_headers()
                    return
            self.send_error(404)
        except:
            #traceback.print_exc()
            pass

        return

    def do_GET(self):
        self.do_HEAD()
        return

    def do_POST(self):
        path = urllib.unquote_plus(self.path)
        print "=========================================\n"
        print "HTTPSERVER PATH: %s" % path
        length = int(self.headers.getheader('content-length'))
        urls = self.rfile.read(length).split("\n")
        urls_md5 = md5.new("\n".join(urls)).hexdigest()

        new_urls = []
        for url in urls:
            new_path = "/%s/%s" % (urls_md5, url.split("/")[-1])
            new_url = "http://%s:%d%s" % (HOST_NAME, PORT_NUMBER, new_path)
            new_urls.append(new_url)
            REDIRECTIONS[new_path] = url

        self.wfile.write("\n".join(new_urls))

        print "URLS: %s" % "\n\t".join(urls)
        print "NEW_URLS: %s" % "\n\t".join(new_urls)
        print urls_md5

        #print "REDIRECTIONS:"
        #for orig,redir in REDIRECTIONS.items():
        #    print "  %s\n    %s" % (orig,redir)

        print "\n\n"

class ThreadingHTTPServer (SocketServer.ThreadingMixIn,
                           BaseHTTPServer.HTTPServer): pass

if __name__ == '__main__':
    if USE_REDIRECT_SERVER:
        server_class = ThreadingHTTPServer
        httpd = server_class((HOST_NAME, PORT_NUMBER), RedirectHandler)
        print "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER)
        httpd.serve_forever()

