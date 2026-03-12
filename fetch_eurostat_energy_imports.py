"""
Script de récupération des données Eurostat sur les importations d'énergie fossile
par pays européens.

Sources :
  - nrg_ti_sff : Importations de combustibles fossiles solides (charbon, etc.)
  - nrg_ti_gas : Importations de gaz naturel
  - nrg_ti_oilp : Importations de produits pétroliers
  - nrg_ti_oil  : Importations de pétrole brut

Unité par défaut : TJ (térajoules). Si indisponible, on retente en THS_T ou MIO_M3.
"""

import requests
import pandas as pd
import json

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# Pays membres de l'UE-27 + autres pays européens importants
EU_COUNTRIES = {
    "EU27_2020": "Union européenne (27 pays)",
    "BE": "Belgique",
    "BG": "Bulgarie",
    "CZ": "Tchéquie",
    "DK": "Danemark",
    "DE": "Allemagne",
    "EE": "Estonie",
    "IE": "Irlande",
    "EL": "Grèce",
    "ES": "Espagne",
    "FR": "France",
    "HR": "Croatie",
    "IT": "Italie",
    "CY": "Chypre",
    "LV": "Lettonie",
    "LT": "Lituanie",
    "LU": "Luxembourg",
    "HU": "Hongrie",
    "MT": "Malte",
    "NL": "Pays-Bas",
    "AT": "Autriche",
    "PL": "Pologne",
    "PT": "Portugal",
    "RO": "Roumanie",
    "SI": "Slovénie",
    "SK": "Slovaquie",
    "FI": "Finlande",
    "SE": "Suède",
    "NO": "Norvège",
    "IS": "Islande",
    "UK": "Royaume-Uni",
}

YEARS = ["2019", "2020", "2021", "2022", "2023"]


def fetch_eurostat(dataset_code: str, params: dict) -> dict | None:
    """Appel à l'API Eurostat et renvoie le JSON brut, ou None en cas d'erreur."""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = f"{BASE_URL}/{dataset_code}"
    try:
        resp = requests.get(url, params=params, timeout=60, verify=False)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"  ✗ Erreur lors de la récupération de {dataset_code}: {exc}")
        return None


