"""Registre de modèles sur fichiers : versions, promotion réglée par une règle, retour arrière, intégrité.

Chaque version vit dans models/registry/<nom>/<version>/ avec :
- le modèle lui-même ;
- manifest.json : empreinte SHA256, données utilisées, commit Git, graine, versions des bibliothèques ;
- metrics.json : erreurs sur l'échantillon de test, comparées à la climatologie ;
- model_card.md : fiche lisible, générée, avec ses limites et ses risques.
models/registry/current.json désigne la version en production et garde l'historique des promotions.
"""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from datetime import datetime
from importlib import metadata
from pathlib import Path

from solarvision.config import DATA, MODELS, ROOT, load_params

REGISTRY = MODELS / "registry"
CURRENT = REGISTRY / "current.json"
LIBRARIES = ["numpy", "pandas", "torch", "statsmodels", "xgboost", "prophet", "scikit-learn"]


def use(folder: Path) -> None:
    """Bascule le registre vers un autre dossier (mode rapide, tests) : la production n'est pas touchée."""
    global REGISTRY, CURRENT
    REGISTRY, CURRENT = folder, folder / "current.json"


class IntegrityError(RuntimeError):
    """Le fichier du modèle ne correspond plus à l'empreinte enregistrée."""


class PromotionRefused(RuntimeError):
    """La règle de promotion n'est pas satisfaite."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "inconnu"


def _library_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for name in LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "absent"
    return versions


def versions(name: str) -> list[str]:
    folder = REGISTRY / name
    found = [p.name for p in folder.iterdir() if p.is_dir()] if folder.exists() else []
    return sorted(found, key=lambda v: tuple(int(x) for x in v.split(".")))


def next_version(name: str) -> str:
    """Version sémantique : 1.0.0 pour la première, puis le numéro mineur augmente à chaque réentraînement."""
    existing = versions(name)
    if not existing:
        return "1.0.0"
    major, minor, _ = (int(x) for x in existing[-1].split("."))
    return f"{major}.{minor + 1}.0"


def register(name: str, artifact: Path, metrics: dict, description: str, training: dict) -> Path:
    """Enregistre une nouvelle version : copie du modèle, manifeste, métriques et fiche."""
    version = next_version(name)
    folder = REGISTRY / name / version
    folder.mkdir(parents=True)
    model_file = folder / f"model{artifact.suffix}"
    shutil.copy2(artifact, model_file)
    data_manifest = DATA / "manifest.yaml"
    manifest = {
        "nom": name, "version": version, "cree_le": datetime.now().isoformat(timespec="seconds"),
        "fichier_modele": model_file.name, "sha256": sha256_file(model_file), "octets": model_file.stat().st_size,
        "description": description, "entrainement": training,
        "donnees": {"manifeste": "data/manifest.yaml",
                    "sha256_manifeste": sha256_file(data_manifest) if data_manifest.exists() else "absent"},
        "commit_git": _git_commit(), "graine": load_params()["seed"], "bibliotheques": _library_versions(),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "model_card.md").write_text(model_card(manifest, metrics), encoding="utf-8")
    return folder


def read_version(name: str, version: str) -> dict:
    folder = REGISTRY / name / version
    return {"dossier": folder, "manifest": json.loads((folder / "manifest.json").read_text(encoding="utf-8")),
            "metrics": json.loads((folder / "metrics.json").read_text(encoding="utf-8"))}


def verify(name: str, version: str) -> Path:
    """Recalcule l'empreinte du modèle avant de le charger : un fichier altéré n'est jamais servi."""
    entry = read_version(name, version)
    model_file = entry["dossier"] / entry["manifest"]["fichier_modele"]
    if sha256_file(model_file) != entry["manifest"]["sha256"]:
        raise IntegrityError(f"{name} {version} : empreinte SHA256 différente de celle du manifeste")
    return model_file


def current() -> dict | None:
    return json.loads(CURRENT.read_text(encoding="utf-8")) if CURRENT.exists() else None


def check_promotion(name: str, version: str) -> list[str]:
    """Règle de promotion. Renvoie la liste des raisons de refus (vide si la promotion est permise).

    Un modèle n'est promu que s'il fait mieux que la climatologie ET mieux que la version en
    production, sur les mêmes dates de test.
    """
    candidate = read_version(name, version)["metrics"]
    refusals = []
    if not candidate["rmse_moyen"] < candidate["rmse_climatologie_moyen"]:
        refusals.append(f"ne bat pas la climatologie ({candidate['rmse_moyen']:.4f} contre {candidate['rmse_climatologie_moyen']:.4f})")
    active = current()
    if active:
        production = read_version(active["nom"], active["version"])["metrics"]
        if production["dates_test"] != candidate["dates_test"] or production["villes"] != candidate["villes"]:
            refusals.append("dates de test ou villes différentes de celles de la version en production : comparaison impossible")
        elif not candidate["rmse_moyen"] < production["rmse_moyen"]:
            refusals.append(f"ne bat pas la version en production {active['nom']} {active['version']} "
                            f"({candidate['rmse_moyen']:.4f} contre {production['rmse_moyen']:.4f})")
    return refusals


def promote(name: str, version: str) -> dict:
    """Passe une version en production si la règle le permet ; l'ancienne reste dans l'historique."""
    verify(name, version)
    refusals = check_promotion(name, version)
    if refusals:
        raise PromotionRefused(f"{name} {version} : " + " ; ".join(refusals))
    active = current()
    history = (active or {}).get("historique", [])
    if active:
        history = [*history, {k: active[k] for k in ("nom", "version", "promu_le")}]
    pointer = {"nom": name, "version": version, "promu_le": datetime.now().isoformat(timespec="seconds"),
               "regle": "bat la climatologie et la version précédente sur les mêmes dates de test", "historique": history}
    REGISTRY.mkdir(parents=True, exist_ok=True)
    CURRENT.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8")
    return pointer


def rollback() -> dict:
    """Revient à la version précédemment en production."""
    active = current()
    if not active or not active.get("historique"):
        raise RuntimeError("aucune version précédente vers laquelle revenir")
    *history, previous = active["historique"]
    verify(previous["nom"], previous["version"])
    pointer = {**previous, "retour_arriere_le": datetime.now().isoformat(timespec="seconds"),
               "remplace": {"nom": active["nom"], "version": active["version"]}, "historique": history}
    CURRENT.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8")
    return pointer


def list_models() -> list[dict]:
    """Toutes les versions enregistrées, avec leur statut."""
    active = current() or {}
    rows = []
    for folder in sorted(p for p in REGISTRY.iterdir() if p.is_dir()) if REGISTRY.exists() else []:
        for version in versions(folder.name):
            entry = read_version(folder.name, version)
            rows.append({"nom": folder.name, "version": version, "cree_le": entry["manifest"]["cree_le"],
                         "rmse_moyen": entry["metrics"]["rmse_moyen"],
                         "rmse_climatologie_moyen": entry["metrics"]["rmse_climatologie_moyen"],
                         "villes_ou_il_bat_la_climatologie": entry["metrics"]["villes_gagnees"],
                         "sha256": entry["manifest"]["sha256"],
                         "statut": "production" if (active.get("nom"), active.get("version")) == (folder.name, version) else "enregistré"})
    return rows


def model_card(manifest: dict, metrics: dict) -> str:
    """Fiche du modèle, générée à chaque version à partir du manifeste et des métriques."""
    libs = ", ".join(f"{k} {v}" for k, v in manifest["bibliotheques"].items())
    training = "\n".join(f"| {k} | {v} |" for k, v in manifest["entrainement"].items())
    return f"""# Fiche du modèle {manifest['nom']} — version {manifest['version']}

