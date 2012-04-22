# -*- coding: utf-8 -*-

from gluon.contrib.login_methods.cas_auth import CasAuth
from gluon.storage import Storage
from gluon.sql import SQLField
from gluon.http import HTTP, redirect
import openid.consumer.consumer
from openid.association import Association
from openid.store.interface import OpenIDStore
from openid.extensions.sreg import SRegRequest, SRegResponse
from openid.store import nonce
import gluon.tools
import time


class OpenIDLogin(CasAuth):
    """
    OpenIDLogin
    
    This class implements the CasAuth interface and allows one
    to substitute the standard logon/register procedure using
    OpenID.
    
    Example:
    
        #include in your model after auth has been defined
        from <appname>.modules.w2popenid import OpenIDLogin
        auth.settings.login_form = OpenIDLogin(consumer_url, environment)
        
        # consumer_url is the URL of the consumer server in the form of
        # URL(r=request, c='...', f='...') (see w2popenid.Consumer)
        # and environment equals globals()
    """                                        

    def __init__(self, consumer_url, environment):
       self.consumer_url = consumer_url
       self.environment = Storage(environment)
       
    def login_url(self, next='/'):       
        if not self.environment.session.has_key('w2popenid'):
            self.environment.session.w2popenid = Storage()
        self.environment.session.w2popenid.login_next = next
        return self.consumer_url + '/login'
       
    def logout_url(self, next='/'):
        del(self.environment.session.w2popenid)
        return next
       
    def get_user(self):
        if self.environment.session.w2popenid:
           return self.environment.session.w2popenid.user_data
        else:
           return None


class OpenIDAuth(gluon.tools.Auth):
    pass

class Consumer(object):
    """
    OpenID consumer (relaying party)
     
    
    """
    
    def __init__(self, environment, db):
       self.environment = Storage(environment)
       self.store = Web2pyStore(db)
       self.consumer = openid.consumer.consumer.Consumer(self.environment.session,
                                                         self.store)
       request = self.environment.request                                                 
       self.realm = 'http://%s' % request.env.http_host
       self.return_to_url = self.realm + self.environment.URL(r=request, args=['oidresponse'])
      
    def __call__(self):
        request = self.environment.request
        args = request.args
        if not args:
            redirect(self.environment.URL(r=request, args=['login']))
        if args[0] == 'login':
            return self.login()
        elif args[0] == 'oidresponse':
            self.process_response()
        else:
            raise HTTP(404)
           
    def login(self):
        request = self.environment.request
        session = self.environment.session
        form = self.environment.FORM("openID: ",
                                     self.environment.INPUT(_type="input", _name="oid"),
                                     self.environment.INPUT(_type="submit"))
        if form.accepts(request.vars, session):
            auth_req = self.consumer.begin(request.vars.oid)
            auth_req.addExtension(SRegRequest(required=['email','nickname']))
            url = auth_req.redirectURL(return_to=self.return_to_url, realm=self.realm)
            print url
            redirect(url)
        return form
   
      
    def process_response(self):
        resp = self.consumer.complete(self.environment.request.vars, self.return_to_url)
        if resp.status == openid.consumer.consumer.SUCCESS:
            sreg_resp = SRegResponse.fromSuccessResponse(resp)
            print sreg_resp.data
            self.environment.session.w2popenid.user_data = sreg_resp.data
            flash = 'OpenID authentication successfull.'
        if resp.status == openid.consumer.consumer.FAILURE:
            flash = 'OpenID authentication failed. (Error message: %s)' % resp.message
        if resp.status == openid.consumer.consumer.CANCEL:
            flash = 'OpenID authentication canceled by user.'
        if resp.status == openid.consumer.consumer.SETUP_NEEDED:
            flash = 'OpenID authentication needs to be setup by the user with the provider first.'
        self.environment.session.flash = flash
        redirect(self.environment.session.w2popenid.login_next)
                 
       
       
