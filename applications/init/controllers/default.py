import sys
path = '../modules/'
if not path in sys.path: sys.path.append(path)
import urllib
import os
import datetime
import simplejson as json

import commons
commons.db = db
commons.redirect = redirect
commons.request = request
commons.session = session


if not session.uid: session.uid = commons.Clients().uid

def index():
    '''The HostStation'''
    if len(request.args) > 0:
        base = request.args[0]
        if not commons.Clients().get_user(base):
            names = commons.Clients().get_users_by_name(base)
            if len(names) > 0:
                request.args[0] = names.first().uid
    path = ""
    for var in request.args:
        path += "/"+var
    path = urllib.unquote(path)
    bash = commons.get_hash(path+":live")
    if path == "":  bash = commons.get_hash("/"+session.uid+":live")
    file = commons.FileSystem().get_file(bash)
    if file is None:    raise HTTP(404)
    elif file.is_dir:   return project(file)
    elif "raw" in request.vars:    return code(file)
    else:   return editor(file)

def project(file):
    '''Loads a directory'''
    if file is None or not file.is_dir: raise HTTP(404)
    files=commons.FileSystem().get_file_list(file.bash)
    return response.render('default/project.html', locals())
def new():
    '''Creates a new file/folder'''
    home = request.vars["home"]
    name = request.vars["name"]
    if request.vars.has_key("is_dir") and request.vars["is_dir"] == "1":    is_dir = True
    else:   is_dir = False
    dir = commons.FileSystem().get_file(home)
    if not dir: raise HTTP(404)
    commons.FileSystem().new_file(home=home,
        project=dir.project,
        path=dir.path+"/"+dir.name,
        name=name,
        version=dir.version,
        is_dir=is_dir)
    redirect("/init/default/index"+dir.path+"/"+dir.name)
    return project(dir)
def slink():
    '''Creates a Soft-Link'''
    source = request.vars["source"]
    home = request.vars["home"]
    dir = commons.FileSystem().get_file(home)
    if not dir: raise HTTP(404)
    commons.FileSystem().new_file(home=home,
        project=dir.project,
        path=dir.path+"/"+dir.name,
        version=dir.version,
        slinked = source)
    redirect("/init/default/index"+dir.path+"/"+dir.name)
    return project(dir)

def editor(file):
    '''Load the editor.'''
    if file is None or file.is_dir: raise HTTP(404)
    return response.render('default/editor.html', locals())

def code(file):
    '''Get teh code.'''
    if file is None or file.is_dir: raise HTTP(404)
    return file.text

def upload_handler():
    '''Handles file upload'''
    files = request.vars["files[]"]
    home = request.vars["home"]
    dir = commons.FileSystem().get_file(home)
    if not dir: raise HTTP(404)
    if not type(files) is list:  files = [files]
    for file in files:
        commons.FileSystem().new_file(home=home,
            project=dir.project,
            path=dir.path+"/"+dir.name,
            name=file.filename,
            version=dir.version,
            is_dir=False,
            text=file.file.read())
    redirect("/init/default/index"+dir.path+"/"+dir.name)
    return project(dir)
