#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A simple script to compare the features in an SSR file with the OpenStreetMap XAPI.
The results are presented to the user, eventually providing edit/update capabalities.

TODO: cleanup - this has become beautiful soup
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
NOTE_API =u"http://api.openstreetmap.org/api/0.6/notes"
# parameters = name urlencoded, lon, lat, lon, lat
TOL = TOLERANCE = 0.005 # degrees of search in area
TINY = MINTOLERANCE = 0.001 # finding exact local matches
OSM_URL  = u"http://www.openstreetmap.org/?lat=%.4f&lon=%.4f&zoom=14&layers=M"
EDIT_URL = u"http://www.openstreetmap.org/edit?editor=id&lat=%.4f&lon=%.4f&zoom=17"
NK_URL   = u"http://beta.norgeskart.no/?sok=%.4f,%.4f#14/%.4f/%.4f"
NODE_URL = u"http://www.openstreetmap.org/?node=%s" 
PDIST    = 0.0005 # when creating a way or area stub, use this distance between points (should be tiny, but manageable)

navntype    = json.loads(open("navntype.json","r","utf-8").read())
credentials = json.loads(open("credentials.json","r","utf-8").read())
username, password = credentials

api = OsmApi.OsmApi(username=username, password=password, api="api.openstreetmap.org")

