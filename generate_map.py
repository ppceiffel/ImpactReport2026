"""
generate_map.py — Carte interactive des importations d'énergie fossile en Europe
Données Eurostat 2023.

Couleur choroplèthe : % importations fossiles / consommation totale GIC
Clic sur un pays : panneau droit + flèches animées depuis fournisseurs
"""

import json, requests, urllib3, folium, branca.colormap as cm
urllib3.disable_warnings()

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
YEAR = "2023"

CONV_KTOE = {
    "C0000X0350-0370": 0.474,
    "G3000":           0.02388,
    "O4000XBIO":       1.020,
}
TYPE_LABEL = {
    "C0000X0350-0370": "Charbon",
    "G3000":           "Gaz naturel",
    "O4000XBIO":       "Pétrole",
}
TYPE_COLOR = {
    "Charbon":     "#4a4a4a",
    "Gaz naturel": "#e86c1f",
    "Pétrole":     "#a0001a",
}
EU_COUNTRIES = {
    "AT":"Autriche","BE":"Belgique","BG":"Bulgarie","CY":"Chypre",
    "CZ":"Tchéquie","DE":"Allemagne","DK":"Danemark","EE":"Estonie",
    "EL":"Grèce","ES":"Espagne","FI":"Finlande","FR":"France",
    "HR":"Croatie","HU":"Hongrie","IE":"Irlande","IS":"Islande",
    "IT":"Italie","LT":"Lituanie","LU":"Luxembourg","LV":"Lettonie",
    "MT":"Malte","NL":"Pays-Bas","NO":"Norvège","PL":"Pologne",
    "PT":"Portugal","RO":"Roumanie","SE":"Suède","SI":"Slovénie",
    "SK":"Slovaquie","UK":"Royaume-Uni",
}
ISO2_TO_ISO3 = {
    "AT":"AUT","BE":"BEL","BG":"BGR","CY":"CYP","CZ":"CZE","DE":"DEU",
    "DK":"DNK","EE":"EST","EL":"GRC","ES":"ESP","FI":"FIN","FR":"FRA",
    "HR":"HRV","HU":"HUN","IE":"IRL","IS":"ISL","IT":"ITA","LT":"LTU",
    "LU":"LUX","LV":"LVA","MT":"MLT","NL":"NLD","NO":"NOR","PL":"POL",
    "PT":"PRT","RO":"ROU","SE":"SWE","SI":"SVN","SK":"SVK","UK":"GBR",
}
# Centroïdes + iso2 des principaux fournisseurs (label Eurostat -> (iso2, lat, lon))
PARTNER_META = {
    "Russia":("RU",61.5,90.0),"United States":("US",38.0,-97.0),
    "Norway":("NO",64.5,17.7),"Algeria":("DZ",28.0,1.7),
    "Saudi Arabia":("SA",24.0,45.0),"Qatar":("QA",25.3,51.2),
    "Nigeria":("NG",9.0,8.0),"Kazakhstan":("KZ",48.0,67.0),
    "Australia":("AU",-25.0,133.0),"Colombia":("CO",4.0,-72.0),
    "South Africa":("ZA",-29.0,25.0),"Azerbaijan":("AZ",40.4,47.8),
    "Libya":("LY",27.0,17.0),"Iraq":("IQ",33.0,44.0),
    "United Kingdom":("GB",54.0,-2.3),"Netherlands":("NL",52.3,5.3),
    "Poland":("PL",52.0,20.0),"Belgium":("BE",50.8,4.3),
    "France":("FR",46.0,2.0),"Germany":("DE",51.0,10.0),
    "Czechia":("CZ",50.0,15.5),"Peru":("PE",-9.0,-75.0),
    "Canada":("CA",56.0,-96.0),"China":("CN",35.0,105.0),
    "Mozambique":("MZ",-18.0,35.0),"Egypt":("EG",26.0,30.0),
    "United Arab Emirates":("AE",24.0,54.0),"Kuwait":("KW",29.5,47.7),
    "Turkmenistan":("TM",40.0,60.0),"Iran":("IR",32.0,53.0),
    "Mexico":("MX",23.0,-102.0),"Angola":("AO",-11.0,18.0),
    "Gabon":("GA",-1.0,11.7),"Equatorial Guinea":("GQ",2.0,10.0),
    "Trinidad and Tobago":("TT",11.0,-61.0),"Brazil":("BR",-14.0,-51.0),
    "Argentina":("AR",-34.0,-64.0),"Venezuela":("VE",8.0,-66.0),
    "Indonesia":("ID",-5.0,120.0),"Malaysia":("MY",4.0,110.0),
    "Oman":("OM",21.0,57.0),"Ukraine":("UA",49.0,32.0),
    "Belarus":("BY",53.5,28.0),"Türkiye":("TR",39.0,35.0),
    "Turkey":("TR",39.0,35.0),"Switzerland":("CH",47.0,8.0),
    "Denmark":("DK",56.0,10.0),"Sweden":("SE",63.0,18.0),
    "Spain":("ES",40.0,-4.0),"Italy":("IT",42.5,12.5),
    "Austria":("AT",47.5,13.0),"Hungary":("HU",47.2,19.5),
    "Romania":("RO",45.5,24.5),"Bulgaria":("BG",42.7,25.5),
    "Greece":("GR",39.0,22.0),"Portugal":("PT",39.5,-8.0),
    "Serbia":("RS",44.0,21.0),"Albania":("AL",41.0,20.0),
    "Georgia":("GE",42.0,43.5),"Israel":("IL",31.5,35.0),
    "Japan":("JP",36.0,138.0),"South Korea":("KR",37.0,127.5),
    "India":("IN",20.0,78.0),"New Zealand":("NZ",-41.0,174.0),
    "Senegal":("SN",14.5,-14.5),"Ghana":("GH",7.9,-1.0),
    "Cyprus":("CY",35.1,33.4),"Luxembourg":("LU",49.8,6.1),
    "Latvia":("LV",56.9,24.6),"Lithuania":("LT",55.2,23.9),
    "Estonia":("EE",58.6,25.0),"Finland":("FI",64.0,26.0),
    "Iceland":("IS",65.0,-18.0),"Malta":("MT",35.9,14.5),
    "Slovenia":("SI",46.1,14.9),"Slovakia":("SK",48.7,19.7),
    "Croatia":("HR",45.1,15.4),"Bosnia and Herzegovina":("BA",44.0,17.0),
    "North Macedonia":("MK",41.6,21.7),"Moldova":("MD",47.4,28.4),
    "Montenegro":("ME",42.7,19.4),"Kosovo*":("XK",42.6,20.9),
    "Guyana":("GY",5.0,-59.0),"Congo":("CG",-1.0,15.8),
    "Democratic Republic of the Congo":("CD",-4.0,21.8),
    "Côte d'Ivoire":("CI",7.5,-5.5),"Cameroon":("CM",3.9,11.5),
    "Tanzania":("TZ",-6.0,35.0),"Liberia":("LR",6.4,-9.4),
    "Tunisia":("TN",34.0,9.0),"Morocco":("MA",32.0,-6.0),
}
PARTNER_EXCLUDE = {
    "TOTAL","NSP","EU27_2020","EUR_OTH","EX_SU_OTH","AME_OTH",
    "AFR_OTH","ASI_OTH","ASI_NME_OTH","EA21","EA20","EA19",
}

