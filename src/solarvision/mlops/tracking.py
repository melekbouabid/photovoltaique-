"""Suivi d'expériences avec MLflow, en local (base SQLite à la racine du dépôt).

MLflow garde la trace de chaque version : paramètres, métriques, commit, graine, versions des
bibliothèques. S'il n'est pas installé ou s'il échoue, l'enregistrement dans le registre de fichiers
continue : l'échec est renvoyé en clair au lieu d'être masqué.
"""
from __future__ import annotations

import json
from pathlib import Path

from solarvision.config import ROOT

EXPERIMENT = "solarvision_v2"


def tracking_uri() -> str:
    return f"sqlite:///{(ROOT / 'mlflow.db').as_posix()}"


def log_version(name: str, version: str, metrics: dict, training: dict, folder: Path) -> str:
    """Journalise une version de modèle. Renvoie l'identifiant de l'exécution, ou la raison de l'échec."""
    try:
        import mlflow
    except ImportError:
        return "non journalisé : MLflow n'est pas installé"
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        mlflow.set_tracking_uri(tracking_uri())
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name=f"{name}-{version}") as run:
            mlflow.set_tags({"modele": name, "version": version, "scenario": "ex_ante", "technologie": metrics["technologie"],
                             "villes": str(metrics["villes"]), "commit_git": manifest["commit_git"]})
            mlflow.log_params({**{k: str(v) for k, v in training.items()}, "graine": manifest["graine"],
                               "sha256_modele": manifest["sha256"], "sha256_donnees": manifest["donnees"]["sha256_manifeste"],
                               **{f"lib_{k}": v for k, v in manifest["bibliotheques"].items()}})
            mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))})
            for file in ("manifest.json", "metrics.json", "model_card.md"):
                mlflow.log_artifact(str(folder / file))
        return run.info.run_id
    except Exception as err:                               # noqa: BLE001 - le suivi ne doit pas bloquer le registre
        return f"non journalisé : {type(err).__name__} : {str(err)[:120]}"
