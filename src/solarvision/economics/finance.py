"""Formules financières, écrites pour des tableaux (une ligne par tirage, une colonne par année).

Convention : l'investissement est payé à l'année 0 ; les flux des années 1 à N sont reçus en fin d'année.
"""
from __future__ import annotations

import numpy as np


def discount_factors(rate: np.ndarray, years: int) -> np.ndarray:
    """Facteurs 1 / (1 + r)^t pour t = 1..N. `rate` peut être un nombre ou un vecteur de tirages."""
    rate = np.atleast_1d(np.asarray(rate, float))
    return (1.0 + rate[:, None]) ** -np.arange(1, years + 1)[None, :]


def npv(capex: np.ndarray, cash_flows: np.ndarray, rate: np.ndarray) -> np.ndarray:
    """Valeur actuelle nette : somme des flux actualisés, moins l'investissement."""
    cash_flows = np.atleast_2d(cash_flows)
    return (cash_flows * discount_factors(rate, cash_flows.shape[1])).sum(axis=1) - np.atleast_1d(capex)


def payback_years(capex: np.ndarray, cash_flows: np.ndarray) -> np.ndarray:
    """Temps de retour simple (non actualisé), interpolé dans l'année ; infini si l'investissement n'est jamais remboursé."""
    cash_flows = np.atleast_2d(cash_flows)
    capex = np.atleast_1d(np.asarray(capex, float))
    cumulative = np.cumsum(cash_flows, axis=1)
    reached = cumulative >= capex[:, None]
    year = reached.argmax(axis=1)                          # indice de la première année où le cumul couvre l'investissement
    before = np.where(year > 0, cumulative[np.arange(len(year)), np.maximum(year - 1, 0)], 0.0)
    flow = cash_flows[np.arange(len(year)), year]
    with np.errstate(divide="ignore", invalid="ignore"):
        out = year + (capex - before) / flow
    return np.where(reached.any(axis=1), out, np.inf)


def irr(capex: np.ndarray, cash_flows: np.ndarray, low: float = -0.99, high: float = 1.0, iterations: int = 60) -> np.ndarray:
    """Taux de rentabilité interne par dichotomie : le taux qui annule la valeur actuelle nette.

    Les flux sont positifs après l'investissement, donc la VAN décroît avec le taux et la racine est unique.
    NaN si aucune racine n'existe dans l'intervalle exploré.
    """
    cash_flows = np.atleast_2d(cash_flows)
    capex = np.atleast_1d(np.asarray(capex, float))
    lo, hi = np.full(len(capex), low), np.full(len(capex), high)
    valid = (npv(capex, cash_flows, lo) > 0) & (npv(capex, cash_flows, hi) < 0)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        positive = npv(capex, cash_flows, mid) > 0
        lo, hi = np.where(positive, mid, lo), np.where(positive, hi, mid)
    return np.where(valid, (lo + hi) / 2, np.nan)


def lcoe(capex: np.ndarray, operating_costs: np.ndarray, production_kwh: np.ndarray, rate: np.ndarray) -> np.ndarray:
    """Coût actualisé de l'énergie : coûts actualisés sur toute la durée de vie, divisés par l'énergie actualisée."""
    operating_costs, production_kwh = np.atleast_2d(operating_costs), np.atleast_2d(production_kwh)
    factors = discount_factors(rate, production_kwh.shape[1])
    return (np.atleast_1d(capex) + (operating_costs * factors).sum(axis=1)) / (production_kwh * factors).sum(axis=1)
