#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A simple script to compare the features in an SSR file with the OpenStreetMap XAPI.
The results are presented to the user, eventually providing edit/update capabalities.
"""

import geojson
import simplejson as json
import sys
import requests
from   codecs import        open, getreader
from   lxml import etree as tree
from   urllib import        urlopen, quote_plus 
from   Levenshtein import   ratio
from   math import          sqrt

#XAPI_URL="http://jxapi.osm.rambler.ru/xapi/api/0.6/*[bbox=%s,%s,%s,%s]"
XAPI_URL="http://www.overpass-api.de/api/xapi?*[bbox=%s,%s,%s,%s]"
NAME_Q  ="[name=%s]"
# parameters = name urlencoded, lon, lat, lon, lat
TOL = TOLERANCE = 0.005 # degrees of search in area
OSM_URL  = "http://www.openstreetmap.org/?lat=%.4f&lon=%.4f&zoom=14&layers=M"
EDIT_URL = "http://www.openstreetmap.org/edit?editor=id&lat=%.4f&lon=%.4f&zoom=17"
NK_URL   = "http://beta.norgeskart.no/?sok=%.4f,%.4f#14/%.4f/%.4f"
NODE_URL = "http://www.openstreetmap.org/?node=%s" 

API    = "http://api.openstreetmap.org"

navntype    = json.loads(open("navntype.json","r","utf-8").read())
credentials = json.loads(open("credentials.json","r","utf-8").read())

osmtypes    = {
  6:  "natural=peak",   # massif?
  16: "natural=valley", # only way and area!
  37: "waterway=river", # bekk
  83: "natural=bay",
  104:"place=farm",     # grend
  108:"place=farm",     # bruk
  110:"building=cabin", # fritidsbolig, area!
}

skrstat = {
  "G": "Godkjent",
  "V": "Vedtak",
  "A": "Avslått",
}
tystat = {
  "H": "hovednavn",
}
langcode = {
  "NO": "no",
  "SN": "se",
}

self, fin, fout = sys.argv

data = geojson.loads(open(fin,"r","utf-8").read())
features = data['features']

status = {} # dict:ssrid->{found, ...}

def identify(feature):
  lon, lat = map(float,feature['geometry']['coordinates'])
  sname    = feature['properties']['enh_snavn']
  forname  = feature['properties']['for_snavn']

  if sname != forname:
    print sname,"!=",forname,"!!!111", "avslått?",  skrstat[feature['properties']['skr_snskrstat']]
    return

  ssrid    = feature['properties']['enh_ssr_id']

  XTOL = TOL * 100
  queryByName = (XAPI_URL + NAME_Q) % (lon-XTOL, lat-XTOL, lon+XTOL, lat+XTOL, quote_plus(sname.encode('utf-8')))
  queryWoName = (XAPI_URL) % (lon-TOL, lat-TOL, lon+TOL, lat+TOL)
  osm = tree.parse(queryWoName)
  names = osm.findall(".//tag[@k='name']")
    
  if len(names) == 0:
    osm = tree.parse(queryByName)
    names = osm.findall(".//tag[@k='name']")

  status[ssrid] = {}
  status[ssrid]['found']=False
  bestratio = 0

  for name in names:
    osmname = unicode(name.get('v'))
    osmid   = name.getparent().get('id')
    osmlon  = name.getparent().get('lon') # only works for nodes, or we'll a) have to fetch references b) find a better distance calculation
    osmlat  = name.getparent().get('lat')
    if osmlon:
      dx = float(osmlon)-lon
      dy = float(osmlat)-lat
      distance = sqrt(dx*dx+dy*dy) # GIS people are allowed to simplify like this
    else:
      distance = float("inf")
    if sname == osmname or forname == osmname:
      if status[ssrid]['found']: # multiple matches
        status[ssrid]['nodes'].append({"osmid":osmid, "distance":distance})
      else:
        status[ssrid]['found']=True
        status[ssrid]['nodes']=[{"osmid":osmid, "distance":distance}]
        print "IDENTIFIED", osmname
        #print "Please check: ", OSM_URL % (float(osmlat), float(osmlon))
        #print "Please check: ", NK_URL % (lat, lon, lat, lon)
    else:
      delta = max( ratio(osmname, sname), ratio(osmname, forname) )
      if delta > bestratio:
        status[ssrid]['bestmatch'] = {"osmname":osmname, "osmid":osmid, "levenshtein":delta}
        bestratio = delta
  if not status[ssrid]['found']:
    print "------------------------------------------------------------------------------"
    print "Not found:", sname, "Best match:", str(status[ssrid].get('bestmatch',"None"))
    typ = unicode(feature['properties']['enh_navntype'])
    print "It's a ", navntype.get(typ, typ), "(number ",typ,")"
    print skrstat[feature['properties']['skr_snskrstat']], tystat [feature['properties']['enh_sntystat']]
    lang = langcode[feature['properties']['enh_snspraak']]
    print
    print "Please check: ", OSM_URL % (lat,lon)
    print "Please check: ", EDIT_URL % (lat,lon)
    print "Please check: ", NK_URL % (lat, lon, lat, lon)

    # course of action:
    # - ignore
    # - add to openstreetmap as node of type [see lookup table for places that make sense as node]
    # - add note (sic) to openstreetmap at this position, if it does not yet exist

    osmtype = osmtypes.get(int(typ), None)
    username, password = credentials

    print
    print "CHOOSE WISELY:"
    print "[I]gnore or E[x]it"
    if osmtype:
      print "[a]dd openstreetmap node of type %s" % osmtype
      print "add [n]ote" 
    print 

    userin = sys.stdin.readline()

    if userin in ["x\n", "X\n"]:
      sys.exit(0)
    elif userin in ["a\n", "A\n"]:
      r = requests.get(API + "/api/0.6/permissions", auth = (username, password))   
      perms  = tree.fromstring(r.text.encode('utf-8'),tree.XMLParser(encoding='utf-8'))
      if not perms.findall(".//permission[@name='allow_write_api']"):
        print "Permission denied."
        print tree.tostring(perms)
        sys.exit(1)
 

      typekey, typeval = osmtype.split("=")

      comment = "Adding single element from the central place name register of Norway (SSR): %s" % sname

      changeset = """
       <osm>
         <changeset>
           <tag k="created_by" v="ssr-api alpha"/>
           <tag k="comment" v="%s"/>
         </changeset>
       </osm>
      """ % (comment,)

      #create changeset
      r = requests.put(API + "/api/0.6/changeset/create", auth = (username, password), data = changeset)   

      csid = r.text
      print "Creating changeset id #", csid

      element = tree.fromstring("""
        <osm>
          <node changeset="%s" lat="%.6f" lon="%.6f">
            <tag k="name" v="%s"/>
            <tag k="name:%s" v="%s"/>
            <tag k="official_name" v="%s"/>
            <tag k="source" v="Kartverket"/>
            <tag k="source_id" v="%s"/>
            <tag k="source_ref" v="http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=%s"/>
            <tag k="%s" v="%s"/> 
          </node>
        </osm>
      """ % (csid, lat, lon, sname, lang, sname, sname, ssrid, ssrid, typekey, typeval)
      )


      #print tree.tostring(element)
      r = requests.put(API + "/api/0.6/node/create", auth = (username, password), data = tree.tostring(element))   

      print r 
      oid = r.text
      
      print "Created element", NODE_URL % oid
      
      r = requests.put(API + "/api/0.6/changeset/#%s/close" % csid, auth = (username, password))   

map(identify, features[8:20])

#fd = open(fout, "w")
#fd.write(json.dumps(status))
#fd.close()


