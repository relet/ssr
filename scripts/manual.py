#!/usr/bin/env python26
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
try:
  from   lxml import etree as tree
except:
  import xml.etree.cElementTree as tree
from   urllib import        urlopen, quote_plus 
from   math import          sqrt
try:
  from Levenshtein import ratio
except:
  pass
import OsmApi


#XAPI_URL="http://jxapi.osm.rambler.ru/xapi/api/0.6/*[bbox=%s,%s,%s,%s]"
XAPI_URL="http://www.overpass-api.de/api/xapi?*[bbox=%s,%s,%s,%s]"
NAME_Q  ="[name=%s]"
# parameters = name urlencoded, lon, lat, lon, lat
TOL = TOLERANCE = 0.005 # degrees of search in area
OSM_URL  = "http://www.openstreetmap.org/?lat=%.4f&lon=%.4f&zoom=14&layers=M"
EDIT_URL = "http://www.openstreetmap.org/edit?editor=id&lat=%.4f&lon=%.4f&zoom=17"
NK_URL   = "http://beta.norgeskart.no/?sok=%.4f,%.4f#14/%.4f/%.4f"
NODE_URL = "http://www.openstreetmap.org/?node=%s" 

navntype    = json.loads(open("navntype.json","r","utf-8").read())
credentials = json.loads(open("credentials.json","r","utf-8").read())
username, password = credentials

api = OsmApi.OsmApi(username=username, password=password, api="api.openstreetmap.org")

osmtypes    = {
  6:  ("node", "natural=peak"),   # kollen - massif?
  8:  ("node", "natural=peak"),   # haug - mound?
  10: ("node", "natural=hillside"), # li - imaginary tag
  16: ("way" , "natural=valley"), # dal - only way and area!
  17: ("node" , "natural=valley"), # botn - the end of a valley
  31: ("area", "natural=water"),  # vann
  32: ("area", "natural=water"),  # tjern
  35: ("node", "natural=bay"),    # vik
  36: ("way" , "waterway=river"), # elv
  37: ("way" , "waterway=river"), # bekk
  47: ("node", "natural=cape"),   # nes
  61: ("area", "natural=wetland"),   # myr + wetland=marsh
  84: ("node", "natural=strait"), # sund
  85: ("area", "place=island"),   # holme
  83: ("node", "natural=bay"),    # vik i sjø
  87: ("node", "natural=cape"),   # nes i sjø
  104:("node", "place=farm"),     # grend
  108:("node", "place=farm"),     # bruk
  109:("area", "building=house"), # enebolig
  110:("area", "building=cabin"), # fritidsbolig, area!
  216:("relation", "place=island"), # øppe
  218:("node", "landuse=quarry"), # grustak/steinbrudd
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
  "SS": "sma",
}

self, fin = sys.argv

data = geojson.loads(open(fin,"r","utf-8").read())
features = data['features']

status = {} # dict:ssrid->{found, ...}

def identify(feature):
  lon, lat = map(float,feature['geometry']['coordinates'])
  sname    = feature['properties']['enh_snavn']
  forname  = feature['properties']['for_snavn']

  if sname != forname:
    return #usually avslatt

  ssrid    = feature['properties']['enh_ssr_id']

  XTOL = TOL * 100
  queryByName = (XAPI_URL + NAME_Q) % (lon-XTOL, lat-XTOL, lon+XTOL, lat+XTOL, quote_plus(sname.encode('utf-8')))
  queryWoName = (XAPI_URL) % (lon-TOL, lat-TOL, lon+TOL, lat+TOL)
  osm = tree.fromstring(requests.get(queryWoName).text.encode('utf-8'))
  names = osm.findall(".//tag")
  #names = osm.findall(".//tag[@k='name']")
    
  if len(names) == 0:
    osm = tree.fromstring(requests.get(queryByName).text.encode('utf-8'))
    names = osm.findall(".//tag")
    #names = osm.findall(".//tag[@k='name']")

  status[ssrid] = {}
  status[ssrid]['found']=False
  bestratio = 0

  for name in names:
    if not name.get('k') == 'name':
      continue
    try: 
      parent = name.getparent() #lxml
    except:
      parent_map = dict((c, p) for p in osm.getiterator() for c in p)
      parent = parent_map[name] 
    osmname = unicode(name.get('v'))
    osmid   = parent.get('id')
    osmlon  = parent.get('lon') # only works for nodes, or we'll a) have to fetch references b) find a better distance calculation
    osmlat  = parent.get('lat')
    #TODO: extract all "tag" elements from parent
    
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

        #TODO: compare source and source_id tags 
        #if source == "Kartverket" and link:
        #  print "linked to ssr"
        #  if link == ssrid:
        #    print "CORRECT!"
        #  else:
        #    print link, ssrid
        #else:
        #  print "not linked to ssr."# TODO: display edit/update options
        #  print "ID Editor: ", EDIT_URL % (float(osmlat),float(osmlon))
    else:
      try:
        delta = max( ratio(osmname, sname), ratio(osmname, forname) ) # Levenshtein may not be available
      except:
        delta = 1
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
    # - edit an existing area, way or node

    geomtype, osmtype = osmtypes.get(int(typ), (None,None))

    print
    print "CHOOSE WISELY:"
    print "[I]gnore or E[x]it"
    if osmtype:
      print "[a]dd openstreetmap %s (stub) of type %s" % (geomtype,osmtype)
      print "add [m]etadata to an existing %s in this area" % (geomtype)
      print "add [n]ote" 
    print 

    userin = sys.stdin.readline()

    if userin in ["x\n", "X\n"]:
      sys.exit(0)
    elif userin in ["a\n", "A\n"]:
      #r = requests.get(API + "/api/0.6/permissions", auth = (username, password))   
      #perms  = tree.fromstring(r.text)#.encode('utf-8'),tree.XMLParser(encoding='utf-8'))
      ##if not perms.findall(".//permission[@name='allow_write_api']"):
      #if not perms.findall(".//permission"):
      #  print "Permission denied."
      #  print tree.tostring(perms)
      #  sys.exit(1)

      typekey, typeval = osmtype.split("=")

      comment = "Adding single element from the central place name register of Norway (SSR): %s" % sname
      csid    = api.ChangesetCreate({
          "comment":comment,
          "created_by":"ssr-api alpha",
      })

      print "Creating changeset id #", csid

      if geomtype == "node":
        node = api.NodeCreate({
          "lat":"%.6f"%lat,
          "lon":"%.6f"%lon,
          "tag":{ 
            "name":sname,
            "name:%s" % lang: sname,
            "official_name":sname,
            "source":"Kartverket",
            "source_id":unicode(ssrid),
            "source_ref":"http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=%s" % ssrid,
            typekey: typeval,
        }})

        print "Created element", NODE_URL % node["id"]

      api.ChangesetClose()


map(identify, features[:20])

#fd = open(fout, "w")
#fd.write(json.dumps(status))
#fd.close()


