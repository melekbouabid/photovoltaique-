"""Vérifie les coordonnées et l'altitude de configs/cities.yaml contre une source indépendante.

Une erreur de latitude ou de longitude fausse toute une ville : chaque entrée est comparée au
géocodage d'Open-Meteo (base GeoNames). Le script écrit reports/cities_verification.csv et
s'arrête en erreur si une ville est à plus de 15 km de sa référence.

Usage : python scripts/verify_cities.py
"""
from __future__ import annotations

import math
import sys
import time

import pandas as pd
import requests

from solarvision.config import REPORTS, load_cities

GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
MAX_DISTANCE_KM = 15          # un centre-ville et sa référence GeoNames diffèrent de quelques kilomètres au plus
MAX_ALTITUDE_GAP_M = 60       # au-delà, l'altitude du fichier est à corriger
# Nom local de la ville quand il diffère du nom français utilisé dans le projet.
LOCAL_NAMES = {"seville": "Sevilla", "barcelone": "Barcelona", "valence": "Valencia", "malaga": "Málaga",
               "saragosse": "Zaragoza", "murcie": "Murcia", "grenade": "Granada", "palma": "Palma",
               "gabes": "Gabès", "medenine": "Medenine"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def main() -> int:
    rows = []
    for city in load_cities().values():
        r = requests.get(GEOCODING, params={"name": LOCAL_NAMES.get(city.id, city.nom), "count": 20, "language": "fr"},
                         timeout=60)
        r.raise_for_status()
        # Plusieurs lieux portent le même nom : on garde le lieu habité (code PPL*) le plus peuplé du bon pays.
        hits = [h for h in r.json().get("results", [])
                if h.get("country_code") == city.code_pays and str(h.get("feature_code", "")).startswith("PPL")]
        if not hits:
            rows.append({"ville": city.id, "statut": "introuvable"})
            continue
        ref = max(hits, key=lambda h: h.get("population") or 0)
        distance = haversine_km(city.lat, city.lon, ref["latitude"], ref["longitude"])
        gap = city.altitude - ref.get("elevation", float("nan"))
        ok = distance <= MAX_DISTANCE_KM and abs(gap) <= MAX_ALTITUDE_GAP_M and ref.get("timezone") == city.fuseau
        rows.append({"ville": city.id, "lat": city.lat, "lon": city.lon, "altitude": city.altitude,
                     "ref_nom": ref["name"], "ref_lat": ref["latitude"], "ref_lon": ref["longitude"],
                     "ref_altitude": ref.get("elevation"), "ref_fuseau": ref.get("timezone"),
                     "ref_population": ref.get("population"), "distance_km": round(distance, 2),
                     "ecart_altitude_m": round(gap, 1), "statut": "ok" if ok else "à corriger"})
        time.sleep(0.3)
    table = pd.DataFrame(rows)
    REPORTS.mkdir(exist_ok=True)
    table.to_csv(REPORTS / "cities_verification.csv", index=False)
    print(table[["ville", "ref_nom", "distance_km", "altitude", "ref_altitude", "ref_fuseau", "statut"]].to_string(index=False))
    return int((table["statut"] != "ok").any())


if __name__ == "__main__":
    sys.exit(main())
