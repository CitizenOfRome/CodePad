# -*- coding: utf-8 -*-

#########################################################################
## This scaffolding model makes your app work on Google App Engine too
## File is released under public domain and you can use without limitations
#########################################################################

if not request.env.web2py_runtime_gae:     
    ## if NOT running on Google App Engine use SQLite or other DB
    db = DAL('sqlite://storage.sqlite') 
else:
    ## connect to Google BigTable (optional 'google:datastore://namespace')
    db = DAL('google:datastore') 
    ## store sessions and tickets there
    session.connect(request, response, db = db) 
    ## or store session in Memcache, Redis, etc.
    ## from gluon.contrib.memdb import MEMDB
    ## from google.appengine.api.memcache import Client
    ## session.connect(request, response, db = MEMDB(Client()))

## by default give a view/generic.extension to all actions from localhost
## none otherwise. a pattern can be 'controller/function.extension'
response.generic_patterns = ['*'] if request.is_local else []

#########################################################################
## Here is sample code if you need for
## - email capabilities
## - authentication (registration, login, logout, ... )
## - authorization (role based authorization)
## - services (xml, csv, json, xmlrpc, jsonrpc, amf, rss)
## - old style crud actions
## (more options discussed in gluon/tools.py)
#########################################################################

from gluon.tools import Auth, Crud, Service, PluginManager, prettydate
auth = Auth(db, hmac_key=Auth.get_or_create_key()) 
crud, service, plugins = Crud(db), Service(), PluginManager()

## create all tables needed by auth if not custom tables
auth.define_tables() 

## configure email
mail=auth.settings.mailer
mail.settings.server = 'logging' or 'smtp.gmail.com:587'
mail.settings.sender = 'you@gmail.com'
mail.settings.login = 'username:password'

## configure auth policy
auth.settings.registration_requires_verification = False
auth.settings.registration_requires_approval = False
auth.settings.reset_password_requires_verification = True

## if you need to use OpenID, Facebook, MySpace, Twitter, Linkedin, etc.
## register with janrain.com, write your domain:api_key in private/janrain.key
from gluon.contrib.login_methods.rpx_account import use_janrain
use_janrain(auth,filename='private/janrain.key')

#########################################################################
## Define your tables below (or better in another model file) for example
##
## >>> db.define_table('mytable',Field('myfield','string'))
##
## Fields can be 'text','string','password','integer','double','boolean'
##       'date','time','datetime','blob','upload', 'reference TABLENAME'
## There is an implicit 'id integer autoincrement' field
## Consult manual for more options, validators, etc.
##
## More API examples for controllers:
##
## >>> db.mytable.insert(myfield='value')
## >>> rows=db(db.mytable.myfield=='value').select(db.mytable.ALL)
## >>> for row in rows: print row.id, row.myfield#/<application>/<controller>/<action>
#########################################################################ctrl(ctrl)+view(action=ctrl_func.html)+model
import simplejson as json

db.define_table('users', 
                    db.Field('name', 'string'),
                    db.Field('password', 'password'),#If local user
                    db.Field('active', 'boolean', default=False),
                    db.Field('uid', 'string'),
                    db.Field('slinked', 'string', default=""),#Redirect to a linked account
                    db.Field('extensions', 'string', default=""),#Extensions to load on login
                    db.Field('extensions_bak', 'string', default=""),#Extensions to load if logout failed
                    db.Field('reputation', 'integer', default=0),
                    db.Field('memory', 'integer', default=0), #Total size of the data owned by user
                    db.Field('last_in', 'datetime', default=request.now),
                    db.Field('date', 'datetime', default=request.now, writable=False)
                )

db.define_table('files', 
                    db.Field('name', 'string'),
                    db.Field('path', 'text'),
                    db.Field('version', 'string', default="live"),
                    db.Field('slinked', 'string', default=""),#Hash of slinked file, if slinked
                    db.Field('bash', 'string', unique=True),#/userName/pathToFile/FileName:Version
                    db.Field('home', 'string'),#Hash of directory where this file resides
                    db.Field('project', 'string'),#Hash of project where this file resides
                    db.Field('is_dir', 'boolean', default=False),
                    db.Field('size', 'integer', default=0), #Size in bytes
                    db.Field('text', 'text', default=""),#Holds file data
                    db.Field('meta', 'text', default=json.dumps({'date':str(request.now)})),
                    db.Field('contributors', 'text', default=json.dumps([])),
                    db.Field('active', 'text', default=json.dumps([]))
                )
# db.files.name.requires = IS_NOT_EMPTY()
# db.files.path.requires = IS_NOT_EMPTY()

db.define_table('projects', 
                    db.Field('name', 'string'),
                    db.Field('creator', 'string'),
                    db.Field('bash', 'string', unique=True),#Hash(UserId/Name)
                    db.Field('versions', 'text', default=json.dumps(["live"])),
                    db.Field('meta', 'text', default=json.dumps( { 'date':str(request.now) } )),
                    db.Field('admins', 'text', default=json.dumps([])),
                    db.Field('contributors', 'text', default=json.dumps([])),
                    db.Field('banned', 'text', default=json.dumps([]))
                )

db.define_table('viewobj', #ViewObj, used by MobWrite
                    db.Field('username', 'string'),
                    db.Field('filename', 'string'),
                    db.Field('shadow', 'text', default=""),
                    db.Field('backup_shadow', 'text', default=""),
                    db.Field('edit_stack', 'text', default=json.dumps([])),
                    db.Field('textobj', db.files),
                    db.Field('changed', 'boolean', default=False),
                    db.Field('delta_ok', 'boolean', default=True),
                    db.Field('shadow_client_version', 'integer', default=0),
                    db.Field('shadow_server_version', 'integer', default=0),
                    db.Field('shadow_server_version', 'integer', default=0),
                    db.Field('backup_shadow_server_version', 'integer', default=0),
                    db.Field('lasttime', 'datetime', default=request.now)
                )
