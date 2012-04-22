#!/usr/bin/python2.7

"""MobWrite - Real-time Synchronization and Collaboration Service

Copyright 2008 Google Inc.
http://code.google.com/p/google-mobwrite/

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""This file is the server, running under Google App Engine.

Accepting synchronization sessions from clients.
"""

__author__ = "fraser@google.com (Neil Fraser)"
__modified_by__ = "Sathvik Ponangi"

import cgi
import simplejson as json
import datetime
import os
import sys
import urllib

# from google.appengine.ext import db as dib
# from google.appengine import runtime
# from google.appengine.api import memcache

from aeoid import middleware
from aeoid import users

import logging
import re
import diff_match_patch as dmp_module

def toTime(value):
      (quantity, unit) = value.split(None, 1)
      quantity = int(quantity)
      if (unit == "seconds"):
        delta = datetime.timedelta(seconds=quantity)
      elif (unit == "minutes"):
        delta = datetime.timedelta(minutes=quantity)
      elif (unit == "hours"):
        delta = datetime.timedelta(hours=quantity)
      elif (unit == "days"):
        delta = datetime.timedelta(days=quantity)
      else:
        raise "Config: Unknown time value."
      return delta

# Global Diff/Match/Patch object.
DMP = dmp_module.diff_match_patch()
# Global logging object.
LOG = logging.getLogger("mobwrite")
DMP.Diff_Timeout = 0.1
MAX_CHARS = 100000
TIMEOUT_VIEW = toTime("30 minutes")
TIMEOUT_TEXT = toTime("1 days")
TIMEOUT_BUFFER = toTime("15 minutes")
TRANSACT = False

def fetchText(name):
  textobj = db(db.files.bash==name).select().first()
  # textobj = None
  # if textobjs:
      # for row in textobjs:
        # if row.bash == name:
            # textobj = row
  if not textobj:
    textobj_id = db.files.insert(bash=name, name=name, path=name, text="")
    textobj = db.files[textobj_id]
  # if textobj.text is None:
    #LOG.info("Loaded null TextObj: '%s'" % name)
  # else:
    #LOG.info("Loaded %db TextObj: '%s'" % (len(textobj.text), name))
  return textobj