# anything not mentioned defaults to place=locality
osmtypes    = {
  1:  ("node", "natural=peak"),   # berg - massif?
  2:  ("node", "natural=peak"),   # fjell - massif?
  3:  ("node", "natural=massif"), # fjellområde
  4:  ("area", "natural=heath"),  # hei
  5:  ("node", "natural=peak"),   # høydee / hill?
  6:  ("node", "natural=peak"),   # kollen - massif?
  7:  ("node", "natural=ridge"),  # rygg
  8:  ("node", "natural=peak"),   # haug - hill?
  9:  ("node", "natural=slope;place=locality"), # bakke 
  10: ("node", "natural=slope;place=locality"), # li 
  11: ("way" , "natural=cliff"),  # stup
#  12: ("area", "natural=fell"),  # vidde 
#  13: ("area", "natural=fell"), # slette
#  14: ("area", "natural=wood"),# mo
  15: ("way" , "natural=valley"), # dalføre (large valley)
  16: ("way" , "natural=valley"), # dal 
  17: ("node", "natural=valley"), # botn - the end of a valley
  18: ("way" , "natural=valley"), # skar - a slight canyon, cut
  19: ("way" , "natural=valley"), # juv - an actual canyon
  20: ("way" , "natural=valley"), # søkk - a less pronounced canyon
  21: ("node" , "natural=stone"),  # stein, findling
  30: ("area", "natural=water;water=lake"),  # innsjoe
  31: ("area", "natural=water;water=lake"),  # vann
  32: ("area", "natural=water;water=lake"),  # tjern
  33: ("way" , "waterway=dam"),   # pytt (tiny dam)
  35: ("node", "natural=bay"),    # vik
  36: ("way" , "waterway=river;layer=-1"), # elv
  37: ("way" , "waterway=stream;layer=-1"), # bekk
  38: ("way" , "waterway=ditch"), # grøftt - drain?
  39: ("way" , "waterway=waterfall"), # foss
  40: ("way" , "waterway=rapids"),# stryk
  42: ("area", "natural=water;water=pool"),  # høl, a pool under a waterfall
  43: ("node", "natural=bay"),    # lon - bay in a river
  44: ("area", "place=island"),   # ø
  45: ("area", "place=islet"),    # holme
  46: ("node", "natural=cape"),   # halvoey
  39: ("node", "natural=waterfall"), # foss, according to ongoing discussion
  47: ("node", "natural=cape"),   # nes
  80: ("node", "natural=fjord"),  #fjord
  61: ("node", "place=locality;natural=wetland"),   # myr + wetland=marsh - add as locality for now
  62: ("node", "place=locality;landuse=farm"),   # utmark - add as locality for now
  71: ("node", "place=croft"),     # setervoll
  82: ("node", "natural=strait"), # sund
  84: ("area", "place=island"),   # øy i sjø 
  85: ("area", "place=islet"),    # holme i sjø
  86: ("node", "natural=cape"),   # halvoey, preferred over natural=peninsula
  83: ("node", "natural=bay"),    # vik i sjø
  87: ("node", "natural=cape"),   # nes i sjø
  89: ("node", "natural=beach"),  # strand
  90: ("area", "natural=skerry"), # skjær
  92: ("area", "natural=shoal"),  # grunne
  100:("node", "place=town"),     # by
  101:("node", "place=village"),  # tettsted
  102:("node", "place=hamlet"),   # tettbebyggelse
  103:("node", "place=neighbourhood"),     # bygdelag
  104:("node", "place=farm"),     # grend
  105:("node", "place=neighbourhood"),     # boligfelt
  106:("node", "place=neighbourhood"),     # borettslag
  108:("node", "place=farm"),     # bruk
  109:("node", "building=house"), # enebolig
  110:("node", "building=cabin"), # fritidsbolig, area!
  111:("node", "place=farm"),     # seter
  112:("node", "building=farm_auxiliary"),  # bygg for jordbruk
  113:("area", "building=factory;man_made=works"), # fabrikk
  114:("area", "power=plant;building=industrial"), # kraftstasjon
  115:("area", "building=industrial"), # verksted
  116:("area", "building=shop"), # forretning
  117:("area", "building=hotel;tourism=hotel"), # hotell
  118:("area", "building=hotel;tourism=guest_house"), # pensjonat
  119:("node", "tourism=alpine_hut"), # turisthytte 
  120:("area", "building=school"),# skole
  121:("area", "building=hospital"), # sykehus
  122:("area", "amenity=nursing_home"), # helseinstitusjon/aldershjem
  123:("area", "building=church;amenity=place_of_worship"), # kirke
  125:("area", "amenity=community_centre"), # forsamlingshus/kulturhus
  126:("area", "building=civic"), # vaktstasjon 
  127:("area", "building=military;landuse=military"), # militaer bygning
  128:("area", "amenity=sports_centre;building=yes"), # sporthall
  129:("node", "man_made=lighthouse"),   # fyr
  130:("node", "man_made=lighthouse"),   # lykt, man_made=lighthouse may not always be correct
  132:("node", "place=district"),        # bydel
  140:("way", "highway=residential"),    # veg
  142:("way", "highway=track"),   # traktorveg
  143:("way", "highway=path"),    # sti
  146:("way", "bridge=yes"),      # bru
  150:("node", "barrier=lift_gate"), # vegbom
  154:("node", "man_made=pier"),  # kai
  155:("node", "man_made=pier"),  # brygge
  161:("node", "railway=station"),# stasjon
  162:("node", "railway=halt"),   # stoppeplass
  170:("node", "place=locality"), # eiendom
  190:("area", "leisure=sports_centre"),     #idrettsanlegg, may be leisure=pitch
  194:("way", "piste=downhill"),  #slalombakke
  201:("way", "waterway=dam"),    # dam
  204:("way", "waterway=dam;note=artifical facility used for timber floating"), # floetningsanlegg
  206:("node", "historic=archaeological_site"), # gammel bosetningsplass
  207:("node", "historic=archaeological_site;site_type=sacrificial_site"), # offersted
  208:("node", "tourism=attraction;place=locality"), # severdighet
  209:("node", "tourism=viewpoint"), # utsiktspunkt
  211:("node", "natural=peak"),   # topp
  213:("node", "place=locality"), # terrengdetalj
  216:("relation", "place=island"), # øppe
  218:("node", "landuse=quarry"), # grustak/steinbrudd
  221:("area", "landuse=harbour"),# havn
  225:("node", "place=locality"), # annen kulturdetalj
  251:("node", "tourism=museum"), # museum/bibliotek/galleri ~ amenity=arts_centre
  261:("relation", "natural=water"),  # gruppe av vann
  262:("relation", "natural=water;water=lake"),  # gruppe av tjern
  267:("node", "amenity=restaurant"),   # serveringssted
  280:("node", "place=farm"),     # gard
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

if len(sys.argv) == 3:
  self, fin, skipto = sys.argv
else:
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
  suggested = None

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
        status[ssrid]['nodes']=[{"osmid":osmid, "distance":distance}]
        print "IDENTIFIED", osmname, parent.tag, osmid
        typ = parent.tag
        if typ=="way":
          elem  = api.WayGet(osmid)
        elif typ=="node":
          elem  = api.NodeGet(osmid)
        elif typ=="relation":
          elem  = api.RelationGet(osmid)
        link = elem['tag'].get('source_id',None)
        if link:  
          status[ssrid]['found']=True
        else:
          print "...but not linked to SSR"
          suggested = (typ, osmid, elem['tag'].get('name',''))
        
    else:
      try:
        delta = max( ratio(osmname, sname), ratio(osmname, forname) ) # Levenshtein may not be available
      except:
        delta = 1
      if delta > bestratio:
        status[ssrid]['bestmatch'] = {"osmname":osmname, "osmid":osmid, "levenshtein":delta, "type":parent.tag}
        bestratio = delta
  if not status[ssrid]['found']:
    typ = unicode(feature['properties']['enh_navntype'])
    geomtype, osmtype = osmtypes.get(int(typ), ("node","place=locality"))
    lang = langcode[feature['properties']['enh_snspraak']]

    bestmatch  =  str(status[ssrid].get('bestmatch',"None"))
    exactmatch = None
 
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
            "source:name":"Kartverket", 
            "source_id":unicode(ssrid),
            "source_ref":"http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=%s" % ssrid,
          }, **typetags)



      exactmatches = api.Map(min_lon=lon-TINY,min_lat=lat-TINY,max_lon=lon+TINY,max_lat=lat+TINY)
      for match in exactmatches:
        mtyp = match['type']
        if mtyp == geomtype or (mtyp == "way") and (geomtype=="area"):
          mainkey, mainval = osmtype.split(";")[0].split("=")
          if match['data']['tag'].get(mainkey,'---') == mainval:
            exactmatch = "%s %s %s=%s" % (match['type'], match['data']['id'], mainkey, mainval)
             


    print "------------------------------------------------------------------------------"
    print "Not found:", sname
    if not suggested:
      print "  Best match:",     bestmatch
      print "  Location match:", exactmatch
    print "It's a ", navntype.get(typ, typ), "(number ",typ,")"
    print skrstat[feature['properties']['skr_snskrstat']], tystat [feature['properties']['enh_sntystat']]
    print
    print "Please check: ", OSM_URL % (lat,lon)
    print "Please check: ", EDIT_URL % (lat,lon)
    print "Please check: ", NK_URL % (lat, lon, lat, lon)

    # course of action:
    # - ignore
    # - add to openstreetmap as node of type [see lookup table for places that make sense as node]
    # - add note (sic) to openstreetmap at this position, if it does not yet exist
    # - edit an existing area, way or node


    print
    print "CHOOSE WISELY:"
    print "[I]gnore, E[x]it or go [b]ack one element (not implemented)"
    if osmtype:
      print "[a]dd openstreetmap %s (stub) of type %s" % (geomtype,osmtype)
      print "add [m]etadata to an existing %s in this area" % (geomtype)
      if suggested:
        print "     ^ SUGGESTED! -> %s %s %s" % suggested
      print "add [n]ote" 
    print 

    userin = sys.stdin.readline().strip()
      
    if userin in ["x", "X"]:
      sys.exit(0)
    elif userin in ["n", "N"]:
      NOTE_TEXT = """This place is a named place in the Norwegian place name register SSR.
This note identifies a possible conflict with existing data. Please compare:
http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=%s
--- 
Author comment: %s"""
                    
      print "Enter a reason for adding this note:"
      note = sys.stdin.readline().strip()
      note = NOTE_TEXT % (ssrid, note)
      print "Should I add the following note?"
      print
      print note
      print
      print "Please confirm with capital Y"
      confirm = sys.stdin.readline().strip()

      if confirm == "Y":
        params = {"lat":lat, "lon":lon, "text":note}
        r = requests.post(NOTE_API, auth=(username, password), params=params)
        print r
      
      pass
    elif userin in ["m", "M"]:
      print
      print "enter geometry to edit [format \"node|way|relation 123456]\":"
      if suggested:
        print "  ...or empty for suggestion: %s %s %s" % suggested
      userin = sys.stdin.readline().strip()
     
      if suggested and userin == "":
        typ, id, nname = suggested
      else:
        typ, id = userin.split(" ")

      if typ == "node":      
        node = api.NodeGet(id)
        tags = node['tag']
      elif typ == "way":
        way = api.WayGet(id)
        tags = way['tag']
      elif typ == "relation":
        rel = api.RelationGet(id)
        tags = rel['tag']

      print "BEFORE:"
      for tag in tags.keys():
        print " ",tag,"\t=",tags[tag]

      for tag in tagdict: # being friendly and appending data
        if tags.get(tag) == tagdict[tag]:
          continue
        elif tags.get(tag):
          if tag == "name": # replace name by default - TODO: be more careful in case another source is present
            tags[tag]=tagdict[tag]
          else:
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
           "source:name":"Kartverket",
           "source_ref":"http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=%s" % ssrid, 
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
          "source:name":"Kartverket",
          "source_ref":"http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=%s" % ssrid, 
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

ffwd = 0
if skipto is not None:
  while features[ffwd]['properties']['enh_snavn'] != skipto:
    ffwd += 1

print "%.2f%% skipped." % (float(ffwd) / len(features) * 100)

map(identify, features[ffwd:]) # 



