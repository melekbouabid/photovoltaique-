"""Accès aux données servies : panel, tableaux de reports/, registre. Rien n'est écrit en dur dans l'API.

Un fichier absent ne fait pas tomber le service : la page concernée dit quelle commande le produit.
"""
from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import pandas as pd
import yaml

from solarvision.config import DATA, REPORTS, load_cities, load_params
from solarvision.mlops import registry

# Tableau -> commande qui le produit (affichée quand le fichier manque).
TABLES = {
    "metrics_wide": "evaluate", "metrics_tidy": "evaluate", "dm_tests": "evaluate", "synthese_ville": "evaluate",
    "coverage": "evaluate", "tech_recommendation": "recommend", "tech_indicators": "recommend", "tech_scores": "recommend",
    "tech_recommender_summary": "recommend", "tech_orientations": "recommend --orientations", "economics_by_city": "economics", "economics_ranking": "economics",
    "economics_tornado": "economics", "forecast_value": "economics", "sensitivity_imputed": "train --sensitivity",
}


class Store:
    """Charge chaque ressource à la première demande et la garde en mémoire."""

    def __init__(self, data: Path = DATA, reports: Path = REPORTS):
        self.data, self.reports = data, reports
        self._tables: dict[str, pd.DataFrame | None] = {}

    @cached_property
    def panel(self) -> pd.DataFrame | None:
        path = self.data / "processed" / "panel_journalier.parquet"
        return pd.read_parquet(path) if path.exists() else None

    @cached_property
    def splits(self) -> dict:
        path = self.data / "processed" / "splits_90_10.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))["villes"] if path.exists() else {}

    @cached_property
    def manifest(self) -> dict:
        path = self.data / "manifest.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

    @cached_property
    def monitoring(self) -> dict:
        path = self.reports / "monitoring" / "summary.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def table(self, name: str) -> pd.DataFrame | None:
        if name not in self._tables:
            path = self.reports / f"{name}.csv"
            self._tables[name] = pd.read_csv(path, dtype={"horizon": str}) if path.exists() else None
        return self._tables[name]

    def missing(self, *names: str) -> list[str]:
        """Messages à afficher pour les tableaux absents."""
        return [f"Tableau « {n} » absent : lancer python -m solarvision.cli {TABLES.get(n, '...')}"
                for n in names if self.table(n) is None]

    def city_frame(self, city: str) -> pd.DataFrame:
        return self.panel[self.panel["ville"] == city].sort_values("date").reset_index(drop=True)

    @property
    def available_cities(self) -> list[str]:
        return [c for c in load_cities() if c in self.splits]

    def cities_table(self) -> list[dict]:
        """Villes disponibles, avec productible par technologie et jours imputés."""
        if self.panel is None:
            return []
        technologies = load_params()["pv"]["technologies"]
        columns = [f"pv_{t}_kwh_kwc" for t in technologies]
        grouped = self.panel.groupby("ville")
        yearly = grouped[columns].sum() / (grouped.size().to_numpy()[:, None] / 365.25)
        imputed = grouped["jour_impute_pvgis"].sum()
        rows = []
        for city in self.available_cities:
            c = load_cities()[city]
            rows.append({**c.model_dump(), "jours_imputes": int(imputed[city]),
                         **{f"productible_{t}": float(yearly.loc[city, col]) for t, col in zip(technologies, columns, strict=True)}})
        return rows

    def production_model(self) -> dict | None:
        """Version en production, après vérification de l'empreinte du fichier."""
        active = registry.current()
        if not active:
            return None
        entry = registry.read_version(active["nom"], active["version"])
        try:
            registry.verify(active["nom"], active["version"])
            integrity = True
        except registry.IntegrityError:
            integrity = False
        return {"nom": active["nom"], "version": active["version"], "promu_le": active["promu_le"],
                "entraine_le": entry["manifest"]["cree_le"], "sha256": entry["manifest"]["sha256"],
                "sha256_verifie": integrity, "donnees": entry["manifest"]["donnees"], "metriques": entry["metrics"],
                "dossier": entry["dossier"], "fichier": entry["manifest"]["fichier_modele"]}
