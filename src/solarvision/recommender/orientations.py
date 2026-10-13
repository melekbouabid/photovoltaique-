"""Analyse secondaire : que change l'orientation pour la technologie recommandée d'une ville ?

Trois cas, simulés par PVGIS (moyennes annuelles, outil PVcalc) pour 1 kWc :
- **sud** : plein sud, à la pente optimale du site (c'est l'installation de toute l'étude) ;
- **est-ouest** : deux demi-installations à faible pente, l'une vers l'est, l'autre vers l'ouest
  (toiture à deux pans ou toiture plate), dont on moyenne la production ;
- **optimale** : pente et azimut optimisés ensemble par PVGIS.
Les réponses sont mises en cache comme le reste de la collecte.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from solarvision.config import City, load_cities, load_params
from solarvision.data import ingest
from solarvision.recommender.reliability import load_reliability_config


def _pvcalc(city: City, technology: str, name: str, extra: dict) -> dict:
    """Appel PVcalc mis en cache : une orientation, une technologie, une ville."""
    path = ingest.RAW / "pvgis" / city.id / f"orientation_{technology}_{name}.json"
    if not path.exists():
        pv = load_params()["pv"]
        content = ingest.fetch("pvgis", f"{ingest.PVGIS_URL}/PVcalc", {
            "lat": city.lat, "lon": city.lon, "peakpower": pv["peak_power_kwp"], "loss": pv["system_loss_pct"],
            "pvtechchoice": technology, "outputformat": "json", **extra})
        json.loads(content)
        ingest.atomic_write(path, content)
    return json.loads(path.read_text(encoding="utf-8"))


def _yield(response: dict) -> float:
    return float(response["outputs"]["totals"]["fixed"]["E_y"])


def city_orientations(city: City, technology: str) -> dict:
    cfg = load_reliability_config()["orientations"]
    slope = ingest.optimal_slope(city)
    south = _pvcalc(city, technology, "sud", {"angle": slope, "aspect": 0})
    east = _pvcalc(city, technology, "est", {"angle": cfg["east_west_tilt_deg"], "aspect": -90})
    west = _pvcalc(city, technology, "ouest", {"angle": cfg["east_west_tilt_deg"], "aspect": 90})
    best = _pvcalc(city, technology, "optimale", {"optimalangles": 1})
    mount = best["inputs"]["mounting_system"]["fixed"]
    y_south, y_ew, y_best = _yield(south), (_yield(east) + _yield(west)) / 2, _yield(best)
    return {"ville": city.id, "pays": city.pays, "technologie": technology, "pente_sud_deg": slope,
            "rendement_sud_kwh_kwc": y_south, "pente_est_ouest_deg": cfg["east_west_tilt_deg"],
            "rendement_est_ouest_kwh_kwc": y_ew, "ecart_est_ouest_pct": 100 * (y_ew / y_south - 1),
            "pente_optimale_deg": float(mount["slope"]["value"]), "azimut_optimal_deg": float(mount["azimuth"]["value"]),
            "rendement_optimal_kwh_kwc": y_best, "gain_optimal_pct": 100 * (y_best / y_south - 1)}


def run(recommendation: pd.DataFrame, reports: Path) -> pd.DataFrame:
    """Calcule les trois orientations pour la technologie recommandée de chaque ville."""
    cities = load_cities()
    tasks = [(cities[r.ville], r.technologie_recommandee) for r in recommendation.itertuples()]
    rows, failures = [], []

    def work(task: tuple[City, str]) -> None:
        try:
            rows.append(city_orientations(*task))
        except Exception as err:                           # noqa: BLE001 - une ville en échec est signalée, pas inventée
            failures.append({"ville": task[0].id, "erreur": str(err)[:200]})

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(work, tasks))
    table = pd.DataFrame(rows).sort_values(["pays", "ville"]).reset_index(drop=True)
    table.to_csv(reports / "tech_orientations.csv", index=False, float_format="%.6g")
    if failures:
        pd.DataFrame(failures).to_csv(reports / "tech_orientations_failures.csv", index=False)
    return table
