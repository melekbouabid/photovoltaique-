"""Modèle statistique du protocole multi-villes : régression harmonique à erreurs AR(1).

C'est l'« ARIMA à termes de Fourier » retenu par l'étude détaillée de Tunis : ARIMA(1,0,0) avec
deux harmoniques annuelles. Le cycle annuel est déterministe (termes de Fourier), d = 0 car la
série est stationnaire autour de ce cycle, et un AR(1) suffit à décrire ce qui reste.
L'identification complète (ACF, PACF, grille BIC, auto-ARIMA, diagnostics) reste dans le notebook historique.
"""
from __future__ import annotations

import warnings

import numpy as np
from statsmodels.tsa.arima.model import ARIMA

from solarvision.models.protocol import horizons, refit_blocks

Z_95 = 1.959964          # quantile de la loi normale pour un intervalle à 95 %


def fit_ar1_regression(values: np.ndarray, exog: np.ndarray) -> dict[str, np.ndarray | float]:
    """Estime constante, coefficients des termes de Fourier, coefficient AR(1) et variance des innovations."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                    # avertissements de convergence sans conséquence ici
        result = ARIMA(values, exog=exog, order=(1, 0, 0), trend="c").fit()
    params = np.asarray(result.params)
    return {"const": float(params[0]), "beta": params[1:1 + exog.shape[1]], "phi": float(params[-2]),
            "sigma2": float(params[-1]), "aic": float(result.aic), "bic": float(result.bic)}


def forecast_ar1_regression(values: np.ndarray, exog: np.ndarray, origin_positions: np.ndarray,
                            missing_mask: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Prévisions à J+1...J+7 depuis chaque origine, paramètres réestimés à chaque tranche de 30 jours.

    Pour un AR(1), la prévision a une forme exacte : niveau saisonnier du jour visé, plus l'écart
    observé à l'origine multiplié par phi puissance h. L'écart-type de l'erreur à l'horizon h vaut
    sigma * racine((1 - phi^(2h)) / (1 - phi^2)).
    `missing_mask` écarte des jours de l'estimation (analyse de sensibilité aux jours imputés).
    """
    h = horizons()
    values = np.asarray(values, float)
    predicted = np.empty((len(origin_positions), len(h)))
    lower, upper = np.empty_like(predicted), np.empty_like(predicted)
    fits = []
    for start, stop in refit_blocks(len(origin_positions)):
        last = origin_positions[start]                     # le modèle ne voit que le passé de la première origine de la tranche
        train = values[: last + 1].copy()
        if missing_mask is not None:
            train[missing_mask[: last + 1]] = np.nan       # le filtre de Kalman accepte des jours manquants
        fit = fit_ar1_regression(train, exog[: last + 1])
        fits.append(fit)
        level = fit["const"] + exog @ fit["beta"]
        pos = origin_positions[start:stop]
        gap = values[pos] - level[pos]                     # écart à la saison, observé le jour de l'origine
        predicted[start:stop] = level[pos[:, None] + h[None, :]] + gap[:, None] * fit["phi"] ** h[None, :]
        spread = Z_95 * np.sqrt(fit["sigma2"] * (1 - fit["phi"] ** (2 * h)) / (1 - fit["phi"] ** 2))
        lower[start:stop], upper[start:stop] = predicted[start:stop] - spread, predicted[start:stop] + spread
    # Une production ne peut pas être négative.
    return {"predicted": np.clip(predicted, 0, None), "lower": np.clip(lower, 0, None), "upper": upper,
            "phi": np.array([f["phi"] for f in fits]), "sigma2": np.array([f["sigma2"] for f in fits])}
