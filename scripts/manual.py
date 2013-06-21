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
from   math import          sqrt
try:
  from Levenshtein import ratio
except:
  pass
import OsmApi


#XAPI_URL="http://jxapi.osm.rambler.ru/xapi/api/0.6/*[bbox=%s,%s,%s,%s]"
XAPI_URL =u"http://www.overpass-api.de/api/xapi?*[bbox=%s,%s,%s,%s]"
NAME_Q   =u"[name=%s]"
# parameters = name urlencoded, lon, lat, lon, lat
TOL = TOLERANCE = 0.005 # degrees of search in area
OSM_URL  = u"http://www.openstreetmap.org/?lat=%.4f&lon=%.4f&zoom=14&layers=M"
EDIT_URL = u"http://www.openstreetmap.org/edit?editor=id&lat=%.4f&lon=%.4f&zoom=17"
NK_URL   = u"http://beta.norgeskart.no/?sok=%.4f,%.4f#14/%.4f/%.4f"
NODE_URL = u"http://www.openstreetmap.org/?node=%s" 
PDIST    = 0.0005 # when creating a way or area stub, use this distance between points (should be tiny, but manageable)

navntype    = json.loads(open("navntype.json","r","utf-8").read())
credentials = json.loads(open("credentials.json","r","utf-8").read())
username, password = credentials

api = OsmApi.OsmApi(username=username, password=password, api="api.openstreetmap.org")

osmtypes    = {
  1:  ("node", "natural=peak"),   # berg - massif?
  2:  ("node", "natural=peak"),   # fjell - massif?
  3:  ("node", "natural=massif"), # fjellområde
  4:  ("area", "landuse=farm"),   # hei
  5:  ("node", "natural=peak"),   # høyde
  6:  ("node", "natural=peak"),   # kollen - massif?
  7:  ("node", "natural=ridge"),  # rygg
  8:  ("node", "natural=peak"),   # haug - mound?
  9:  ("node", "natural=mountainside"), # bakke - imaginary tag
  10: ("node", "natural=hillside"), # li - imaginary tag
  11: ("way", "natural=cliff"), # stup
#  12: ("area", "natural=fell"), # vidde
#  13: ("area", "natural=plain"), # slette
#  13: ("area", "natural=forest"), # mo
  15: ("way" , "natural=valley"), # dalføre (large valley)
  16: ("way" , "natural=valley"), # dal 
  17: ("node" , "natural=valley"), # botn - the end of a valley
  18: ("way" , "natural=valley"), # skar - a slight canyon, cut
  19: ("way" , "natural=valley"), # juv - an actual canyon
  20: ("way" , "natural=valley"), # søkk - a less pronounced canyon
#  21: ("node" , "natural=..."), # stein, findling
  31: ("area", "natural=water"),  # vann
  32: ("area", "natural=water;water=pond"),  # tjern
  35: ("node", "natural=bay"),    # vik
  36: ("way" , "waterway=river"), # elv
  37: ("node" , "waterway=river"), # bekk
  43: ("node", "natural=bay"),  # lon - bay in a river
  39: ("node" , "natural=waterfall"), # foss, according to ongoing discussion
  47: ("node", "natural=cape"),   # nes
  80: ("node", "natural=fjord"),   #fjord
  61: ("area", "natural=wetland"),   # myr + wetland=marsh
  84: ("area", "place=island"),   # ø sjø 
  85: ("area", "place=island"),   # holme
  83: ("node", "natural=bay"),    # vik i sjø
  87: ("node", "natural=cape"),   # nes i sjø
  89: ("node", "natural=beach"),  # strand
  90: ("area", "natural=skerry"), # skjær
  92: ("area", "natural=shoal"),  # grunne
  103:("node", "place=neighbourhood"),     # bygdelag
  104:("node", "place=farm"),     # grend
  108:("node", "place=farm"),     # bruk
  109:("area", "building=house"), # enebolig
  110:("area", "building=cabin"), # fritidsbolig, area!
  112:("area", "building=barn"), # bygg for jordbruk
  129:("node", "man_made=lighthouse"), # fyr
  130:("node", "man_made=lighthouse"), # lykt
  207:("node", "historical=archaeological_site;site_type=sacrificial_site"), # offersted
  211:("node", "natural=peak"),   # topp
  216:("relation", "place=island"), # øppe
  218:("node", "landuse=quarry"),  # grustak/steinbrudd
  221:("area", "landuse=harbour"), # havn
  261:("relation", "natural=water"),  # gruppe av vann
}

