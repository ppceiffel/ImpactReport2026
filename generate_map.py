"""
Génération d'une carte HTML interactive des importations d'énergie fossile
en Europe (données Eurostat, 2019-2023).

Toutes les valeurs sont converties en ktoe (kilotonnes d'équivalent pétrole)
pour permettre la comparaison inter-types.

Facteurs de conversion (source : Eurostat / AIE) :
  - Charbon (THS_T)  → ktoe : × 0.474
  - Pétrole (THS_T)  → ktoe : × 1.020
  - Gaz (TJ_GCV)     → ktoe : × 0.02388
"""

import json
import os
import pandas as pd
import folium
from folium import plugins
import branca.colormap as cm
import requests, urllib3
urllib3.disable_warnings()

# ── Facteurs de conversion vers ktoe ─────────────────────────────────────────
CONV = {
    "Combustibles fossiles solides (charbon)": 0.474,   # THS_T → ktoe
    "Pétrole brut":                             1.020,   # THS_T → ktoe
    "Pétrole et produits pétroliers":           1.020,   # THS_T → ktoe
    "Gaz naturel":                              0.02388, # TJ_GCV → ktoe
}

ENERGY_COLORS = {
    "Charbon":          "#4a4a4a",
    "Gaz naturel":      "#e86c1f",
    "Pétrole brut":     "#8b0000",
    "Prod. pétroliers": "#d62728",
}

# ── Correspondance codes Eurostat (ISO-2 modifié) → ISO-3 ────────────────────
ISO2_TO_ISO3 = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "CY": "CYP",
    "CZ": "CZE", "DE": "DEU", "DK": "DNK", "EE": "EST",
    "EL": "GRC", "ES": "ESP", "FI": "FIN", "FR": "FRA",
    "HR": "HRV", "HU": "HUN", "IE": "IRL", "IS": "ISL",
    "IT": "ITA", "LT": "LTU", "LU": "LUX", "LV": "LVA",
    "MT": "MLT", "NL": "NLD", "NO": "NOR", "PL": "POL",
    "PT": "PRT", "RO": "ROU", "SE": "SWE", "SI": "SVN",
    "SK": "SVK", "UK": "GBR",
}

TYPE_SHORT = {
    "Combustibles fossiles solides (charbon)": "Charbon",
    "Gaz naturel":                             "Gaz naturel",
    "Pétrole brut":                            "Pétrole brut",
    "Pétrole et produits pétroliers":          "Prod. pétroliers",
}


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Exclure l'agrégat EU27
    df = df[df["geo_code"] != "EU27_2020"].copy()
    # Ajouter ISO-3 et conversion ktoe
    df["iso3"] = df["geo_code"].map(ISO2_TO_ISO3)
    df["type_court"] = df["type_energie"].map(TYPE_SHORT)
    df["ktoe"] = df.apply(
        lambda r: r["valeur"] * CONV.get(r["type_energie"], 1), axis=1
    )
    return df


def build_summary(df: pd.DataFrame) -> dict:
    """
    Construit un dict {iso3: {annee: {type_court: ktoe}}}
    pour toutes les années disponibles.
    """
    summary = {}
    for _, row in df.iterrows():
        iso3 = row["iso3"]
        if pd.isna(iso3):
            continue
        year = str(row["annee"])
        typ  = row["type_court"]
        if iso3 not in summary:
            summary[iso3] = {}
        if year not in summary[iso3]:
            summary[iso3][year] = {}
        summary[iso3][year][typ] = round(row["ktoe"], 1)
    return summary


def total_by_country_year(df: pd.DataFrame) -> dict:
    """Retourne {(iso3, annee): total_ktoe}"""
    grp = (
        df.dropna(subset=["iso3"])
          .groupby(["iso3", "annee"])["ktoe"]
          .sum()
          .reset_index()
    )
    return {(r["iso3"], str(r["annee"])): round(r["ktoe"], 1)
            for _, r in grp.iterrows()}


def get_geojson() -> dict:
    """Télécharge le GeoJSON monde (Natural Earth via un CDN fiable)."""
    url = (
        "https://raw.githubusercontent.com/python-visualization/folium"
        "/main/examples/data/world-countries.json"
    )
    resp = requests.get(url, verify=False, timeout=30)
    resp.raise_for_status()
    return resp.json()