Fiche générée automatiquement le {manifest['cree_le']}.

## Description

{manifest['description']}

## Usage prévu

Prévoir la production journalière d'une installation photovoltaïque de 1 kWc, de J+1 à J+7, pour les villes de l'étude.
Scénario **ex ante** : le modèle n'utilise aucune information postérieure à la date d'émission.

## Entraînement

| Élément | Valeur |
|---|---|
{training}
| Graine | {manifest['graine']} |
| Commit Git | `{manifest['commit_git']}` |
| Bibliothèques | {libs} |

## Données

Voir `{manifest['donnees']['manifeste']}` (empreinte `{manifest['donnees']['sha256_manifeste'][:16]}…`).
Production simulée par PVGIS 5.3 à partir d'images satellitaires ; météo ERA5 ; contrôle par NASA POWER.

## Résultats sur l'échantillon de test

| Mesure | Valeur |
|---|---|
| Villes | {metrics['villes']} |
| Dates de test | {metrics['dates_test']} |
| RMSE moyen du modèle (kWh/kWc) | {metrics['rmse_moyen']:.4f} |
| RMSE moyen de la climatologie (kWh/kWc) | {metrics['rmse_climatologie_moyen']:.4f} |
| Gain moyen sur la climatologie | {metrics['gain_moyen_pct']:.2f} % |
| Villes où le modèle bat la climatologie | {metrics['villes_gagnees']} sur {metrics['villes']} |

## Limites et risques

- **Données simulées.** La production vient d'une simulation, pas de mesures d'installations réelles : pannes, ombrages et salissures ne sont pas représentés.
- **Faible prévisibilité.** Au-delà de deux jours, la production suit surtout la saison : le gain sur la climatologie est faible et peut être nul.
- **Pas de météo à venir.** Le modèle ne connaît pas la prévision météo ; l'associer à une prévision météo réduirait nettement l'erreur.
- **Validité limitée aux villes et à la période de l'étude** (2005-2023). Une ville nouvelle demande un réentraînement.
- **Pas de réentraînement automatique.** Une dérive des données est signalée par le suivi, la décision de réentraîner reste humaine.
- **Intégrité.** L'empreinte SHA256 du fichier est vérifiée à chaque chargement : `{manifest['sha256'][:16]}…`
"""