class Web2pyStore(OpenIDStore):
    """ 
    Web2pyStore
    
    This class implements the OpenIDStore interface. OpenID stores take care
    of persisting nonces and associations. The Janrain Python OpenID library
    comes with implementations for file and memory storage. Web2pyStore uses
    the web2py db abstration layer. See the source code docs of OpenIDStore
    for a comprehensive description of this interface.
    
    """
   
    def __init__(self, database):
        self.database = database
        self._initDB()
        
    def _initDB(self):
        print 'init db', 'x'*100
        self.database.define_table('oid_associations', 
                        SQLField('server_url', 'string', length=2047, required=True),
                        SQLField('handle', 'string', length=255, required=True),
                        SQLField('secret', 'blob', required=True),
                        SQLField('issued', 'integer', required=True),
                        SQLField('lifetime', 'integer', required=True),
                        SQLField('assoc_type', 'string', length=64, required=True)
                       )
        self.database.define_table('oid_nonces', 
                        SQLField('server_url', 'string', length=2047, required=True),
                        SQLField('timestamp', 'integer', required=True),
                        SQLField('salt', 'string', length=40, required=True)
                       )

    def storeAssociation(self, server_url, association):
        """ 
        Store associations. If there already is one with the same
        server_url and handle in the table replace it.
        """
        
        db = self.database
        query = (db.oid_associations.server_url == server_url) & (db.oid_associations.handle == association.handle)
        db(query).delete()
        db.oid_associations.insert(server_url = server_url,
                                   handle = association.handle,
                                   secret = association.secret,
                                   issued = association.issued,
                                   lifetime = association.lifetime,
                                   assoc_type = association.assoc_type), 'insert '*10
              
    def getAssociation(self, server_url, handle=None):
        """ 
        Return the association for server_url and handle. If handle is
        not None return the latests associations for that server_url.
        Return None if no association can be found.
        """
           
        db = self.database
        query = (db.oid_associations.server_url == server_url)
        if handle:
            query &= (db.oid_associations.handle == handle)
        rows = db(query).select(orderby=db.oid_associations.issued)
        keep_assoc, _ = self._removeExpiredAssocations(rows)
        if len(keep_assoc) == 0:
            return None
        else:
            assoc = keep_assoc.pop() # pop the last one as it should be the latest one
            return Association(assoc['handle'],
                               assoc['secret'],
                               assoc['issued'],
                               assoc['lifetime'],
                               assoc['assoc_type'])
        
    def removeAssociation(self, server_url, handle):
        db = self.database
        query = (db.oid_associations.server_url == server_url) & (db.oid_associations.handle == handle)
        return db(query).delete() != None
        
    def useNonce(self, server_url, timestamp, salt):
        """ 
        This method returns Falase if a nonce has been used before or its
        timestamp is not current.
        """
        
        db = self.database
        if abs(timestamp - time.time()) > nonce.SKEW:
            return False
        query = (db.oid_nonces.server_url == server_url) & (db.oid_nonces.timestamp == timestamp) & (db.oid_nonces.salt == salt)
        if db(query).count() > 0:
            return False
        else:
           db.oid_nonces.insert(server_url = server_url,
                                timestamp = timestamp,
                                salt = salt)
           return True
   
    def _removeExpiredAssocations(self, rows):
        """ 
        This helper function is not part of the interface. Given a list of
        association rows it checks which associations have expired and 
        deletes them from the db. It returns a tuple of the form 
        ([valid_assoc], no_of_expired_assoc_deleted).
        """
           
        db = self.database
        keep_assoc = []
        remove_assoc = []
        t1970 = time.time()
        for r in rows:
            if r['issued'] + r['lifetime'] < t1970:
                remove_assoc.append(r)
            else:
                keep_assoc.append(r)
        for r in remove_assoc:
            del db.oid_associations[r['id']]
        return (keep_assoc, len(remove_assoc)) # return tuple (list of valid associations, number of deleted associations)
          
    def cleanupNonces(self):
        """ 
        Remove expired nonce entries from DB and return the number
        of entries deleted. 
        """
           
        db = self.database
        query = (db.oid_nonces.timestamp < time.time() - nonce.SKEW)
        return db(query).delete()
        
    def cleanupAssociations(self):
        """ 
        Remove expired associations from db and return the number
        of entries deleted.
        """
           
        db = self.database
        query = (db.oid_associations.id > 0)
        return self._removeExpiredAssocations(db(query).select())[1] #return number of assoc removed
        
    def cleanup(self):
        """ 
        This method should be run periodically to free the db from
        expired nonce and association entries.
        """
        
        return self.cleanupNonces(), self.cleanupAssociations()
