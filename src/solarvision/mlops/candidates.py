"""Candidats à la production : calcul de leurs métriques, enregistrement, puis promotion selon la règle."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from solarvision.config import ROOT, load_params
from solarvision.features.panel import load_splits
from solarvision.mlops import registry, tracking
from solarvision.models import statistical
from solarvision.models.train import FOURIER, data_dir, load_city, reports_dir

DESCRIPTIONS = {
    "lstm_global": "LSTM à une couche entraîné sur toutes les villes à la fois. Chaque ville est ramenée à sa propre "
                   "normale saisonnière ; un vecteur appris par ville adapte la réponse au climat local. "
                   "Intervalles conformes calibrés sur la dernière année de l'apprentissage.",
    "arima_fourier": "Régression harmonique à erreurs AR(1), une par ville : cycle annuel décrit par deux harmoniques "
                     "de Fourier, écart à la saison prolongé par un AR(1). Modèle interprétable, intervalles analytiques.",
}


def model_metrics(metrics_wide: pd.DataFrame, model: str, splits: dict) -> dict:
    """Erreur du modèle et de la climatologie sur les mêmes villes et les mêmes dates de test."""
    reference = load_params()["pv"]["reference_technology"]
    m = metrics_wide[(metrics_wide["technologie"] == reference) & (metrics_wide["horizon"] == "tous")]
    by_city = m.pivot_table(index="ville", columns="modele", values="RMSE")[[model, "climatologie"]].dropna()
    first = next(iter(splits.values()))
    return {
        "technologie": reference, "villes": int(len(by_city)),
        "dates_test": f"{first['test_debut']} / {first['test_fin']}",
        "rmse_moyen": float(by_city[model].mean()), "rmse_climatologie_moyen": float(by_city["climatologie"].mean()),
        "gain_moyen_pct": float(100 * (1 - by_city[model].mean() / by_city["climatologie"].mean())),
        "villes_gagnees": int((by_city[model] < by_city["climatologie"]).sum()),
        "rmse_par_ville": {c: float(v) for c, v in by_city[model].items()},
    }


def arima_artifact(fast: bool, out: Path) -> Path:
    """Paramètres de la régression AR(1) de chaque ville, estimés sur l'apprentissage : c'est tout le « modèle »."""
    root, splits = data_dir(fast), load_splits(data_dir(fast))
    reference, params = load_params()["pv"]["reference_technology"], {}
    for city, split in splits.items():
        frame = load_city(city, root).frame
        fit = statistical.fit_ar1_regression(frame[f"pv_{reference}_kwh_kwc"].to_numpy()[: split["n_train"]],
                                             frame[FOURIER].to_numpy()[: split["n_train"]])
        params[city] = {"const": fit["const"], "beta": [float(b) for b in fit["beta"]], "phi": fit["phi"], "sigma2": fit["sigma2"]}
    out.write_text(json.dumps({"technologie": reference, "termes_fourier": FOURIER, "villes": params}, indent=2), encoding="utf-8")
    return out


def register_and_promote(fast: bool = False) -> list[dict]:
    """Enregistre les candidats, puis tente de promouvoir le meilleur. Un refus est un résultat, pas une erreur."""
    reports, splits = reports_dir(fast), load_splits(data_dir(fast))
    wide = pd.read_csv(reports / "metrics_wide.csv", dtype={"horizon": str})
    deep_cfg = load_params()["deep"]
    artifacts = {
        "lstm_global": (reports / "forecasts_deep" / "_lstm_global.pt",
                        {"fenetre_jours": deep_cfg["window_days"], "taille_cachee": deep_cfg["hidden_size"],
                         "dropout": deep_cfg["dropout"], "epoques_max": deep_cfg["fast_max_epochs"] if fast else deep_cfg["max_epochs"],
                         "validation": "dernière année de l'apprentissage, arrêt anticipé"}),
        "arima_fourier": (arima_artifact(fast, reports / "arima_fourier_params.json"),
                          {"ordre": "ARIMA(1,0,0)", "harmoniques_annuelles": 2, "estimation": "maximum de vraisemblance, apprentissage seul"}),
    }
    results = []
    for name, (artifact, training) in artifacts.items():
        if not artifact.exists() or name not in set(wide["modele"]):
            results.append({"nom": name, "statut": "absent : modèle non entraîné"})
            continue
        metrics = model_metrics(wide, name, splits)
        folder = registry.register(name, artifact, metrics, DESCRIPTIONS[name], {**training, "mode": "rapide (3 villes)" if fast else "complet"})
        version = folder.name
        if not fast:
            # La fiche du modèle est aussi rangée avec la documentation, où on la cherche d'abord.
            cards = ROOT / "docs" / "model_cards"
            cards.mkdir(parents=True, exist_ok=True)
            shutil.copy2(folder / "model_card.md", cards / f"{name}-{version}.md")
        results.append({"nom": name, "version": version, "rmse_moyen": metrics["rmse_moyen"],
                        "rmse_climatologie_moyen": metrics["rmse_climatologie_moyen"], "statut": "enregistré",
                        "mlflow": tracking.log_version(name, version, metrics, training, folder)})
    # Le meilleur candidat est proposé d'abord ; la règle décide.
    for result in sorted((r for r in results if "version" in r), key=lambda r: r["rmse_moyen"]):
        try:
            registry.promote(result["nom"], result["version"])
            result["statut"] = "promu en production"
        except registry.PromotionRefused as refusal:
            result["statut"] = f"promotion refusée : {refusal}"
    return results