# Centroïdes approximatifs des capitales EU (iso3 -> [lat, lon])
EU_CENTROIDS = {
    "AUT":[47.8,13.0],"BEL":[50.8,4.3],"BGR":[42.7,23.3],"CYP":[35.1,33.4],
    "CZE":[50.0,14.5],"DEU":[51.2,10.0],"DNK":[56.0,10.0],"EST":[58.6,25.0],
    "GRC":[38.0,23.7],"ESP":[40.4,-3.7],"FIN":[60.2,25.0],"FRA":[46.0,2.0],
    "HRV":[45.8,16.0],"HUN":[47.5,19.1],"IRL":[53.3,-6.2],"ISL":[64.1,-21.9],
    "ITA":[41.9,12.5],"LTU":[54.7,25.3],"LUX":[49.6,6.1],"LVA":[56.9,24.1],
    "MLT":[35.9,14.5],"NLD":[52.4,4.9],"NOR":[59.9,10.8],"POL":[52.2,21.0],
    "PRT":[38.7,-9.2],"ROU":[44.4,26.1],"SWE":[59.3,18.1],"SVN":[46.1,14.5],
    "SVK":[48.2,17.1],"GBR":[51.5,-0.1],
}


def fetch(dataset, params):
    try:
        r = requests.get(f"{BASE_URL}/{dataset}", params=params, timeout=60, verify=False)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ERR {dataset}: {e}")
        return None


