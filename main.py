import urllib
import os
import datetime
# from django.utils import simplejson
# from google.appengine.api import channel
# from google.appengine.api import users
# from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from gaesessions import get_current_session
from aeoid import middleware
from aeoid import users
#from diff_match_patch import diff_match_patch, patch_obj


class dbStore(db.Model):
  date = db.DateTimeProperty(auto_now_add=True)
  fileID = db.TextProperty()
  data = db.TextProperty()

class MainPage(webapp.RequestHandler):
    def get(self):
        session = get_current_session()
        session['fileID'] = urllib.unquote(self.request.get('fileID'))
        if not session['fileID']:
            session['fileID'] = "changeThis.txt"
        #user:
        session['user'] = str(users.get_current_user())
        if self.request.get('auth') != 'true':
            session['user'] = str(datetime.datetime.now())
        else:
            if not users.get_current_user():
                self.redirect(users.create_login_url(self.request.uri))

        
        session['data'] = "Please wait while the app loads..."

        template_values = {'user': session['user'],
                           'fileID': session['fileID'],
                           'data' : session['data']}
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))


application = webapp.WSGIApplication([
    ('/', MainPage)], debug=False)
application = middleware.AeoidMiddleware(application)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