def filter_europe(geo: dict, iso3_set: set) -> dict:
    """Conserve uniquement les pays présents dans nos données."""
    features = [
        f for f in geo["features"]
        if f["id"] in iso3_set
    ]
    return {"type": "FeatureCollection", "features": features}


def make_map(df: pd.DataFrame, out_path: str):
    summary   = build_summary(df)
    totals    = total_by_country_year(df)
    years     = sorted(df["annee"].astype(str).unique())
    iso3_set  = set(df["iso3"].dropna().unique())
    pays_name = (
        df[["iso3", "pays"]]
        .dropna(subset=["iso3"])
        .drop_duplicates("iso3")
        .set_index("iso3")["pays"]
        .to_dict()
    )

    print("Téléchargement du GeoJSON…")
    geo_world  = get_geojson()
    geo_europe = filter_europe(geo_world, iso3_set)

    # ── Palettes de couleur par année ────────────────────────────────────────
    default_year = "2023"
    year_totals = {
        iso3: totals.get((iso3, default_year), 0)
        for iso3 in iso3_set
    }
    max_val = max(year_totals.values()) if year_totals else 1

    colormap = cm.LinearColormap(
        colors=["#fff7bc", "#fec44f", "#d95f0e", "#7f0000"],
        vmin=0,
        vmax=max_val,
        caption="Importations totales d'énergie fossile (ktoe)",
    )

    # ── Carte de base ────────────────────────────────────────────────────────
    m = folium.Map(
        location=[54, 15],
        zoom_start=4,
        tiles="CartoDB positron",
        min_zoom=3,
        max_zoom=8,
    )

    # ── Données JS embarquées ────────────────────────────────────────────────
    js_summary = json.dumps(summary, ensure_ascii=False)
    js_pays    = json.dumps(pays_name, ensure_ascii=False)
    js_years   = json.dumps(years)
    js_geo     = json.dumps(geo_europe, ensure_ascii=False)
    js_colormap_colors = '["#fff7bc","#fec44f","#d95f0e","#7f0000"]'

    # ── Couche choropleth initiale (2023) ────────────────────────────────────
    def style_fn(feature):
        iso3 = feature["id"]
        val  = year_totals.get(iso3, 0)
        return {
            "fillColor":   colormap(val) if val else "#cccccc",
            "color":       "white",
            "weight":      1.5,
            "fillOpacity": 0.8,
        }

    choropleth = folium.GeoJson(
        geo_europe,
        name="pays",
        style_function=style_fn,
        highlight_function=lambda x: {
            "weight": 3,
            "color": "#333",
            "fillOpacity": 0.95,
        },
    ).add_to(m)

    colormap.add_to(m)

    # ── HTML complet avec sélecteur d'année et tooltips riches ───────────────
    html_extra = f"""
<style>
  #panel {{
    position: fixed;
    top: 10px; right: 10px;
    z-index: 9999;
    background: rgba(255,255,255,0.96);
    border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,.25);
    font-family: 'Segoe UI', sans-serif;
    min-width: 220px;
  }}
  #panel h3 {{ margin: 0 0 10px; font-size: 13px; color: #333; }}
  .year-btn {{
    display: inline-block;
    margin: 2px 3px;
    padding: 5px 10px;
    border-radius: 5px;
    border: 1.5px solid #aaa;
    cursor: pointer;
    font-size: 12px;
    background: #f5f5f5;
    transition: all .15s;
  }}
  .year-btn.active {{
    background: #d95f0e;
    color: white;
    border-color: #d95f0e;
  }}
  #tooltip-box {{
    position: fixed;
    z-index: 9998;
    background: rgba(255,255,255,0.97);
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: 0 2px 16px rgba(0,0,0,.3);
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
    pointer-events: none;
    display: none;
    min-width: 230px;
    max-width: 280px;
  }}
  #tooltip-box h4 {{ margin: 0 0 8px; font-size: 14px; color: #222; }}
  .bar-row {{ margin: 4px 0; }}
  .bar-label {{ color: #555; margin-bottom: 2px; }}
  .bar-outer {{
    background: #eee; border-radius: 4px; height: 14px; width: 100%;
    overflow: hidden;
  }}
  .bar-inner {{ height: 14px; border-radius: 4px; }}
  .bar-val {{ font-size: 10px; color: #666; margin-top: 1px; text-align: right; }}
  .total-line {{
    margin-top: 8px; padding-top: 6px;
    border-top: 1px solid #ddd;
    font-weight: bold; color: #333;
  }}
  #legend-title {{
    font-size: 11px; color: #555; margin-top: 10px; border-top: 1px solid #ddd; padding-top:8px;
  }}
  #source-note {{
    position: fixed;
    bottom: 30px; left: 10px;
    z-index: 9999;
    font-family: 'Segoe UI', sans-serif;
    font-size: 10px;
    color: #666;
    background: rgba(255,255,255,0.85);
    padding: 4px 8px;
    border-radius: 4px;
  }}
</style>

<div id="panel">
  <h3>🛢️ Importations d'énergie fossile</h3>
  <div id="year-btns"></div>
  <div id="legend-title">
    Source : Eurostat (nrg_ti_sff, nrg_ti_gas, nrg_ti_oil)<br>
    Unité : ktoe — kilotonnes d'éq. pétrole
  </div>
</div>

<div id="tooltip-box"></div>
<div id="source-note">© Eurostat 2026 — Données 2019-2023</div>

<script>
(function() {{

  const SUMMARY  = {js_summary};
  const PAYS     = {js_pays};
  const YEARS    = {js_years};
  const GEO      = {js_geo};
  const COLORS   = {{
    "Charbon":          "#4a4a4a",
    "Gaz naturel":      "#e86c1f",
    "Pétrole brut":     "#8b0000",
    "Prod. pétroliers": "#c0392b"
  }};
  const TYPE_ORDER = ["Charbon","Gaz naturel","Pétrole brut","Prod. pétroliers"];
  const COLOR_STEPS = {js_colormap_colors};

  let currentYear = "2023";

  // ── Calcule totaux par pays/année ────────────────────────────────────────
  function getTotal(iso3, year) {{
    if (!SUMMARY[iso3] || !SUMMARY[iso3][year]) return 0;
    return Object.values(SUMMARY[iso3][year]).reduce((a,b) => a+b, 0);
  }}

  // ── Colormap linéaire ────────────────────────────────────────────────────
  function lerp(a, b, t) {{
    return a.map((v,i) => Math.round(v + (b[i]-v)*t));
  }}
  function hexToRgb(h) {{
    const r = parseInt(h.slice(1,3),16),
          g = parseInt(h.slice(3,5),16),
          b = parseInt(h.slice(5,7),16);
    return [r,g,b];
  }}
  function rgbToHex([r,g,b]) {{
    return '#' + [r,g,b].map(x => x.toString(16).padStart(2,'0')).join('');
  }}

  function getColor(val, maxVal) {{
    if (!val || maxVal === 0) return "#cccccc";
    const stops = COLOR_STEPS.map(hexToRgb);
    const t = Math.min(val / maxVal, 1) * (stops.length - 1);
    const i = Math.floor(t);
    const frac = t - i;
    const rgb = lerp(stops[Math.min(i, stops.length-2)],
                     stops[Math.min(i+1, stops.length-1)], frac);
    return rgbToHex(rgb);
  }}

  // ── Attente du chargement de la carte Folium ─────────────────────────────
  function waitForMap(cb) {{
    const id = setInterval(() => {{
      if (typeof window._map !== 'undefined') {{
        clearInterval(id);
        cb(window._map);
      }}
    }}, 100);
  }}

  function initMap(map) {{
    // Boutons années
    const btnDiv = document.getElementById('year-btns');
    YEARS.forEach(y => {{
      const btn = document.createElement('span');
      btn.className = 'year-btn' + (y === currentYear ? ' active' : '');
      btn.textContent = y;
      btn.onclick = () => {{
        currentYear = y;
        document.querySelectorAll('.year-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        updateLayer();
      }};
      btnDiv.appendChild(btn);
    }});

    // Trouver la couche GeoJSON de Folium
    let geoLayer = null;
    map.eachLayer(l => {{
      if (l.feature !== undefined || (l.getLayers && l.getLayers().length > 0 && l.getLayers()[0].feature)) {{
        geoLayer = l;
      }}
    }});

    // Recalcule maxVal pour l'année courante
    function getMaxVal(year) {{
      return Math.max(...Object.keys(SUMMARY).map(iso3 => getTotal(iso3, year)), 1);
    }}

    function updateLayer() {{
      const maxVal = getMaxVal(currentYear);
      if (!geoLayer) return;
      geoLayer.eachLayer(layer => {{
        const iso3 = layer.feature && layer.feature.id;
        if (!iso3) return;
        const val = getTotal(iso3, currentYear);
        layer.setStyle({{
          fillColor:   getColor(val, maxVal),
          color:       "white",
          weight:      1.5,
          fillOpacity: 0.85,
        }});
      }});
      // Mise à jour légende
      updateLegend(maxVal);
    }}

    function updateLegend(maxVal) {{
      const legEl = document.querySelector('.legend');
      if (!legEl) return;
      // On laisse folium gérer la légende
    }}

    // ── Tooltip personnalisé ─────────────────────────────────────────────
    const tooltip = document.getElementById('tooltip-box');

    function showTooltip(e, iso3) {{
      const data = SUMMARY[iso3] && SUMMARY[iso3][currentYear];
      const nom  = PAYS[iso3] || iso3;
      if (!data) {{
        tooltip.style.display = 'none';
        return;
      }}
      const total = Object.values(data).reduce((a,b) => a+b, 0);
      const maxBar = Math.max(...Object.values(data), 1);

      let rows = TYPE_ORDER.map(t => {{
        if (!data[t]) return '';
        const pct = Math.round((data[t] / maxBar) * 100);
        const col = COLORS[t] || '#888';
        return `
          <div class="bar-row">
            <div class="bar-label">${{t}}</div>
            <div class="bar-outer">
              <div class="bar-inner" style="width:${{pct}}%;background:${{col}}"></div>
            </div>
            <div class="bar-val">${{data[t].toLocaleString('fr-FR')}} ktoe</div>
          </div>`;
      }}).join('');

      tooltip.innerHTML = `
        <h4>🏳️ ${{nom}} — ${{currentYear}}</h4>
        ${{rows}}
        <div class="total-line">Total : ${{Math.round(total).toLocaleString('fr-FR')}} ktoe</div>`;
      tooltip.style.display = 'block';
      positionTooltip(e);
    }}

    function positionTooltip(e) {{
      const x = e.originalEvent ? e.originalEvent.clientX : e.clientX;
      const y = e.originalEvent ? e.originalEvent.clientY : e.clientY;
      const w = tooltip.offsetWidth  || 260;
      const h = tooltip.offsetHeight || 200;
      const vw = window.innerWidth, vh = window.innerHeight;
      tooltip.style.left = (x + 16 + w > vw ? x - w - 12 : x + 16) + 'px';
      tooltip.style.top  = (y + 16 + h > vh ? y - h - 10 : y + 16) + 'px';
    }}

    if (geoLayer) {{
      geoLayer.eachLayer(layer => {{
        layer.on('mouseover', e => showTooltip(e, layer.feature && layer.feature.id));
        layer.on('mousemove', e => positionTooltip(e));
        layer.on('mouseout',  () => {{ tooltip.style.display = 'none'; }});
      }});
    }}

    document.addEventListener('mousemove', e => {{
      if (tooltip.style.display !== 'none') {{
        tooltip.style.left = (e.clientX + 16) + 'px';
        tooltip.style.top  = (e.clientY + 16) + 'px';
      }}
    }});

    updateLayer();
  }}

  // Récupère la carte Folium depuis l'objet global créé par folium
  function findLeafletMap() {{
    // Folium stocke la carte dans une var globale nommée map_XXXX
    const keys = Object.keys(window).filter(k => k.startsWith('map_'));
    if (keys.length > 0) {{
      window._map = window[keys[0]];
      return true;
    }}
    return false;
  }}

  document.addEventListener('DOMContentLoaded', () => {{
    const check = setInterval(() => {{
      if (findLeafletMap()) {{
        clearInterval(check);
        initMap(window._map);
      }}
    }}, 150);
  }});
}})();
</script>
"""

    # Injection dans la carte
    m.get_root().html.add_child(folium.Element(html_extra))

    m.save(out_path)
    print(f"✓ Carte créée : {out_path}")


def main():
    csv_path = "eurostat_fossil_energy_imports.csv"
    out_path = "carte_energie_fossile_europe.html"

    print("Lecture des données…")
    df = load_data(csv_path)

    print(f"  {len(df)} lignes chargées — {df['geo_code'].nunique()} pays")
    print(f"  Années : {sorted(df['annee'].astype(str).unique())}")

    make_map(df, out_path)


if __name__ == "__main__":
    main()
