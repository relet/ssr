ssr
===

Utilities to evaluate the SSR dataset (central place name register of Norway), compare it with Openstreetmap coverage, and import data into OSM.

All data (C) Kartverket, CC-BY 3.0 no 
Source: http://data.kartverket.no

Instead of a manual, which still has to be produced, here is an example interaction with the utility.

<pre>
[scripts]# ./manual.py ../Fylker/03_oslo_stedsnavn.geojson Skomakertjern
0.37% skipped.
IDENTIFIED Skomakertjern node 530826394
...but not linked to SSR
IDENTIFIED Skomakertjern way 46898951
...but not linked to SSR
------------------------------------------------------------------------------
Not found: Skomakertjern
It's a  Tjern (number  32 )
Godkjent hovednavn

Please check:  http://www.openstreetmap.org/?lat=59.9973&lon=10.6634&zoom=14&layers=M
Please check:  http://www.openstreetmap.org/edit?editor=id&lat=59.9973&lon=10.6634&zoom=17
Please check:  http://beta.norgeskart.no/?sok=59.9973,10.6634#14/59.9973/10.6634

CHOOSE WISELY:
[I]gnore, E[x]it or go [b]ack one element (not implemented)
[a]dd openstreetmap area (stub) of type natural=water;water=lake
add [m]etadata to an existing area in this area
     ^ SUGGESTED! -> way 46898951 Skomakertjern
add [n]ote

m

enter geometry to edit [format "node|way|relation 123456]":
  ...or empty for suggestion: way 46898951 Skomakertjern

BEFORE:
  source        = Topografisk kart over Oslo omeng. Blad VI. Udgivet af Norges geografiske Opmaaling 1887. Delvis revidert 1910 og 1915.
  natural       = water
  name  = Skomakertjern
AFTER:
  source:name   = Kartverket
  natural       = water
  name  = Skomakertjern
  no-kartverket-ssr:objid       = 72518
  no-kartverket-ssr:date        = 2003-04-01
  water         = lake
  source        = Topografisk kart over Oslo omeng. Blad VI. Udgivet af Norges geografiske Opmaaling 1887. Delvis revidert 1910 og 1915.
  no-kartverket-ssr:url         = http://faktaark.statkart.no/SSRFakta/faktaarkfraobjektid?enhet=72308
Please confirm with capital Y

</pre>
