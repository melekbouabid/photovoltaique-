"""Peut-on deviner la technologie la plus fiable d'une ville à partir de son climat ?

Un arbre de décision peu profond est entraîné sur les caractéristiques des villes, et jugé en
« leave-one-city-out » : chaque ville est prédite par un modèle qui ne l'a jamais vue. Il est comparé
à la règle la plus simple possible : toujours proposer la technologie la plus souvent gagnante.
Avec 30 villes, le résultat est indicatif ; il est rapporté tel quel, même s'il est décevant.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from solarvision.config import load_cities, load_params
from solarvision.recommender.reliability import load_reliability_config


def city_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Caractéristiques climatiques d'une ville, calculées sur l'apprentissage seulement."""
    reference = f"pv_{load_params()['pv']['reference_technology']}_kwh_kwc"
    cities, rows = load_cities(), []
    for city, frame in panel.groupby("ville"):
        train = frame.iloc[: int(len(frame) * load_params()["split"]["train_fraction"])]
        rows.append({
            "ville": city, "pays": cities[city].pays, "lat": cities[city].lat, "lon": cities[city].lon,
            "altitude": cities[city].altitude,
            "irradiation_moyenne_kwh_m2": train["expost_irr_poa_kwh_m2"].mean(),
            "temperature_moyenne_c": train["expost_t2m_moy_c"].mean(),
            "temperature_max_c": train["expost_t2m_max_c"].quantile(0.99),
            "nebulosite_moyenne_pct": train["expost_nebulosite_pct"].mean(),
            "variabilite_journaliere": (train[reference] - train[f"normale_{load_params()['pv']['reference_technology']}"]).std(),
        })
    return pd.DataFrame(rows)


def leave_one_city_out(features: pd.DataFrame, recommendation: pd.DataFrame, reports: Path) -> dict[str, pd.DataFrame]:
    """Valide l'arbre de décision ville par ville et le compare à la règle de la classe majoritaire."""
    from sklearn.tree import DecisionTreeClassifier, export_text

    cfg, seed = load_reliability_config()["recommender"], load_params()["seed"]
    data = features.merge(recommendation[["ville", "technologie_recommandee", "ex_aequo"]], on="ville")
    x, y = data[cfg["features"]].to_numpy(float), data["technologie_recommandee"].to_numpy()
    predicted, baseline = [], []
    for i in range(len(data)):
        keep = np.arange(len(data)) != i
        tree = DecisionTreeClassifier(max_depth=cfg["tree_max_depth"], random_state=seed).fit(x[keep], y[keep])
        predicted.append(tree.predict(x[i:i + 1])[0])
        labels, counts = np.unique(y[keep], return_counts=True)
        baseline.append(labels[counts.argmax()])          # la technologie la plus fréquente parmi les autres villes
    detail = data[["ville", "pays", "technologie_recommandee", "ex_aequo"]].assign(
        prediction_arbre=predicted, prediction_majoritaire=baseline)
    detail["arbre_correct"] = detail["prediction_arbre"] == detail["technologie_recommandee"]
    detail["majoritaire_correct"] = detail["prediction_majoritaire"] == detail["technologie_recommandee"]
    summary = pd.DataFrame([{
        "villes": len(detail), "classes": int(len(np.unique(y))),
        "exactitude_arbre_pct": 100 * detail["arbre_correct"].mean(),
        "exactitude_majoritaire_pct": 100 * detail["majoritaire_correct"].mean(),
        "exactitude_arbre_hors_ex_aequo_pct": 100 * detail.loc[~detail["ex_aequo"], "arbre_correct"].mean()
        if (~detail["ex_aequo"]).any() else float("nan"),
        "villes_ex_aequo": int(detail["ex_aequo"].sum()),
    }])
    full_tree = DecisionTreeClassifier(max_depth=cfg["tree_max_depth"], random_state=seed).fit(x, y)
    reports.mkdir(parents=True, exist_ok=True)
    detail.to_csv(reports / "tech_recommender_loco.csv", index=False)
    summary.to_csv(reports / "tech_recommender_summary.csv", index=False, float_format="%.4g")
    features.to_csv(reports / "city_features.csv", index=False, float_format="%.6g")
    (reports / "tech_recommender_tree.txt").write_text(export_text(full_tree, feature_names=cfg["features"]), encoding="utf-8")
    return {"detail": detail, "summary": summary}