skrstat = {
  "G": "Godkjent",
  "V": "Vedtak",
  "S": "Samlevedtak",
  "A": "AVSLÅTT!",
  "F": "FORSLAG!",
  "K": "Vedtak påklaget",
  "U": "UVURDERT",
  "P": "PRIVAT",
  "I": "Internasjonalt",
  "H": "HISTORISK",
}
tystat = {
  "H": "hovednavn",
  "S": "SIDENAVN",
  "U": "UNDERNAVN",
}
langcode = {
  "NO": "no",
  "FI": "fi",
  "SN": "se",
  "SS": "sma",
  "SL": "smj",
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
  # we could probably use api.Map here
  queryByName = (XAPI_URL + NAME_Q) % (lon-XTOL, lat-XTOL, lon+XTOL, lat+XTOL, quote_plus(sname.encode('utf-8')))
  queryWoName = (XAPI_URL) % (lon-TOL, lat-TOL, lon+TOL, lat+TOL)
  r = requests.get(queryWoName) # can someone tell me why the f### encoding fails so badly?
  osm = tree.fromstring(r.content)
  names = osm.findall(".//tag")
  #names = osm.findall(".//tag[@k='name']")
    
  if len(names) == 0:
    osm = tree.fromstring(requests.get(queryByName).content)
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

    userin = sys.stdin.readline().strip()

    if osmtype:
      typekeys = osmtype.split(";")
      typetags = {}
      for key in typekeys:
        k,v = key.split("=")
        typetags[k]=v      

      tagdict = dict({ 
            "name":sname,
            "name:%s" % lang: sname,
            "official_name":sname,
            "source":"Kartverket",
            "source_id":unicode(ssrid),
            "source_ref":"http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=%s" % ssrid,
          }, **typetags)

    if userin in ["x", "X"]:
      sys.exit(0)
    elif userin in ["m", "M"]:
      print
      print "enter geometry to edit [format \"node|way|relation 123456]\":"
      userin = sys.stdin.readline().strip()

      typ, id = userin.split(" ")
      if typ == "node":      
        node = api.NodeGet(id)
        tags = node['tag']
      elif typ == "way":
        way = api.WayGet(id)
        tags = way['tag']
      elif typ == "relation":
        rel = api.RelationGet(id)
        print rel
        tags = rel['tag']

      print "BEFORE:"
      for tag in tags.keys():
        print " ",tag,"\t=",tags[tag]

      for tag in tagdict: # being friendly and appending data
        if tags.get(tag) == tagdict[tag]:
          continue
        elif tags.get(tag):
          tags[tag]=tags[tag]+";"+tagdict[tag]
        else: 
          tags[tag]=tagdict[tag]

      print "AFTER:"
      for tag in tags.keys():
        print " ",tag,"\t=",tags[tag]

      print "Please confirm with capital Y"
      userin = sys.stdin.readline().strip()

      if userin == "Y":
        comment = "Updating single element with metadata from the central place name register of Norway (SSR): %s" % sname
        csid    = api.ChangesetCreate({
           "comment":comment,
           "created_by":"ssr-api alpha",
        })

        if typ == "node":
          node['tag'] = tags
          node['changeset'] = csid
          api.NodeUpdate(node)
          api.ChangesetClose()
        elif typ == "way":
          way['tag'] = tags
          way['changeset'] = csid
          api.WayUpdate(way)
          api.ChangesetClose()
        elif typ == "relation":
          rel['tag'] = tags
          rel['changeset'] = csid
          api.RelationUpdate(rel)
          api.ChangesetClose()
  
    elif userin in ["a", "A"]:

      comment = "Adding single element from the central place name register of Norway (SSR): %s" % sname
      csid    = api.ChangesetCreate({
          "comment":comment,
          "created_by":"ssr-api alpha",
      })

      print "Creating changeset id #", csid


      if   geomtype == "area":
        n1   = api.NodeCreate({
          "lat":"%.6f"%lat,
          "lon":"%.6f"%(lon-PDIST),
        })
        n2   = api.NodeCreate({
          "lat":"%.6f"%lat,
          "lon":"%.6f"%(lon+PDIST),
        })
        n3   = api.NodeCreate({
          "lat":"%.6f"%(lat-PDIST),
          "lon":"%.6f"%(lon),
        })
        way = api.WayCreate({
          "nd":[n1["id"], n2["id"], n3["id"], n1["id"]],
          "tag":dict({"area":"yes"},**tagdict),
        })
        
        
      
      elif   geomtype == "way":
        n1   = api.NodeCreate({
          "lat":"%.6f"%lat,
          "lon":"%.6f"%(lon-PDIST),
        })
        n2   = api.NodeCreate({
          "lat":"%.6f"%lat,
          "lon":"%.6f"%(lon+PDIST),
        })
        way = api.WayCreate({
          "nd":[n1["id"], n2["id"]],
          "tag":tagdict,
        })
        
        
      elif geomtype == "node":
        node = api.NodeCreate({
          "lat":"%.6f"%lat,
          "lon":"%.6f"%lon,
          "tag":tagdict,
        })

        print "Created element", NODE_URL % node["id"]

      api.ChangesetClose()


map(identify, features[:]) # skipto Kvalvika 83



