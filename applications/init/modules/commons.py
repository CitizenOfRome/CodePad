'''commons.py:
    Contains a set of modules that are to be used by various parts of the app
'''
from google.appengine.api import users
import simplejson as json
import hashlib

DEFAULT_EXTENSIONS = json.dumps([])
MAX_MEMORY = 100000000

SALT = "CodePad"
def get_hash(string):
    '''Gives the HEX digest for the given string'''
    return hashlib.sha256(string+SALT).hexdigest()
    
class Clients():
    '''Contains methods to manage users'''
    user = None #Unique User ID
    uid = None #bash of user
    client = None #Holds the current user's record
    def __init__(self):
        if not session.uid: self.login()
    def login(self):
        '''Method to login'''
        self.user = users.get_current_user()
        if not self.user:
            '''Create a temporary User if not logged in'''
            redirect(users.create_login_url(request.url))
            pass
        else:
            self.user = self.user.user_id()
            self.nickname = users.get_current_user().nickname
            self.uid = get_hash(self.user)
        self.client = db(db.users.uid==self.uid).select().first()
        if not self.client:    return self.new_user()
        elif self.client.slinked != "":  self.client = db(db.users.uid==self.client.slinked).select().first()
        return  self.client.update_record(active = True, last_in = request.now)
    def logout(self):
        '''Method to logout'''
        return  self.client.update_record(active = False)
    def new_user(self):
        '''Creates a new user (Must call after checking if client exists [see:login()])'''
        if not self.uid: return False
        global DEFAULT_EXTENSIONS
        users_id = db.users.insert(
                name = self.nickname,
                uid = self.uid,
                active = True,
                extensions = DEFAULT_EXTENSIONS,
                last_in = request.now
            )
        Projects().new_project("") # Register default project
        FileSystem().new_file("", "", "", self.uid, "live", True) # Create the user directory
        self.client = db.users[users_id]
        return True
    def get_user(self, uid):
        '''Returns the record associated with the given uid'''
        return db(db.users.uid==uid).select().first()
    def get_users_by_name(self, name):
        '''Returns the record associated with the given uid'''
        return db(db.users.name==name).select()

class FileSystem():
    '''Contains methods that help manipulate the fileSystem.'''
    def get_file(self, bash):
        '''Returns the record associated with the given bash'''
        return db(db.files.bash==bash).select().first()
    def get_file_list(self, bash):
        '''Returns the record's of the files with the given bash as home folder'''
        return db(db.files.home==bash).select()
    def new_file(self, home, project, path, name, version="live", is_dir=False, text=""):
        '''Creates a new file'''
        bash = get_hash(path+"/"+name+":"+version)
        self.file = db(db.files.bash==bash).select().first()
        if not self.file:
            file_id = db.files.insert(
                name = name,
                path = path,
                bash = bash,
                home = home,
                project = project,
                is_dir = is_dir,
                version = version,
                text = text,
                size = len(text)
            )
            self.file = db.files[file_id]
        return self.file
        pass

class Projects():
    '''Contains methods that make handling Projects easier'''
    project = None
    def new_project(self, name):
        '''Gets/Creates a new project with the given name'''
        if not session.uid: session.uid = Clients().uid
        self.project = db((db.projects.name==name) & (db.projects.creator==session.uid)).select().first()
        if not self.project:
            bash = get_hash(session.uid+"/"+name)
            project_id = db.projects.insert(name=name, creator=session.uid, bash=bash)
            self.project = db.projects[project_id]
            FileSystem().new_file(session.uid, bash, "/"+session.uid, name, "live", True)
        return self.project
    def get_project(bash):
        return db(db.projects.bash==bash).select().first()