"""Chargement et validation de la configuration (configs/*.yaml).

Le code ne contient aucune valeur de réglage : villes, graine, découpage et seuils sont lus ici.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

# Racine du dépôt déduite de l'emplacement de ce fichier : aucun chemin absolu n'est écrit.
ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
MODELS = ROOT / "models"
LEGACY_RAW = DATA / "brut"          # cache de la v1, lu sans jamais être modifié


class City(BaseModel):
    """Une ville de l'étude, telle que décrite dans configs/cities.yaml."""

    id: str
    nom: str
    pays: str
    code_pays: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    altitude: float
    fuseau: str
    zone_climatique: str

    @field_validator("id")
    @classmethod
    def _ascii_id(cls, v: str) -> str:
        # L'identifiant sert de nom de dossier et de fichier : ASCII minuscule uniquement.
        if not (v.isascii() and v.islower() and v.replace("_", "").isalnum()):
            raise ValueError(f"identifiant de ville invalide : {v!r}")
        return v


def _read_yaml(name: str) -> dict[str, Any]:
    with open(CONFIGS / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def load_cities() -> dict[str, City]:
    """Villes indexées par identifiant, dans l'ordre du fichier."""
    cities = [City(**c) for c in _read_yaml("cities.yaml")["cities"]]
    ids = [c.id for c in cities]
    if len(ids) != len(set(ids)):
        raise ValueError("identifiants de villes en double dans configs/cities.yaml")
    return {c.id: c for c in cities}


@lru_cache
def load_params() -> dict[str, Any]:
    """Paramètres de l'étude (graine, découpage, seuils, protocole)."""
    return _read_yaml("params.yaml")


def split_index(n: int) -> int:
    """Indice de coupure du découpage chronologique 90/10 : les n_train premiers jours servent à l'apprentissage."""
    return int(n * load_params()["split"]["train_fraction"])


def select_cities(fast: bool = False, only: list[str] | None = None) -> list[City]:
    """Villes à traiter : toutes, le sous-ensemble rapide, ou une liste explicite."""
    cities = load_cities()
    if only:
        unknown = [c for c in only if c not in cities]
        if unknown:
            raise KeyError(f"villes inconnues : {unknown}")
        return [cities[c] for c in only]
    if fast:
        return [cities[c] for c in load_params()["fast_cities"]]
    return list(cities.values())
