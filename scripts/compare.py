#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A simple script to compare the features in an SSR file with the OpenStreetMap XAPI.
The output is a json file, containing a dictionary with the findings - identified nodes or closest matches.
"""

import geojson
import simplejson as json
import sys
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

self, fin, fout = sys.argv

data = geojson.loads(open(fin,"r","utf-8").read())
features = data['features']


status = {} # dict:ssrid->{found, ...}

def identify(feature):
  lon, lat = map(float,feature['geometry']['coordinates'])
  sname    = feature['properties']['enh_snavn']
  forname  = feature['properties']['for_snavn']
  ssrid    = feature['properties']['enh_ssr_id']

  #queryByName = (XAPI_URL + NAME_Q) % (lon-TOL, lat-TOL, lon+TOL, lat+TOL, quote_plus(sname))
  queryWoName = (XAPI_URL) % (lon-TOL, lat-TOL, lon+TOL, lat+TOL)
  
  osm = tree.parse(queryWoName)
  
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
    else:
      delta = max( ratio(osmname, sname), ratio(osmname, forname) )
      if delta > bestratio:
        status[ssrid]['bestmatch'] = {"osmname":osmname, "osmid":osmid, "levenshtein":delta}
        bestratio = delta
  if not status[ssrid]['found']:
    print "Not found:", sname, "Best match:", str(status[ssrid].get('bestmatch',"None"))

map(identify, features)

fd = open(fout, "w")
fd.write(json.dumps(status))
fd.close()


