"""Modèles d'apprentissage automatique : XGBoost en prévision directe et Prophet."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from solarvision.config import load_params
from solarvision.features.panel import LAGGED_WEATHER
from solarvision.models.protocol import horizons, refit_blocks

# Réglages volontairement sobres : peu de signal à apprendre au-delà de la saison, donc arbres peu profonds
# et apprentissage lent pour éviter le surajustement.
XGB_PARAMS = {"n_estimators": 300, "max_depth": 3, "learning_rate": 0.03, "subsample": 0.8, "colsample_bytree": 0.8,
              "min_child_weight": 10, "tree_method": "hist", "n_jobs": 1, "verbosity": 0}
CALENDAR = ["fourier_sin_1", "fourier_cos_1", "fourier_sin_2", "fourier_cos_2", "irr_extraterrestre_kwh_m2",
            "duree_jour_astro_h", "hauteur_soleil_midi_deg", "jour_annee"]


def direct_design(frame: pd.DataFrame, technology: str, horizon: int, ex_post: bool = False) -> tuple[pd.DataFrame, pd.Series]:
    """Variables et cible pour prévoir le jour t depuis l'origine t - h.

    Chaque ligne t reçoit :
    - ce qui est observé à l'origine : production des jours t-h et t-h-6, moyenne des 7 derniers jours,
      écart à la normale, météo du jour de l'origine. Dans le panel, la ligne t-h+1 contient déjà ces
      valeurs sous forme de retards d'un jour : on la décale donc de h-1 lignes ;
    - ce qui est connu à l'avance pour le jour t : calendrier, astronomie, normale saisonnière.
    La cible est l'écart à la normale : le modèle part de la climatologie et n'apprend que la correction.
    Avec ex_post=True, la météo observée le jour t est ajoutée (borne optimiste, jamais opérationnelle).
    """
    pv, normal = f"pv_{technology}_kwh_kwc", f"normale_{technology}"
    window = load_params()["features"]["rolling_window_days"]
    at_origin = [f"{pv}_lag1", f"{pv}_lag7", f"{pv}_moy{window}_passe", *[f"{c}_lag1" for c in LAGGED_WEATHER]]
    design = frame[at_origin].shift(horizon - 1).add_suffix("_origine")
    design["ecart_normale_origine"] = (frame[pv] - frame[normal]).shift(horizon)
    design = design.join(frame[[normal, *CALENDAR]])
    if ex_post:
        excluded = {f"expost_{c}" for c in load_params()["features"]["ex_post_excluded"]}
        design = design.join(frame[[c for c in frame.columns if c.startswith("expost_") and c not in excluded]])
    return design, frame[pv] - frame[normal]


def xgboost_direct(frame: pd.DataFrame, technology: str, origin_positions: np.ndarray, ex_post: bool = False,
                   exclude: np.ndarray | None = None) -> np.ndarray:
    """Un modèle par horizon, réajusté à chaque tranche de 30 jours sur tout le passé disponible.

    `exclude` marque des jours à retirer de l'apprentissage (analyse de sensibilité aux jours imputés).
    """
    from xgboost import XGBRegressor

    seed = load_params()["seed"]
    normal = frame[f"normale_{technology}"].to_numpy()
    predicted = np.empty((len(origin_positions), len(horizons())))
    for j, h in enumerate(horizons()):
        design, target = direct_design(frame, technology, int(h), ex_post)
        usable = design.notna().all(axis=1).to_numpy() & target.notna().to_numpy()
        if exclude is not None:
            # Un jour imputé est écarté s'il est la cible ou s'il sert d'origine à la ligne.
            usable &= ~exclude & ~np.roll(exclude, int(h))
        x, y = design.to_numpy(), target.to_numpy()
        for start, stop in refit_blocks(len(origin_positions)):
            last = origin_positions[start]
            train = usable.copy()
            train[last + 1:] = False                       # la cible doit être connue à la première origine de la tranche
            model = XGBRegressor(**XGB_PARAMS, random_state=seed).fit(x[train], y[train])
            rows = origin_positions[start:stop] + h
            predicted[start:stop, j] = normal[rows] + model.predict(x[rows])
    return np.clip(predicted, 0, None)


def prophet_forecast(dates: pd.DatetimeIndex, values: np.ndarray, origin_positions: np.ndarray) -> dict[str, np.ndarray]:
    """Prophet (tendance et saisonnalité annuelle), réajusté à chaque tranche de 30 jours.

    Prophet n'utilise pas les dernières observations : entre deux réajustements, sa prévision pour
    une date donnée est la même quelle que soit l'origine. C'est une climatologie lissée avec tendance.
    """
    from prophet import Prophet

    for name in ("prophet", "cmdstanpy"):
        logging.getLogger(name).setLevel(logging.ERROR)    # sinon un message par ajustement
    h = horizons()
    out = {k: np.empty((len(origin_positions), len(h))) for k in ("predicted", "lower", "upper")}
    for start, stop in refit_blocks(len(origin_positions)):
        last = origin_positions[start]
        model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False,
                        interval_width=0.95, uncertainty_samples=200)
        model.fit(pd.DataFrame({"ds": dates[: last + 1], "y": values[: last + 1]}))
        first, end = last + 1, origin_positions[stop - 1] + int(h.max())
        forecast = model.predict(pd.DataFrame({"ds": dates[first: end + 1]}))
        rows = origin_positions[start:stop, None] + h[None, :] - first
        for key, column in (("predicted", "yhat"), ("lower", "yhat_lower"), ("upper", "yhat_upper")):
            out[key][start:stop] = forecast[column].to_numpy()[rows]
    return {k: np.clip(v, 0, None) if k != "upper" else v for k, v in out.items()}
