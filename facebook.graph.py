#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import pg
import re
import json
import csv
#import time
import datetime
import httplib
import urllib
import json

import mypass

usage = "usage: facebook.oauth.py [Facebook ID or username] [-h|--http-header|-co|--csv-out|-d|--database\
|-t OBJTYPE|--type=OBJTYPE|-c OBJTYPE|--connection-type=CONNTYPE] "
helptxt = "[OBJTYPE] currently supported: user|group \n\
[CONNTYPE] currently supported: feed|members \n\
Graph API Reference: http://developers.facebook.com/docs/reference/api/ "

pgconn = mypass.getConn()

FB_GRAPH_API = "graph.facebook.com"
fbook_oauth = mypass.getFacebookOauth()
APP_ID = str(fbook_oauth["app_id"])
ACCESS_TOKEN = fbook_oauth["access_token"]

def getMetadata(fbid, showHeaders=False):
    params = dict()
    params['access_token'] = APP_ID + "|" + ACCESS_TOKEN
    params['metadata'] = 1
    url = fbid + "?" + urllib.urlencode(params)
    conn = httplib.HTTPSConnection(FB_GRAPH_API)
    try:
	conn.request("GET", url)
    except Exception:
	#sys.exit(sys.exc_info())
	return json.loads('{}')
    r = conn.getresponse()
    if showHeaders:
	print "https://" + FB_GRAPH_API + url
	print r.status, r.reason
	print r.getheaders()
    js = json.loads(r.read())
    return js