def _strides(sizes):
    st = [1]*len(sizes)
    for i in range(len(sizes)-2, -1, -1):
        st[i] = st[i+1]*sizes[i+1]
    return st


def _inv(data, dim):
    return {v: k for k, v in data["dimension"][dim]["category"]["index"].items()}


def decode_geo_vals(data, conv=1.0):
    """Decode a Eurostat JSON -> {geo_code: value} for all EU countries."""
    if not data or not data.get("value"):
        return {}
    dims, sizes = data["id"], data["size"]
    geo_inv  = _inv(data, "geo")
    time_inv = _inv(data, "time")
    strides  = _strides(sizes)
    out = {}
    for idx_str, val in data["value"].items():
        if val is None: continue
        idx = int(idx_str); indices, rem = [], idx
        for s in strides: indices.append(rem//s); rem %= s
        gc = geo_inv.get(indices[dims.index("geo")], "?")
        tc = time_inv.get(indices[dims.index("time")], "?")
        if gc in EU_COUNTRIES and tc == YEAR:
            out[gc] = round(val * conv, 1)
    return out


def fetch_import_total(dataset, siec, unit):
    d = fetch(dataset, {"format":"JSON","lang":"EN","freq":"A",
        "unit":unit,"siec":siec,"partner":"TOTAL",
        "sinceTimePeriod":YEAR,"untilTimePeriod":YEAR})
    return decode_geo_vals(d, CONV_KTOE[siec])


def fetch_consumption(siec):
    """Consommation intérieure brute GIC (nrg_bal_c) -> {geo: ktoe}"""
    d = fetch("nrg_bal_c", {"format":"JSON","lang":"EN","freq":"A",
        "unit":"KTOE","nrg_bal":"GIC","siec":siec,
        "sinceTimePeriod":YEAR,"untilTimePeriod":YEAR})
    return decode_geo_vals(d, 1.0)


def fetch_import_partners(dataset, siec, unit):
    """Top-5 fournisseurs par pays -> {geo: [{pays, ktoe, iso2, lat, lon}]}"""
    d = fetch(dataset, {"format":"JSON","lang":"EN","freq":"A",
        "unit":unit,"siec":siec,
        "sinceTimePeriod":YEAR,"untilTimePeriod":YEAR})
    if not d or not d.get("value"): return {}
    dims, sizes = d["id"], d["size"]
    geo_inv     = _inv(d, "geo")
    partner_inv = _inv(d, "partner")
    time_inv    = _inv(d, "time")
    partner_lbl = d["dimension"]["partner"]["category"]["label"]
    strides     = _strides(sizes)
    conv        = CONV_KTOE[siec]
    raw = {}
    for idx_str, val in d["value"].items():
        if val is None or val <= 0: continue
        idx = int(idx_str); indices, rem = [], idx
        for s in strides: indices.append(rem//s); rem %= s
        gc = geo_inv.get(indices[dims.index("geo")], "?")
        pc = partner_inv.get(indices[dims.index("partner")], "?")
        tc = time_inv.get(indices[dims.index("time")], "?")
        if gc not in EU_COUNTRIES or tc != YEAR: continue
        if pc in PARTNER_EXCLUDE: continue
        pname = partner_lbl.get(pc, pc)
        raw.setdefault(gc, {})[pname] = round(val * conv, 1)
    result = {}
    for gc, pmap in raw.items():
        top5 = sorted(pmap.items(), key=lambda x: -x[1])[:5]
        entries = []
        for pname, ktoe in top5:
            meta = PARTNER_META.get(pname)
            if meta:
                iso2, lat, lon = meta
                entries.append({"pays": pname, "ktoe": ktoe, "iso2": iso2, "lat": lat, "lon": lon})
            else:
                entries.append({"pays": pname, "ktoe": ktoe, "iso2": "UN", "lat": 0, "lon": 0})
        result[gc] = entries
    return result


def build_data():
    DATASETS = [
        ("nrg_ti_sff", "C0000X0350-0370", "THS_T"),
        ("nrg_ti_gas", "G3000",           "TJ_GCV"),
        ("nrg_ti_oil", "O4000XBIO",       "THS_T"),
    ]
    imports_total    = {}  # {geo: {lbl: ktoe}}
    imports_partners = {}  # {geo: {lbl: [{pays,ktoe,iso2,lat,lon}]}}
    consumption_type = {}  # {geo: {lbl: ktoe}}

    for ds, siec, unit in DATASETS:
        lbl = TYPE_LABEL[siec]
        print(f"  [{lbl}] importations…")
        for geo, v in fetch_import_total(ds, siec, unit).items():
            imports_total.setdefault(geo, {})[lbl] = v
        print(f"  [{lbl}] fournisseurs…")
        for geo, v in fetch_import_partners(ds, siec, unit).items():
            imports_partners.setdefault(geo, {})[lbl] = v
        print(f"  [{lbl}] consommation GIC…")
        for geo, v in fetch_consumption(siec).items():
            consumption_type.setdefault(geo, {})[lbl] = v

    print("  [Total] consommation GIC toutes énergies…")
    cons_total_raw = fetch_consumption("TOTAL")

    # Assemblage final par pays (iso3)
    all_geos = set(imports_total.keys())
    out = {}
    for geo in all_geos:
        iso3 = ISO2_TO_ISO3.get(geo)
        if not iso3: continue
        imp  = imports_total.get(geo, {})
        cons = consumption_type.get(geo, {})
        cT   = cons_total_raw.get(geo, 0)
        tot_imp = sum(imp.values())
        dep_pct = round(tot_imp / cT * 100, 1) if cT > 0 else 0

        types_data = {}
        for lbl in ["Charbon", "Gaz naturel", "Pétrole"]:
            imp_v  = imp.get(lbl, 0)
            cons_v = cons.get(lbl, 0)
            bar_pct = round(min(imp_v / cons_v * 100, 150), 1) if cons_v > 0 else 0
            types_data[lbl] = {
                "imp":     imp_v,
                "cons":    cons_v,
                "bar_pct": bar_pct,
                "partners": imports_partners.get(geo, {}).get(lbl, []),
            }

        out[iso3] = {
            "nom":     EU_COUNTRIES[geo],
            "dep_pct": dep_pct,
            "tot_imp": round(tot_imp, 1),
            "cons_tot": cT,
            "types":   types_data,
            "centroid": EU_CENTROIDS.get(iso3, [50, 15]),
        }
    return out


def get_geojson(iso3_set):
    url = ("https://raw.githubusercontent.com/python-visualization/folium"
           "/main/examples/data/world-countries.json")
    geo = requests.get(url, verify=False, timeout=30).json()
    return {"type":"FeatureCollection",
            "features":[f for f in geo["features"] if f["id"] in iso3_set]}


def make_map(data, out_path):
    max_dep = max((v["dep_pct"] for v in data.values()), default=100)

    colormap = cm.LinearColormap(
        colors=["#ffffcc","#fed976","#fd8d3c","#e31a1c","#800026"],
        vmin=0, vmax=min(max_dep, 100),
        caption="Importations fossiles / consommation totale (%)",
    )

    def style_fn(feature):
        iso3 = feature["id"]
        pct  = data.get(iso3, {}).get("dep_pct", 0)
        return {"fillColor": colormap(min(pct,100)) if pct else "#cccccc",
                "color":"white","weight":1.5,"fillOpacity":0.82}

    m = folium.Map(location=[54,14], zoom_start=4,
                   tiles="CartoDB positron", min_zoom=3, max_zoom=8)

    geo = get_geojson(set(data.keys()))
    print("GeoJSON OK.")
    folium.GeoJson(geo, name="pays",
        style_function=style_fn,
        highlight_function=lambda x: {"weight":3,"color":"#222","fillOpacity":0.95},
    ).add_to(m)
    colormap.add_to(m)

    js_data     = json.dumps(data,          ensure_ascii=False)
    js_colors   = json.dumps(TYPE_COLOR,    ensure_ascii=False)
    js_centroids= json.dumps(EU_CENTROIDS,  ensure_ascii=False)
    TYPE_ORDER  = ["Charbon","Gaz naturel","Pétrole"]
    js_order    = json.dumps(TYPE_ORDER)

    # ── HTML / CSS / JS embarqué ────────────────────────────────────────────
    # Note : on utilise __PYVAR__ comme placeholders pour éviter les conflits
    # avec les accolades JS dans le contenu Python
    html_tpl = """
<style>
*{box-sizing:border-box}
#side-panel{
  position:fixed;top:0;right:0;z-index:9999;
  width:340px;height:100vh;
  background:#fff;border-left:1px solid #e0e0e0;
  box-shadow:-4px 0 20px rgba(0,0,0,.15);
  font-family:'Segoe UI',Arial,sans-serif;
  transform:translateX(100%);transition:transform .3s ease;
  display:flex;flex-direction:column;overflow:hidden;
}
#side-panel.open{transform:translateX(0)}
#sp-header{
  padding:16px 16px 12px;background:#1a1a2e;color:#fff;
  flex-shrink:0;
}
#sp-header h2{margin:0 0 2px;font-size:16px}
#sp-header .sub{font-size:11px;opacity:.7}
#sp-close{
  position:absolute;top:12px;right:12px;
  background:none;border:none;color:#fff;
  font-size:20px;cursor:pointer;line-height:1;padding:4px;
}
#sp-body{flex:1;overflow-y:auto;padding:14px}
.dep-big{text-align:center;margin:8px 0 14px}
.dep-pct{font-size:36px;font-weight:800;color:#e31a1c;line-height:1}
.dep-label{font-size:11px;color:#888;margin-top:2px}
.energy-block{margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #f0f0f0}
.energy-block:last-child{border-bottom:none}
.energy-title{display:flex;align-items:center;gap:6px;font-weight:700;font-size:12px;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.e-dot{width:11px;height:11px;border-radius:50%}
.e-stats{display:flex;justify-content:space-between;font-size:11px;color:#666;margin-bottom:5px}
.e-stats strong{color:#222}
.bar-wrap{background:#f0f0f0;border-radius:5px;height:9px;overflow:hidden;margin-bottom:8px}
.bar-fill{height:9px;border-radius:5px;transition:width .4s ease}
.bar-pct-label{font-size:10px;color:#999;text-align:right;margin-top:-4px;margin-bottom:6px}
.partners-lbl{font-size:10px;color:#aaa;margin:6px 0 4px;font-style:italic}
.partner-row{display:flex;align-items:center;gap:6px;padding:3px 0;font-size:11px}
.p-flag{font-size:16px;line-height:1}
.p-name{flex:1;color:#333}
.p-val{font-size:10px;color:#888}
.grand-line{
  margin-top:12px;padding:10px 12px;background:#f7f7f7;
  border-radius:8px;display:flex;justify-content:space-between;
  font-size:12px;font-weight:700;color:#222;
}
#sp-source{font-size:9px;color:#bbb;padding:8px 14px;border-top:1px solid #f0f0f0;flex-shrink:0}
/* Leaflet arrow layers */
.arrow-flag-label{pointer-events:none}
</style>

<div id="side-panel">
  <div id="sp-header">
    <button id="sp-close" onclick="closePanel()">&#x2715;</button>
    <h2 id="sp-country-name">—</h2>
    <div class="sub">Importations d'énergie fossile — 2023</div>
  </div>
  <div id="sp-body"></div>
  <div id="sp-source">Source : Eurostat — nrg_ti_sff / nrg_ti_gas / nrg_ti_oil / nrg_bal_c</div>
</div>

<script>
(function(){
const DATA      = __DATA__;
const COLORS    = __COLORS__;
const CENTROIDS = __CENTROIDS__;
const ORDER     = __ORDER__;

let arrowLayers = [];
let activeIso3  = null;

function flag(iso2){
  if(!iso2||iso2==='UN') return '🌍';
  const base = 0x1F1E6;
  const a = iso2.toUpperCase().charCodeAt(0) - 65;
  const b = iso2.toUpperCase().charCodeAt(1) - 65;
  return String.fromCodePoint(base+a) + String.fromCodePoint(base+b);
}

function fmt(n){ return Math.round(n).toLocaleString('fr-FR'); }

function closePanel(){
  document.getElementById('side-panel').classList.remove('open');
  clearArrows();
  activeIso3 = null;
}

function clearArrows(){
  arrowLayers.forEach(l => { try{ map.removeLayer(l) }catch(e){} });
  arrowLayers = [];
}

function bezierPoints(p1, p2, n){
  const mlat=(p1[0]+p2[0])/2, mlng=(p1[1]+p2[1])/2;
  const dlat=p2[0]-p1[0], dlng=p2[1]-p1[1];
  const len=Math.sqrt(dlat*dlat+dlng*dlng)||1;
  const curve = len * 0.35;
  const cp=[mlat - dlng/len*curve, mlng + dlat/len*curve];
  const pts=[];
  for(let i=0;i<=n;i++){
    const t=i/n;
    pts.push([
      (1-t)*(1-t)*p1[0]+2*(1-t)*t*cp[0]+t*t*p2[0],
      (1-t)*(1-t)*p1[1]+2*(1-t)*t*cp[1]+t*t*p2[1]
    ]);
  }
  return pts;
}

function bearing(p1, p2){
  const lat1=p1[0]*Math.PI/180, lat2=p2[0]*Math.PI/180;
  const dL=(p2[1]-p1[1])*Math.PI/180;
  const y=Math.sin(dL)*Math.cos(lat2);
  const x=Math.cos(lat1)*Math.sin(lat2)-Math.sin(lat1)*Math.cos(lat2)*Math.cos(dL);
  return (Math.atan2(y,x)*180/Math.PI+360)%360;
}

function drawArrows(iso3){
  clearArrows();
  const d = DATA[iso3]; if(!d) return;
  const dest = d.centroid;

  // Collecter fournisseurs uniques (toutes catégories)
  const seen = {};
  ORDER.forEach(t => {
    const pts = (d.types[t]||{}).partners||[];
    pts.forEach((p,i) => {
      if(p.lat===0 && p.lon===0) return;
      const key = p.pays;
      if(!seen[key] || seen[key].ktoe < p.ktoe){
        seen[key] = { ...p, rank: i+1, type: t };
      }
    });
  });

  const partners = Object.values(seen)
    .sort((a,b)=>b.ktoe-a.ktoe)
    .slice(0,5);

  const colors = ['#e31a1c','#fd8d3c','#fecc5c','#74c476','#2c7fb8'];

  partners.forEach((p, idx) => {
    const src  = [p.lat, p.lon];
    const pts  = bezierPoints(src, dest, 30);
    const col  = colors[idx] || '#888';

    // Ligne courbe
    const line = L.polyline(pts, {
      color: col, weight: 2.5, opacity: 0.75, smoothFactor: 1
    }).addTo(map);
    arrowLayers.push(line);

    // Tête de flèche (triangle) à l'arrivée
    const last2 = pts.slice(-2);
    const hdg   = bearing(last2[0], last2[1]);
    const arrowHtml = `<div style="
      width:0;height:0;
      border-left:5px solid transparent;
      border-right:5px solid transparent;
      border-bottom:11px solid ${col};
      transform:rotate(${hdg}deg);
      transform-origin:center 70%;
      filter:drop-shadow(0 1px 1px rgba(0,0,0,.3))
    "></div>`;
    const arrow = L.marker(dest, {
      icon: L.divIcon({html:arrowHtml, className:'', iconSize:[10,11], iconAnchor:[5,6]}),
      interactive:false, zIndexOffset:1000+idx
    }).addTo(map);
    arrowLayers.push(arrow);

    // Drapeau + nom à la source
    const fl = flag(p.iso2);
    const flagHtml = `<div class="arrow-flag-label" style="
      display:flex;flex-direction:column;align-items:center;gap:2px;
      min-width:60px;transform:translateX(-50%)
    ">
      <span style="font-size:22px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.4))">${fl}</span>
      <span style="font-size:10px;background:#fff;border-radius:3px;
        padding:1px 5px;white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,.25);
        font-weight:600;color:${col}">${p.pays}</span>
    </div>`;
    const marker = L.marker(src, {
      icon: L.divIcon({html:flagHtml, className:'', iconAnchor:[30,30]}),
      interactive:false, zIndexOffset:500+idx
    }).addTo(map);
    arrowLayers.push(marker);
  });
}

function openPanel(iso3){
  const d = DATA[iso3]; if(!d) return;
  activeIso3 = iso3;

  document.getElementById('sp-country-name').textContent = d.nom;

  let html = `<div class="dep-big">
    <div class="dep-pct">${d.dep_pct.toFixed(1)} %</div>
    <div class="dep-label">Importations fossiles / consommation d'énergie totale</div>
  </div>`;

  ORDER.forEach(t => {
    const td = d.types[t]; if(!td || !td.imp) return;
    const col = COLORS[t]||'#888';
    const bpct = Math.min(td.bar_pct, 100);
    const pList = (td.partners||[]).map((p,i)=>{
      const fl = flag(p.iso2);
      return `<div class="partner-row">
        <span class="p-flag">${fl}</span>
        <span class="p-name">${p.pays}</span>
        <span class="p-val">${fmt(p.ktoe)} ktoe</span>
      </div>`;
    }).join('');

    html += `<div class="energy-block">
      <div class="energy-title">
        <span class="e-dot" style="background:${col}"></span>${t}
      </div>
      <div class="e-stats">
        <span>Importé : <strong>${fmt(td.imp)} ktoe</strong></span>
        <span>Consommé : <strong>${fmt(td.cons)} ktoe</strong></span>
      </div>
      <div class="bar-wrap">
        <div class="bar-fill" style="width:${bpct}%;background:${col}"></div>
      </div>
      <div class="bar-pct-label">Import / Conso : ${td.bar_pct.toFixed(0)} %</div>
      ${pList ? '<div class="partners-lbl">&#127758; Principaux fournisseurs :</div>'+pList : ''}
    </div>`;
  });

  html += `<div class="grand-line">
    <span>Total importé (fossile)</span>
    <span>${fmt(d.tot_imp)} ktoe</span>
  </div>`;

  document.getElementById('sp-body').innerHTML = html;
  document.getElementById('side-panel').classList.add('open');
  drawArrows(iso3);
}

// Initialisation
let map;
let justOpenedPanel = false;

function waitAndInit(){
  const key = Object.keys(window).find(k=>k.startsWith('map_'));
  if(!key){ setTimeout(waitAndInit,120); return; }
  map = window[key];

  map.eachLayer(l=>{
    if(!l.eachLayer) return;
    l.eachLayer(sub=>{
      if(!sub.feature) return;
      sub.on('click', function(e){
        // Stopper la propagation pour éviter que map.on('click') se déclenche
        L.DomEvent.stopPropagation(e);
        openPanel(sub.feature.id);
      });
    });
  });

  // Fermer le panneau sur clic dans la carte (hors pays)
  map.on('click', ()=>{
    if(activeIso3){ closePanel(); }
  });
}
document.addEventListener('DOMContentLoaded', waitAndInit);
})();
</script>
"""
    # Injection des données Python dans les placeholders
    html = (html_tpl
        .replace("__DATA__",      js_data)
        .replace("__COLORS__",    js_colors)
        .replace("__CENTROIDS__", js_centroids)
        .replace("__ORDER__",     js_order)
    )
    m.get_root().html.add_child(folium.Element(html))
    m.save(out_path)
    print(f"Carte sauvegardee : {out_path}")


def main():
    print("="*60)
    print(f"Carte importations energie fossile — Eurostat {YEAR}")
    print("="*60)
    print("\nRecuperation des donnees…")
    data = build_data()
    print(f"\n  {len(data)} pays charges")
    # Stats rapides
    for iso3, d in sorted(data.items(), key=lambda x: -x[1]["dep_pct"])[:5]:
        print(f"  {d['nom']:20s} dep={d['dep_pct']}%")
    make_map(data, "carte_energie_fossile_europe.html")


if __name__ == "__main__":
    main()
