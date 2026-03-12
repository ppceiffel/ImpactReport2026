"""
Génération de la carte HTML interactive des importations d'énergie fossile
en Europe — données Eurostat 2023.

Toutes les valeurs sont converties en ktoe (kilotonnes équivalent pétrole) :
  Charbon   THS_T  × 0.474
  Pétrole   THS_T  × 1.020
  Gaz       TJ_GCV × 0.02388
"""

import json
import requests
import urllib3
import folium
import branca.colormap as cm

urllib3.disable_warnings()

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
YEAR     = "2023"

CONV_KTOE = {
    "C0000X0350-0370": 0.474,
    "O4100_TOT":       1.020,
    "O4000XBIO":       1.020,
    "G3000":           0.02388,
}

TYPE_LABEL = {
    "C0000X0350-0370": "Charbon",
    "O4100_TOT":       "Pétrole brut",
    "O4000XBIO":       "Produits pétroliers",
    "G3000":           "Gaz naturel",
}

TYPE_COLOR = {
    "Charbon":             "#4a4a4a",
    "Gaz naturel":         "#e86c1f",
    "Pétrole brut":        "#8b0000",
    "Produits pétroliers": "#c0392b",
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

PARTNER_EXCLUDE = {
    "TOTAL","NSP","EU27_2020","EUR_OTH","EX_SU_OTH","AME_OTH",
    "AFR_OTH","ASI_OTH","ASI_NME_OTH","EA21","EA20",
}


def fetch(dataset, params):
    try:
        r = requests.get(f"{BASE_URL}/{dataset}", params=params, timeout=60, verify=False)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ✗ {dataset}: {e}")
        return None


def _strides(sizes):
    st = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        st[i] = st[i + 1] * sizes[i + 1]
    return st


def _inv(data, dim):
    return {v: k for k, v in data["dimension"][dim]["category"]["index"].items()}


def fetch_total_by_geo(dataset, siec, unit):
    """Retourne {geo_code: ktoe} pour le partenaire TOTAL."""
    d = fetch(dataset, {
        "format":"JSON","lang":"EN","freq":"A",
        "unit":unit,"siec":siec,"partner":"TOTAL",
        "sinceTimePeriod":YEAR,"untilTimePeriod":YEAR,
    })
    if not d or not d.get("value"):
        return {}
    dims, sizes = d["id"], d["size"]
    geo_inv  = _inv(d, "geo")
    time_inv = _inv(d, "time")
    strides  = _strides(sizes)
    conv     = CONV_KTOE[siec]
    out = {}
    for idx_str, val in d["value"].items():
        if val is None: continue
        idx = int(idx_str)
        indices, rem = [], idx
        for s in strides:
            indices.append(rem // s); rem %= s
        gc = geo_inv.get(indices[dims.index("geo")], "?")
        tc = time_inv.get(indices[dims.index("time")], "?")
        if gc in EU_COUNTRIES and tc == YEAR:
            out[gc] = round(val * conv, 1)
    return out


def fetch_partners(dataset, siec, unit):
    """Retourne {geo_code: {partner_label: ktoe}} top-5 par pays."""
    d = fetch(dataset, {
        "format":"JSON","lang":"EN","freq":"A",
        "unit":unit,"siec":siec,
        "sinceTimePeriod":YEAR,"untilTimePeriod":YEAR,
    })
    if not d or not d.get("value"):
        return {}
    dims, sizes = d["id"], d["size"]
    geo_inv     = _inv(d, "geo")
    partner_inv = _inv(d, "partner")
    time_inv    = _inv(d, "time")
    partner_lbl = d["dimension"]["partner"]["category"]["label"]
    strides     = _strides(sizes)
    conv        = CONV_KTOE[siec]
    raw: dict[str, dict[str, float]] = {}
    for idx_str, val in d["value"].items():
        if val is None or val == 0: continue
        idx = int(idx_str)
        indices, rem = [], idx
        for s in strides:
            indices.append(rem // s); rem %= s
        gc  = geo_inv.get(indices[dims.index("geo")], "?")
        pc  = partner_inv.get(indices[dims.index("partner")], "?")
        tc  = time_inv.get(indices[dims.index("time")], "?")
        if gc not in EU_COUNTRIES or tc != YEAR: continue
        if pc in PARTNER_EXCLUDE: continue
        pname = partner_lbl.get(pc, pc)
        raw.setdefault(gc, {})[pname] = round(val * conv, 1)
    # Garder top-5 par pays
    return {
        gc: [{"pays": p, "ktoe": v}
             for p, v in sorted(pmap.items(), key=lambda x: -x[1])[:5]]
        for gc, pmap in raw.items()
    }


def build_data():
    DATASETS = [
        ("nrg_ti_sff", "C0000X0350-0370", "THS_T"),
        ("nrg_ti_gas", "G3000",           "TJ_GCV"),
        ("nrg_ti_oil", "O4100_TOT",       "THS_T"),
        ("nrg_ti_oil", "O4000XBIO",       "THS_T"),
    ]
    totals_by_type:   dict[str, dict] = {}
    partners_by_type: dict[str, dict] = {}
    for dataset, siec, unit in DATASETS:
        lbl = TYPE_LABEL[siec]
        print(f"  [{lbl}] total…")
        totals_by_type[siec]   = fetch_total_by_geo(dataset, siec, unit)
        print(f"  [{lbl}] partenaires…")
        partners_by_type[siec] = fetch_partners(dataset, siec, unit)

    # {geo: {type_label: ktoe}}
    country_totals = {}
    for siec, geo_map in totals_by_type.items():
        for geo, val in geo_map.items():
            country_totals.setdefault(geo, {})[TYPE_LABEL[siec]] = val

    # {geo: {type_label: [{pays, ktoe}]}}
    country_partners = {}
    for siec, geo_map in partners_by_type.items():
        lbl = TYPE_LABEL[siec]
        for geo, plist in geo_map.items():
            country_partners.setdefault(geo, {})[lbl] = plist

    return country_totals, country_partners


def get_geojson(iso3_set):
    url = (
        "https://raw.githubusercontent.com/python-visualization/folium"
        "/main/examples/data/world-countries.json"
    )
    geo = requests.get(url, verify=False, timeout=30).json()
    return {
        "type": "FeatureCollection",
        "features": [f for f in geo["features"] if f["id"] in iso3_set],
    }


def make_map(country_totals, country_partners, out_path):
    totals_iso3   = {ISO2_TO_ISO3[g]: v for g, v in country_totals.items()   if g in ISO2_TO_ISO3}
    partners_iso3 = {ISO2_TO_ISO3[g]: v for g, v in country_partners.items() if g in ISO2_TO_ISO3}
    pays_iso3     = {ISO2_TO_ISO3[g]: n for g, n in EU_COUNTRIES.items()     if g in ISO2_TO_ISO3}

    grand_total = {
        iso3: round(sum(v for v in types.values()), 1)
        for iso3, types in totals_iso3.items()
    }
    max_val = max(grand_total.values()) if grand_total else 1
    iso3_set = set(totals_iso3.keys())

    print("Téléchargement du GeoJSON…")
    geo = get_geojson(iso3_set)

    colormap = cm.LinearColormap(
        colors=["#fff7bc","#fec44f","#d95f0e","#7f0000"],
        vmin=0, vmax=max_val,
        caption="Importations fossiles totales 2023 (ktoe)",
    )

    def style_fn(feature):
        val = grand_total.get(feature["id"], 0)
        return {
            "fillColor":   colormap(val) if val else "#cccccc",
            "color":       "white", "weight": 1.5, "fillOpacity": 0.82,
        }

    m = folium.Map(
        location=[54, 14], zoom_start=4,
        tiles="CartoDB positron", min_zoom=3, max_zoom=8,
    )
    folium.GeoJson(
        geo, name="pays",
        style_function=style_fn,
        highlight_function=lambda x: {"weight": 3, "color": "#222", "fillOpacity": 0.95},
    ).add_to(m)
    colormap.add_to(m)

    js_totals   = json.dumps(totals_iso3,   ensure_ascii=False)
    js_partners = json.dumps(partners_iso3, ensure_ascii=False)
    js_pays     = json.dumps(pays_iso3,     ensure_ascii=False)
    js_grand    = json.dumps(grand_total,   ensure_ascii=False)
    js_colors   = json.dumps(TYPE_COLOR,    ensure_ascii=False)
    TYPE_ORDER  = ["Charbon","Gaz naturel","Pétrole brut","Produits pétroliers"]
    js_order    = json.dumps(TYPE_ORDER)

    html = f"""
<style>
* {{ box-sizing: border-box; }}
#info-panel {{
  position: fixed; top: 12px; right: 12px; z-index: 9999;
  background: rgba(255,255,255,0.97); border-radius: 10px;
  padding: 14px 18px; box-shadow: 0 2px 14px rgba(0,0,0,.22);
  font-family: 'Segoe UI', Arial, sans-serif; min-width: 230px; max-width: 260px;
}}
#info-panel h3 {{ margin: 0 0 6px; font-size: 13px; color: #222; }}
#info-panel .subtitle {{ font-size: 11px; color: #777; margin-bottom: 10px; }}
.legend-bar {{ display: flex; align-items: center; gap: 7px; margin: 4px 0; font-size: 11px; color: #444; }}
.legend-swatch {{ width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0; }}
#info-panel .source {{ margin-top: 10px; padding-top: 8px; border-top: 1px solid #e0e0e0; font-size: 10px; color: #999; line-height: 1.5; }}
#tooltip-box {{
  position: fixed; z-index: 9998;
  background: rgba(255,255,255,0.98); border-radius: 10px;
  padding: 14px 16px; box-shadow: 0 4px 20px rgba(0,0,0,.28);
  font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px;
  pointer-events: none; display: none; min-width: 290px; max-width: 350px;
}}
#tooltip-box h4 {{ margin: 0 0 10px; font-size: 14px; color: #111; border-bottom: 2px solid #eee; padding-bottom: 6px; }}
.energy-block {{ margin-bottom: 12px; }}
.energy-title {{ font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 4px; color: #444; display: flex; align-items: center; gap: 5px; }}
.energy-title .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
.ktoe-total {{ font-size: 13px; font-weight: 700; color: #222; margin-bottom: 4px; }}
.bar-outer {{ background: #eee; border-radius: 4px; height: 6px; width: 100%; margin-bottom: 5px; overflow: hidden; }}
.bar-inner {{ height: 6px; border-radius: 4px; }}
.partners-title {{ font-size: 10px; color: #888; margin: 3px 0 2px; font-style: italic; }}
.partner-row {{ display: flex; justify-content: space-between; font-size: 11px; color: #444; padding: 1px 0; }}
.partner-rank {{ color: #bbb; margin-right: 3px; }}
.partner-val {{ color: #888; font-size: 10px; }}
.grand-total {{ margin-top: 10px; padding-top: 8px; border-top: 2px solid #eee; font-size: 13px; font-weight: 700; color: #111; display: flex; justify-content: space-between; }}
</style>

<div id="info-panel">
  <h3>🛢️ Importations d'énergie fossile en Europe</h3>
  <div class="subtitle">Année 2023 — unité : ktoe</div>
  <div class="legend-bar"><span class="legend-swatch" style="background:#4a4a4a"></span>Charbon</div>
  <div class="legend-bar"><span class="legend-swatch" style="background:#e86c1f"></span>Gaz naturel</div>
  <div class="legend-bar"><span class="legend-swatch" style="background:#8b0000"></span>Pétrole brut</div>
  <div class="legend-bar"><span class="legend-swatch" style="background:#c0392b"></span>Produits pétroliers</div>
  <div class="source">Source : Eurostat (nrg_ti_sff, nrg_ti_gas, nrg_ti_oil)<br>ktoe = kilotonnes équivalent pétrole<br>Survoler un pays pour le détail</div>
</div>

<div id="tooltip-box"></div>

<script>
(function() {{
  const TOTALS   = {js_totals};
  const PARTNERS = {js_partners};
  const PAYS     = {js_pays};
  const GRAND    = {js_grand};
  const COLORS   = {js_colors};
  const ORDER    = {js_order};
  const tooltip  = document.getElementById('tooltip-box');

  function fmt(n) {{ return Math.round(n).toLocaleString('fr-FR'); }}

  function showTooltip(e, iso3) {{
    const nom    = PAYS[iso3] || iso3;
    const types  = TOTALS[iso3]   || {{}};
    const ptns   = PARTNERS[iso3] || {{}};
    const gtotal = GRAND[iso3]    || 0;
    if (!gtotal) {{ tooltip.style.display = 'none'; return; }}

    const maxType = Math.max(...ORDER.map(t => types[t] || 0), 1);

    const blocks = ORDER.map(t => {{
      const val = types[t]; if (!val) return '';
      const col  = COLORS[t] || '#888';
      const pct  = Math.round((val / maxType) * 100);
      const pList= (ptns[t] || []).map((p, i) =>
        `<div class="partner-row"><span><span class="partner-rank">${{i+1}}.</span>${{p.pays}}</span><span class="partner-val">${{fmt(p.ktoe)}} ktoe</span></div>`
      ).join('');
      return `<div class="energy-block">
        <div class="energy-title"><span class="dot" style="background:${{col}}"></span>${{t}}</div>
        <div class="ktoe-total">${{fmt(val)}} ktoe</div>
        <div class="bar-outer"><div class="bar-inner" style="width:${{pct}}%;background:${{col}}"></div></div>
        ${{pList ? '<div class="partners-title">🌍 Principaux fournisseurs :</div>' + pList : ''}}
      </div>`;
    }}).join('');

    tooltip.innerHTML = `<h4>🏳️ ${{nom}}</h4>${{blocks}}<div class="grand-total"><span>Total fossile 2023</span><span>${{fmt(gtotal)}} ktoe</span></div>`;
    tooltip.style.display = 'block';
    moveTooltip(e);
  }}

  function moveTooltip(e) {{
    const ev = e.originalEvent || e;
    const x = ev.clientX, y = ev.clientY;
    const w = tooltip.offsetWidth || 320, h = tooltip.offsetHeight || 320;
    const vw = window.innerWidth,   vh = window.innerHeight;
    tooltip.style.left = (x + 18 + w > vw ? x - w - 10 : x + 18) + 'px';
    tooltip.style.top  = (y + 18 + h > vh ? y - h - 10 : y + 18) + 'px';
  }}

  function waitAndInit() {{
    const key = Object.keys(window).find(k => k.startsWith('map_'));
    if (!key) {{ setTimeout(waitAndInit, 120); return; }}
    window[key].eachLayer(l => {{
      if (!l.eachLayer) return;
      l.eachLayer(sub => {{
        if (!sub.feature) return;
        sub.on('mouseover', e => showTooltip(e, sub.feature.id));
        sub.on('mousemove', e => moveTooltip(e));
        sub.on('mouseout',  () => {{ tooltip.style.display = 'none'; }});
      }});
    }});
  }}
  document.addEventListener('DOMContentLoaded', waitAndInit);
}})();
</script>
"""
    m.get_root().html.add_child(folium.Element(html))
    m.save(out_path)
    print(f"✓ Carte sauvegardée : {out_path}")


def main():
    print("=" * 60)
    print(f"Génération de la carte — données Eurostat {YEAR}")
    print("=" * 60)
    print("\nRécupération des données Eurostat…")
    country_totals, country_partners = build_data()
    print(f"\n  {len(country_totals)} pays avec données")
    make_map(country_totals, country_partners, "carte_energie_fossile_europe.html")


if __name__ == "__main__":
    main()