if __name__ == "__main__":
    fbid = 0
    fbname = ""
    showheader = False
    csvout = False
    database = True
    allfields = False
    fields = ""
    fbobjtype = None
    fbconntype = None
    allowUpdate = True

    if len(sys.argv) > 1:
	if sys.argv[1] == "?" or sys.argv[1] == "--help":
	    print helptxt
	    sys.exit()
	try:
	    fbid = int(sys.argv[1])
	except ValueError: # fall back to unique name
	    fbid = 0
	    fbname = sys.argv[1]
    else:
	print usage
	sys.exit()

    if re.search('^[\w.]+$', fbname) is not None:
	fbidname = fbname
    elif fbid > 0:
	fbidname = fbid
    else:
	print usage
	sys.exit()

    if len(sys.argv) > 2:
	for i in range(2,len(sys.argv)):
	    if sys.argv[i] == "-h" or sys.argv[i] == "--http-header":
		showheader = True
	    if sys.argv[i] == "-co" or sys.argv[i] == "--csv-out":
		csvout = True
	    if sys.argv[i] == "-no" or sys.argv[i] == "--no-overwrite":
		allowUpdate = False
	    if sys.argv[i] == "-d" or sys.argv[i] == "--database":
		database = True
	    if sys.argv[i] == "-a" or sys.argv[i] == "--all-fields":
		allfields = True
	    if sys.argv[i] == "-t":
		if i+1<len(sys.argv):
		    fbobjtype = sys.argv[i+1]
	    if sys.argv[i].startswith("--type="):
		fbobjtype = sys.argv[i].split("=")[1]
	    if sys.argv[i] == "-c":
		if i+1<len(sys.argv):
		    fbconntype = sys.argv[i+1]
	    if sys.argv[i].startswith("--connection="):
		fbconntype = sys.argv[i].split("=")[1]

    #metadata = getMetadata(fbidname)
    #if fbobjtype is None:
    #	fbobjtype = metadata["type"]

    # process according to object type
    if allfields:
       	if fbobjtype == "user":
	    fields = "id,name,first_name,last_name,link,locale,updated_time,timezone,gender,verified,third_party_id,location,picture"
	elif fbobjtype == "group":
	    fields = "feed,members,docs"
	elif fbobjtype == "event":
	    fields = "feed,noreply,maybe,invited,attending,declined,picture"
	elif fbobjtype == "page":
	    fields = "id,name,description,picture,category,link,website,username,products,fan_count,founded,company_overview,mission"
	elif fbobjtype == "application":
	    fields = "id,name,description,picture,link,category"
	else:
	    fields = ""#feed,members,noreply,maybe,invited,attending,declined,picture,docs" # grab-all fields

    # get the parameters
    params = dict()
    params['access_token'] = APP_ID + "|" + ACCESS_TOKEN
    params['fields'] = fields
    params['metadata'] = 1
    params['type'] = fbobjtype

    # form the url
    url = "/" + str(fbidname)
    if fbconntype is not None:
	url += "/" + fbconntype
    url += "?%s" % urllib.urlencode(params)

    # try to connect
    conn = httplib.HTTPSConnection(FB_GRAPH_API)
    try:
	conn.request("GET", url)
	#resp, content = conn.request(url, "GET")
    except Exception:
	sys.exit(sys.exc_info())

    # get the response
    r = conn.getresponse()

    # print status code and headers
    if showheader:
	print "https://" + FB_GRAPH_API + url
	print r.status, r.reason
	print r.getheaders()

    # load the response as json string
    js = json.loads(r.read())

    # Handling of errors returned by the server
    if "error" in js:
	print js["error"]
	sys.exit(sys.exc_info())
    if "error_msg" in js:
	print js["error_msg"]
	sys.exit(sys.exc_info())


    # break if the reflected type does not match the one specified
    if fbobjtype is None:
	fbobjtype = js["type"]
    if js["type"] != fbobjtype:
	print "Specified type (%(stype)s) does not match reflected one [real type:%(rtype)s] " % { "stype": fbobjtype, "rtype": js["type"]}
	sys.exit()

    if csvout:
	import csv
	d = datetime.datetime.now()
	cw = csv.writer(open(str(fbidname) + "_" + d.strftime("%Y%m%d%H%M") + ".csv","w"), quoting=csv.QUOTE_MINIMAL)
	if fbobjtype == "group" and (fbconntype == "members" or allfields):
	    if fbconntype is None and allfields:
		members = js["members"]["data"]
	    else:
		members = js["data"]
	    for x in members:
		cw.writerow([x["id"],x["name"].encode("utf8")])
		#print x
    if database:
	if fbobjtype == "user":
	    js['retrieved'] = "NOW()"
	    for a in ["name", "first_name", "last_name"]:
		if a in js and js[a] is not None:
		    js[a] = js[a].encode("utf8")
	    try:
		pgconn.insert("facebook_users", js)
		print str(js["id"]) + "\t" + js["first_name"] + "\t" + js["last_name"]
	    except pg.ProgrammingError:
		try:
		    if allowUpdate:
			pgconn.update("facebook_users", js)
		except pg.ProgrammingError:
		    print "Cannot update"
		    print js
	if fbobjtype == "page":
	    if "location" in js:
		js["location"] = json.dumps(js["location"])
	    for a in ["name", "description", "location", "icon", "picture", "products", "website", "founded", "company_overview", "mission"]:
		if a in js and js[a] is not None:
		    js[a] = js[a].encode("utf8")
	    if "fan_count" in js:
		js["likes"] = js["fan_count"]
	    table_name = str("facebook_%ss" % fbobjtype)
	    try:
		pgconn.insert(table_name, js)
	    except pg.ProgrammingError:
		try:
		    if allowUpdate:
			print "Cannot insert, will update instead"
			pgconn.update(table_name, js)
		except pg.ProgrammingError:
		    print "Cannot update"
		    print js
	if fbobjtype == "application":
	    js['retrieved'] = "NOW()"
	    for a in ["name", "description", "picture", "link"]:
		if a in js and js[a] is not None:
		    js[a] = js[a].encode("utf8")
	    table_name = str("facebook_%ss" % fbobjtype)
	    try:
		pgconn.insert(table_name, js)
		print str(str(js["id"]))
	    except pg.ProgrammingError:
		try:
		    if allowUpdate:
			print "Cannot insert, will update instead"
			pgconn.update(table_name, js)
		    #print "duplicate: " + js["id"]
		except pg.ProgrammingError:
		    print "Cannot update"
		    print js
	if fbobjtype == "group" or fbobjtype == "event":
    	    for x in ["name", "description", "location", "icon", "picture"]:
		if x in js and js[x] is not None:
		    js[x] = js[x].encode("utf8")
	    if "venue" in js:
		js["venue"] = json.dumps(js["venue"]).encode("utf8")
	    if "owner" in js:
		js["owner"] = js["owner"]["id"]
	    table_name = str("facebook_%ss" % fbobjtype)
	    try:
		pgconn.update(table_name, js)
	    except pg.ProgrammingError:
		pgconn.update(table_name, js)
	if fbobjtype == "group" and (fbconntype == "members" or allfields):
	    d = datetime.datetime.now()
	    if fbconntype is None and allfields:
		members = js["members"]["data"]
	    else:
		members = js["data"]
	    for x in members:
		x["name"] = x["name"].encode("utf8")
		try:
		    pgconn.insert("facebook_users", x)
		except pg.ProgrammingError, ValueError:
		    try:
			pgconn.update("facebook_users", x)
		    except pg.ProgrammingError:
			print "Cannot update"
		try:
	    	    pgconn.insert("facebook_users_groups", {"uid":long(x["id"]),"gid":long(fbid)})
		except pg.ProgrammingError:
		    pass
		#print x
    else:
	print js