def parse_eurostat_json(data: dict, energy_type: str) -> list[dict]:
    """
    Extrait les observations d'un JSON Eurostat (format SDMX-JSON 2.0)
    et retourne une liste de dictionnaires plats.
    """
    if not data or "value" not in data:
        return []

    values = data["value"]
    if not values:
        print(f"  ⚠ Aucune valeur trouvée pour {energy_type}")
        return []

    dims = data["id"]           # ordre des dimensions, ex: ["freq","siec","partner","unit","geo","time"]
    sizes = data["size"]        # taille de chaque dimension
    dimension_info = data["dimension"]

    # Construction d'une version inverse (index → label) pour chaque dimension utile
    def idx_to_labels(dim_name: str) -> dict:
        cat = dimension_info[dim_name]["category"]
        return {v: k for k, v in cat["index"].items()}

    geo_labels = dimension_info["geo"]["category"]["label"]
    time_labels = dimension_info["time"]["category"]["label"]
    unit_labels = dimension_info["unit"]["category"]["label"]
    siec_labels = dimension_info["siec"]["category"]["label"]

    geo_idx  = idx_to_labels("geo")
    time_idx = idx_to_labels("time")
    unit_idx = idx_to_labels("unit")
    siec_idx = idx_to_labels("siec")

    # Positions des dimensions dans le vecteur de strides
    dim_pos = {name: i for i, name in enumerate(dims)}

    # Calcul des strides (pour décoder l'index linéaire)
    strides = [1] * len(dims)
    for i in range(len(dims) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    rows = []
    for linear_idx_str, obs_value in values.items():
        linear_idx = int(linear_idx_str)

        # Décomposition en indices par dimension
        indices = []
        remaining = linear_idx
        for stride in strides:
            indices.append(remaining // stride)
            remaining %= stride

        geo_code  = geo_idx.get(indices[dim_pos["geo"]], "?")
        time_code = time_idx.get(indices[dim_pos["time"]], "?")
        unit_code = unit_idx.get(indices[dim_pos["unit"]], "?")
        siec_code = siec_idx.get(indices[dim_pos["siec"]], "?")

        # Filtrer sur les pays/années qui nous intéressent
        if geo_code not in EU_COUNTRIES:
            continue
        if time_code not in YEARS:
            continue

        rows.append({
            "geo_code":    geo_code,
            "pays":        EU_COUNTRIES.get(geo_code, geo_code),
            "annee":       time_code,
            "type_energie": energy_type,
            "siec_code":   siec_code,
            "siec_label":  siec_labels.get(siec_code, siec_code),
            "unite":       unit_code,
            "unite_label": unit_labels.get(unit_code, unit_code),
            "valeur":      obs_value,
        })

    return rows


def fetch_solid_fossil_fuels() -> list[dict]:
    """Importations de combustibles fossiles solides (charbon, coke, lignite…)"""
    print("→ Importations de combustibles fossiles solides (nrg_ti_sff)...")
    # Agrégat principal : C0000X0350-0370 = Total solid fossil fuels
    # Unité préférée : THS_T (milliers de tonnes)
    params = {
        "format":          "JSON",
        "lang":            "EN",
        "freq":            "A",
        "unit":            "THS_T",
        "siec":            "C0000X0350-0370",
        "partner":         "TOTAL",
        "sinceTimePeriod": YEARS[0],
        "untilTimePeriod": YEARS[-1],
    }
    data = fetch_eurostat("nrg_ti_sff", params)
    rows = parse_eurostat_json(data, "Combustibles fossiles solides (charbon)")
    print(f"  → {len(rows)} observations récupérées.")
    return rows


def fetch_natural_gas() -> list[dict]:
    """Importations de gaz naturel (inclut GNL)"""
    print("→ Importations de gaz naturel (nrg_ti_gas)...")
    params = {
        "format":          "JSON",
        "lang":            "EN",
        "freq":            "A",
        "unit":            "TJ_GCV",
        "siec":            "G3000",        # Natural gas (total)
        "partner":         "TOTAL",
        "sinceTimePeriod": YEARS[0],
        "untilTimePeriod": YEARS[-1],
    }
    data = fetch_eurostat("nrg_ti_gas", params)
    rows = parse_eurostat_json(data, "Gaz naturel")
    print(f"  → {len(rows)} observations récupérées.")
    return rows


def fetch_crude_oil() -> list[dict]:
    """Importations de pétrole brut"""
    print("→ Importations de pétrole brut (nrg_ti_oil, O4100_TOT)...")
    params = {
        "format":          "JSON",
        "lang":            "EN",
        "freq":            "A",
        "unit":            "THS_T",
        "siec":            "O4100_TOT",   # Crude oil
        "partner":         "TOTAL",
        "sinceTimePeriod": YEARS[0],
        "untilTimePeriod": YEARS[-1],
    }
    data = fetch_eurostat("nrg_ti_oil", params)
    rows = parse_eurostat_json(data, "Pétrole brut")
    print(f"  → {len(rows)} observations récupérées.")
    return rows


def fetch_oil_products() -> list[dict]:
    """Importations de pétrole et produits pétroliers (hors biocarburants)"""
    print("→ Importations pétrole + produits pétroliers (nrg_ti_oil, O4000XBIO)...")
    params = {
        "format":          "JSON",
        "lang":            "EN",
        "freq":            "A",
        "unit":            "THS_T",
        "siec":            "O4000XBIO",   # Oil and petroleum products (excl. biofuels)
        "partner":         "TOTAL",
        "sinceTimePeriod": YEARS[0],
        "untilTimePeriod": YEARS[-1],
    }
    data = fetch_eurostat("nrg_ti_oil", params)
    rows = parse_eurostat_json(data, "Pétrole et produits pétroliers")
    print(f"  → {len(rows)} observations récupérées.")
    return rows


def main():
    print("=" * 60)
    print("Récupération des données Eurostat — Importations d'énergie fossile")
    print("=" * 60)

    all_rows = []
    all_rows.extend(fetch_solid_fossil_fuels())
    all_rows.extend(fetch_natural_gas())
    all_rows.extend(fetch_crude_oil())
    all_rows.extend(fetch_oil_products())

    if not all_rows:
        print("\n✗ Aucune donnée collectée. Vérifiez la connexion ou les paramètres API.")
        return

    df = pd.DataFrame(all_rows)

    # Réorganisation des colonnes
    col_order = [
        "pays", "geo_code", "annee",
        "type_energie", "siec_code", "siec_label",
        "valeur", "unite", "unite_label",
    ]
    df = df[col_order].sort_values(["pays", "annee", "type_energie"])

    output_path = "eurostat_fossil_energy_imports.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"\n✓ Fichier créé : {output_path}")
    print(f"  {len(df)} lignes × {len(df.columns)} colonnes")
    print(f"\nAperçu des données :")
    print(df.head(15).to_string(index=False))
    print(f"\nPays couverts : {sorted(df['geo_code'].unique())}")
    print(f"Années : {sorted(df['annee'].unique())}")
    print(f"Types d'énergie : {df['type_energie'].unique()}")


if __name__ == "__main__":
    main()