class MobWrite2Py():

  def parseRequest(self, data):
    """Parse the raw MobWrite commands into a list of specific actions.
    See: http://code.google.com/p/google-mobwrite/wiki/Protocol

    Args:
      data: A multi-line string of MobWrite commands.

    Returns:
      A list of actions, each action is a dictionary.  Typical action:
      {"username":"fred",
       "filename":"report",
       "mode":"delta",
       "data":"=10+Hello-7=2",
       "force":False,
       "server_version":3,
       "client_version":3,
       "echo_username":False
      }
    """
    # Passing a Unicode string is an easy way to cause numerous subtle bugs.
    if type(data) != str:
     # #LOG.critical("parseRequest data type is %s" % type(data))
      return []
    if not (data.endswith("\n\n") or data.endswith("\r\r") or
            data.endswith("\n\r\n\r") or data.endswith("\r\n\r\n")):
      # There must be a linefeed followed by a blank line.
      # Truncated data.  Abort.
     # #LOG.warning("Truncated data: '%s'" % data)
      return []

    # Parse the lines
    actions = []
    username = None
    filename = None
    server_version = None
    echo_username = False
    for line in data.splitlines():
      if not line:
        # Terminate on blank line.
        break
      if line.find(":") != 1:
        # Invalid line.
        continue
      (name, value) = (line[:1], line[2:])

      # Parse out a version number for file, delta or raw.
      version = None
      if ("FfDdRr".find(name) != -1):
        div = value.find(":")
        if div > 0:
          try:
            version = int(value[:div])
          except ValueError:
           # #LOG.warning("Invalid version number: %s" % line)
            continue
          value = value[div + 1:]
        else:
         # #LOG.warning("Missing version number: %s" % line)
          continue

      if name == "b" or name == "B":
        # Decode and store this entry into a buffer.
        try:
          (name, size, index, text) = value.split(" ", 3)
          size = int(size)
          index = int(index)
        except ValueError:
         # #LOG.warning("Invalid buffer format: %s" % value)
          continue
        # Store this buffer fragment.
        text = self.feedBuffer(name, size, index, text)
        # Check to see if the buffer is complete.  If so, execute it.
        if text:
         # #LOG.info("Executing buffer: %s_%d" % (name, size))
          # Duplicate last character.  Should be a line break.
          # Note that buffers are not intended to be mixed with other commands.
          return self.parseRequest(text + text[-1])

      elif name == "u" or name == "U":
        # Remember the username.
        username = value
        # Client may request explicit usernames in response.
        echo_username = (name == "U")

      elif name == "f" or name == "F":
        # Remember the filename and version.
        filename = value
        server_version = version

      elif name == "n" or name == "N":
        # Nullify this file.
        filename = value
        if username and filename:
          action = {}
          action["username"] = username
          action["filename"] = filename
          action["mode"] = "null"
          actions.append(action)

      else:
        # A delta or raw action.
        action = {}
        if name == "d" or name == "D":
          action["mode"] = "delta"
        elif name == "r" or name == "R":
          action["mode"] = "raw"
        else:
          action["mode"] = None
        if name.isupper():
          action["force"] = True
        else:
          action["force"] = False
        action["server_version"] = server_version
        action["client_version"] = version
        action["data"] = value
        action["echo_username"] = echo_username
        if username and filename and action["mode"]:
          action["username"] = username
          action["filename"] = filename
          actions.append(action)

    return actions

  def feedBuffer(self, name, size, index, datum):
    """Add one block of text to the buffer and return the whole text if the
      buffer is complete.

    Args:
      name: Unique name of buffer object.
      size: Total number of slots in the buffer.
      index: Which slot to insert this text (note that index is 1-based)
      datum: The text to insert.

    Returns:
      String with all the text blocks merged in the correct order.  Or if the
      buffer is not yet complete returns the empty string.
    """
    text = ""
    if not 0 < index <= size:
      pass
      #LOG.error("Invalid buffer: '%s %d %d'" % (name, size, index))
    elif size == 1 and index == 1:
      # A buffer with one slot?  Pointless.
      text = datum
      #LOG.info("Buffer with only one slot: '%s'" % name)
    else:
      timeout = TIMEOUT_BUFFER.seconds
      mc = memcache.Client()
      namespace = "%s_%d" % (name, size)
      # Save this buffer to memcache.
      if mc.add(str(index), datum, time=timeout, namespace=namespace):
        # Add a counter or increment it if it already exists.
        counter = 1
        if not mc.add("counter", counter, time=timeout, namespace=namespace):
          counter = mc.incr("counter", namespace=namespace)
        if counter == size:
          # The buffer is complete.  Extract the data.
          keys = []
          for index in xrange(1, size + 1):
            keys.append(str(index))
          data_map = mc.get_multi(keys, namespace=namespace)
          data_array = []
          for index in xrange(1, size + 1):
            datum = data_map.get(str(index))
            if datum is None:
              #LOG.critical("Memcache buffer '%s' does not contain element %d." % (namespace, index))
              return ""
            data_array.append(datum)
          text = str("".join(data_array))
          # Abandon the data, memcache will clean it up.
      # else:
        #LOG.warning("Duplicate packet for buffer '%s'." % namespace)
    return urllib.unquote(text)

  def cleanup(self):
    '''Function to delete unused data from tables'''
    pass

  def handleRequest(self, text):
    actions = self.parseRequest(text)
    return self.doActions(actions)

  def loadViews(self, actions):
    # Enumerate all the requested view objects.
    # Build a list of database keys and ids for each object
    viewobj_ids = []
    viewobj_values = []
    for action in actions:
      if (action["username"], action["filename"]) not in viewobj_ids:
        viewobj_ids.append((action["username"], action["filename"]))
        view = db((db.viewobj.username==action["username"]) & (db.viewobj.filename==action["filename"])).select().first()
        #if view:    LOG.info("shadow:%s" % view.shadow)
        viewobj_values.append(view)
    # Load all needed view objects from Datastore
    #viewobj_values = db.viewobj

    # Populate the hashes and create any missing objects.
    viewobjs = {}
    for index in xrange(len(viewobj_ids)):
      id = viewobj_ids[index]
      viewobj = viewobj_values[index]
      if viewobj is None:
        view_id = db.viewobj.insert(username=action["username"], filename=action["filename"])
        viewobj = db.viewobj[view_id]
        #LOG.info("Created new ViewObj: '%s'" % viewobj)
      # else:
        # Uncompress the edit stack from a string.
        #LOG.info("Loaded %db ViewObj: '%s'" % (len(viewobj.shadow), viewobj))
      viewobjs[id] = viewobj
    return viewobjs

  def saveViews(self, viewobjs):
    # Build unified list of objects to save to Datastore.

    for viewobj in viewobjs.values():
      if viewobj.shadow is None:
        #LOG.info("Nullified ViewObj: '%s'" % viewobj)
        #LOG.info("shadow:%s" % viewobj.shadow)
        viewobj.delete_record()
          
      elif viewobj.changed:
        # Compress the edit stack into a string.
        viewobj.update_record(changed = False)
        #LOG.info("Saved %db ViewObj: '%s'" % (len(viewobj.shadow), viewobj))

  def applyPatches(self, viewobj, diffs, action):
    """Apply a set of patches onto the view and text objects.  This function must
      be enclosed in a lock or transaction since the text object is shared.

    Args:
      textobj: The shared server text to be updated.
      viewobj: The user's view to be updated.
      diffs: List of diffs to apply to both the view and the server.
      action: Parameters for how forcefully to make the patch; may be modified.
    """
    # Expand the fragile diffs into a full set of patches.
    patches = DMP.patch_make(viewobj.shadow, diffs)
    #LOG.info("***shadow: %s" % viewobj.shadow)
    #LOG.info("kc: %s" % viewobj.textobj.version)
    #LOG.info("diffs: %s" % diffs)
    #LOG.info("newShadow: %s" % DMP.diff_text2(diffs))
    # First, update the client's shadow.
    viewobj.update_record(backup_shadow = viewobj.shadow,
        shadow = DMP.diff_text2(diffs),
        backup_shadow_server_version = viewobj.shadow_server_version,
        changed = True)
    #LOG.info("backup_shadow: %s" % viewobj.backup_shadow)
    #LOG.info("shadow: %s" % viewobj.shadow)

    # Second, deal with the server's text.
    textobj = viewobj.textobj
    #LOG.info("textobj: %s" % textobj.text)
    if textobj.text is None:
      # A view is sending a valid delta on a file we've never heard of.
      textobj.update_record(text = viewobj.shadow)
      #LOG.info("shadow: %s" % viewobj.shadow)
      action["force"] = False
     # #LOG.info("Set content: '%s'" % viewobj)
    else:
      if action["force"]:
        # Clobber the server's text if a change was received.
        if patches:
          mastertext = viewobj.shadow
         # #LOG.info("Overwrote content: '%s'" % viewobj)
        else:
          mastertext = textobj.text
      else:
        (mastertext, results) = DMP.patch_apply(patches, textobj.text)
        #LOG.info("mastertext: %s" % mastertext)
       # #LOG.info("Patched (%s): '%s'" % (",".join(["%s" % (x) for x in results]), viewobj))
      # mastertext = viewobj.shadow
      textobj.update_record(text = mastertext)
    #LOG.info("textobj: %s" % textobj.text)
    #LOG.info("shadow: %s" % viewobj.shadow)

  def doActions(self, actions):
    viewobjs = self.loadViews(actions)

    output = []
    viewobj = None
    last_username = None
    last_filename = None
    user_views = None

    for action_index in xrange(len(actions)):
      # Use an indexed loop in order to peek ahead on step to detect
      # username/filename boundaries.
      action = actions[action_index]
      username = action["username"]
      filename = action["filename"]
      viewobj = viewobjs[(username, filename)]
      viewobj.update_record(textobj = fetchText(filename))
      if action["mode"] == "null":
        # Nullify the text.
        #LOG.info("Nullifying: '%s'" % viewobj)
        # Textobj transaction not needed; just a set.
        textobj = viewobj.textobj
        textobj.update_record(text = "")
        viewobj.delete_record()
        continue

      if (action["server_version"] != viewobj.shadow_server_version and
          action["server_version"] == viewobj.backup_shadow_server_version):
        # Client did not receive the last response.  Roll back the shadow.
        #LOG.warning("Rollback from shadow %d to backup shadow %d" %(viewobj.shadow_server_version, viewobj.backup_shadow_server_version))
        
        viewobj.update_record(shadow = viewobj.backup_shadow,
            shadow_server_version = viewobj.backup_shadow_server_version,
            edit_stack = json.dumps([]),
            changed = True)
        #LOG.info("shadow:%s" % viewobj.shadow)

      # Remove any elements from the edit stack with low version numbers which
      # have been acked by the client.
      # viewobj.update_record(edit_stack = json.dumps([]))
      x = 0
      stack = json.loads(viewobj.edit_stack)
      while x < len(stack):
        if stack[x][0] <= action["server_version"]:
          del stack[x]
        else:
          x += 1
      viewobj.update_record(edit_stack = json.dumps(stack))
      if action["mode"] == "raw":
        # It's a raw text dump.
        data = urllib.unquote(action["data"]).decode("utf-8")
        #LOG.info("Got %db raw text: '%s'" % (len(data), data))
        
        # First, update the client's shadow.
        viewobj.update_record(delta_ok = True,
            backup_shadow = viewobj.shadow,
            shadow = data,
            backup_shadow_server_version = viewobj.shadow_server_version,
            shadow_client_version = action["client_version"],
            shadow_server_version = action["server_version"],
            edit_stack = json.dumps([]),
            changed = True)
        #LOG.info("shadow:%s" % viewobj.shadow)
        # Textobj transaction not needed; in a collision here data-loss is
        # inevitable anyway.
        textobj = viewobj.textobj
        #LOG.info("Survived so far!!!")
        if action["force"] or textobj.text is None:
          # Clobber the server's text.
          if textobj.text != data:
            textobj.update_record(text = data)
            #LOG.info("Overwrote content: '%s'" % viewobj.textobj.text)
      elif action["mode"] == "delta":
        # It's a delta.
        #LOG.info("Got '%s' delta: '%s'" % (action["data"], viewobj.textobj.version))
        if action["server_version"] != viewobj.shadow_server_version:
          # Can't apply a delta on a mismatched shadow version.
          viewobj.update_record(delta_ok = False)
          #LOG.warning("Shadow version mismatch: %d != %d" % (action["server_version"], viewobj.shadow_server_version))
        elif action["client_version"] > viewobj.shadow_client_version:
          # Client has a version in the future?
          viewobj.update_record(delta_ok = False)
          #LOG.warning("Future delta: %d > %d" % (action["client_version"], viewobj.shadow_client_version))
        elif action["client_version"] < viewobj.shadow_client_version:
          # We've already seen this diff.
          pass
          #LOG.warning("Repeated delta: %d < %d" % (action["client_version"], viewobj.shadow_client_version))
        else:
          # Expand the delta into a diff using the client shadow.
          if viewobj.shadow is None:
            # This view was previously nullified.
            #LOG.info("shadow:%s" % viewobj.shadow)
            viewobj.update_record(shadow = "")
          try:
            diffs = DMP.diff_fromDelta(viewobj.shadow, action["data"])
          except ValueError:
            diffs = None
            viewobj.update_record(delta_ok = False)
            #LOG.warning("Delta failure, expected %d length: '%s'" % (len(viewobj.shadow), viewobj))
          viewobj.update_record(shadow_client_version = viewobj.shadow_client_version+1, changed = True)
          if diffs != None:
            # Textobj transaction required for read/patch/write cycle.
            # dib.run_in_transaction(self.applyPatches, viewobj, diffs, action)
            self.applyPatches(viewobj, diffs, action)
            # TRANSACT = True
          # else: TRANSACT = False

      # Generate output if this is the last action or the username/filename
      # will change in the next iteration.
      #LOG.info("So far Sooo Good...")
      if ((action_index + 1 == len(actions)) or
          actions[action_index + 1]["username"] != username or
          actions[action_index + 1]["filename"] != filename):
        print_username = None
        print_filename = None
        if action["echo_username"] and last_username != username:
          # Print the username if the previous action was for a different user.
          print_username = username
        if last_filename != filename or last_username != username:
          # Print the filename if the previous action was for a different user
          # or file.
          print_filename = filename
        #LOG.info("BFBlackHole: So far Sooo Good...")
        output.append(self.generateDiffs(viewobj, print_username,  print_filename, action["force"]))
        #LOG.info("BlackHole: So far Sooo Good...")
        last_username = username
        last_filename = filename

    self.saveViews(viewobjs)
    #LOG.info("Got o/p: %s" % "".join(output))
    return "".join(output)

  def generateDiffs(self, viewobj, print_username, print_filename, force):
    output = []
    if print_username:
      output.append("u:%s\n" %  print_username)
    if print_filename:
      output.append("F:%d:%s\n" % (viewobj.shadow_client_version, print_filename))

    # Textobj transaction not needed; just a get, stale info is ok.
    textobj = viewobj.textobj
    mastertext = textobj.text
    stack = json.loads(viewobj.edit_stack)
    if not stack: stack = []
    if viewobj.delta_ok:
      if mastertext is None:
        mastertext = ""
      # Create the diff between the view's text and the master text.
      diffs = DMP.diff_main(viewobj.shadow, mastertext)
      DMP.diff_cleanupEfficiency(diffs)
      text = DMP.diff_toDelta(diffs)
      if force:
        # Client sending 'D' means number, no error.
        # Client sending 'R' means number, client error.
        # Both cases involve numbers, so send back an overwrite delta.
        stack.append((viewobj.shadow_server_version, "D:%d:%s\n" % (viewobj.shadow_server_version, text)))
        viewobj.update_record(edit_stack = json.dumps(stack))
      else:
        # Client sending 'd' means text, no error.
        # Client sending 'r' means text, client error.
        # Both cases involve text, so send back a merge delta.
        stack.append((viewobj.shadow_server_version, "d:%d:%s\n" % (viewobj.shadow_server_version, text)))
        viewobj.update_record(edit_stack = json.dumps(stack))
      viewobj.update_record(shadow_server_version = viewobj.shadow_server_version+1)
      #LOG.info("Sent '%s' delta: '%s'" % (text, viewobj))
    else:
      # Error; server could not parse client's delta.
      # Send a raw dump of the text.
      viewobj.update_record(shadow_client_version = viewobj.shadow_client_version+1)
      if mastertext is None:
        mastertext = ""
        stack.append((viewobj.shadow_server_version, "r:%d:\n" % viewobj.shadow_server_version))
        viewobj.update_record(edit_stack = json.dumps(stack))
        #LOG.info("Sent empty raw text: '%s'" % viewobj)
      else:
        # Force overwrite of client.
        text = mastertext
        text = text.encode("utf-8")
        text = urllib.quote(text, "!~*'();/?:@&=+$,# ")
        stack.append((viewobj.shadow_server_version, "R:%d:%s\n" % (viewobj.shadow_server_version, text)))
        viewobj.update_record(edit_stack = json.dumps(stack))
        #LOG.info("Sent %db raw text: '%s'" % (len(text), viewobj.textobj.text))

    viewobj.update_record(shadow = mastertext, changed = True)
    #LOG.info("shadow:%s" % viewobj.shadow)

    #if not json.loads(viewobj.edit_stack):  return "".join(output)
    for edit in stack:#json.loads(viewobj.edit_stack)
      output.append(edit[1])
    
    #LOG.info("EndOfBlackHole: So far Sooo Good...")
    return "".join(output)


