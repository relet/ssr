#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Write the comparison information back into the geojson file, 
while prettifying the results.
"""

import geojson
import simplejson as json
import sys
from   codecs import        open, getreader

self, ssr, comp, fout = sys.argv

data = geojson.loads(open(ssr,"r","utf-8").read())
features = data['features']

compdata = json.loads(open(comp, "r", "utf-8").read())

replace = {
  "skr_snskrstat"     : "spelling",
  "enh_ssr_id"        : "ssrid",
  "for_kartid"        : None,
  "for_regdato"       : None,
  "skr_sndato"        : None,
  "enh_snmynd"        : None,
  "for_sist_endret_dt": "updated",
  "enh_snspraak"      : "lang",
  "nty_gruppenr"      : None,
  "enh_snavn"         : "name",
  "enh_komm"          : None,
  "enh_ssrobj_id"     : None,
  "enh_sntystat"      : "status",
  "enh_navntype"      : "type",
  "for_snavn"         : None,
  "kom_fylkesnr"      : None,
  "kpr_tekst"         : None,
}

def upgrade(feature):
  props    = feature['properties']
  ssrid    = props['enh_ssr_id']
  compset  = compdata[str(ssrid)]

  for key in props.keys():
    if props.get(replace[key],None):
      props[replace[key]] = props[key]
    del props[key] 

  for key in compset.keys():
    #if key == "bestmatch":
    #  if compset["bestmatch"]["levenshtein"] < 0.85:
    #    continue
    props[key] = compset[key]
    
  if props["found"]:
    try:
      del props["bestmatch"]
    except:
      pass
    # flatten results to make them displayable
    nodes = props["nodes"]
    node  = reduce(lambda x,y:x["distance"] < y["distance"] and x or y, nodes)
    osmid = node["osmid"]
    props["osmid"] = osmid
    del props["nodes"]
  elif props.get("bestmatch",None):
    # flatten results to make them displayable
    props["levenshtein"] = props["bestmatch"]["levenshtein"]
    props["osmname"]     = props["bestmatch"]["osmname"]
    props["bestmatch"]   = props["bestmatch"]["osmid"]

  # github/mapbox style hints
  if props["found"]:
    props["marker-color"] = "#082"
  elif props.get("bestmatch", None):
    leven = compset["bestmatch"]["levenshtein"]
    red   = int((0.999-leven) * 10) # 0 and 1 should never happen
    green = int(leven * 10)
    rgb   = "#%s%s2" % (red, green)
    props["marker-color"] = rgb
  else:
    props["marker-color"] = "#802" 



map(upgrade, features)

#print features[0]

fd = open(fout, "w", "utf-8")
fd.write(geojson.dumps(data))
fd.close()