def main(): 
  logging.basicConfig()
  #CFG.initConfig("lib/mobwrite_config.txt")
  mobwrite = MobWrite2Py()
  form = request.vars
  #LOG.info("form:%s" % form)
  ret = ""
  if form.has_key("q"):
    # Client sending a sync.  Requesting text return.
    response.headers["Content-Type:"] = "text/plain"
    ret = mobwrite.handleRequest(form["q"])
    #LOG.info("Handled a q request")
  elif form.has_key("p"):
    # Client sending a sync.  Requesting JS return.
    response.headers["Content-Type:"] = "text/javascript"
    value = mobwrite.handleRequest(form["p"])
    #LOG.info("Handled a p request")
    value = value.replace("\\", "\\\\").replace("\"", "\\\"")
    value = value.replace("\n", "\\n").replace("\r", "\\r")
    ret = "mobwrite.callback(\"%s\");" % value
  elif form.has_key("clean"):
    # Cron job to clean the database.
    response.headers["Content-Type:"] = "text/plain"
    mobwrite.cleanup()
  elif os.environ["QUERY_STRING"]:
    # Display a minimal editor.
    response.headers["Content-Type:"] = "text/html"
    f = open("editor.html")
    ret = f.read()
    f.close
  else:
    # Unknown request.
    response.headers["Content-Type:"] = "text/plain"
  
  #LOG.info("Disconnecting.")
  logging.shutdown()
  ret = ret+"\n"
  return ret
  #return response.render('mobwrite/mobwrite', locals())

# def test(viewobj, *args, **kwargs):
    # return viewobj.update_record(*args, **kwargs)

def index():
  #VALIDATION!!!
  
  return main()

  # transact(fetchText, "doodle.it")
  # textobj = db(db.files.bash=="doodle.it").select().first()
  # test(textobj, text="zyx", version="done")
  # textobj = db(db.files.bash=="changeThis.txt").select().first()
  # ret = textobj.version
  # textobj.update_record(text="abcd", version="live")
  # ret = ret +":"+ textobj.version
  # textobj.delete_record()
  # return response.render('mobwrite/mobwrite', locals())