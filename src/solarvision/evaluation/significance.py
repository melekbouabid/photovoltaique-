"""Tests de significativité : Diebold-Mariano (correction HLN), correction de Holm, bootstrap par blocs.

Chaque test écrit ici dit ses hypothèses, sa fonction de perte et son sens, parce qu'un test dont on
ne connaît ni la famille ni la direction ne se laisse pas interpréter.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class DMResult:
    statistic: float          # positive : le modèle fait mieux que la référence
    p_one_sided: float        # H1 : la perte moyenne du modèle est inférieure à celle de la référence
    p_two_sided: float        # H1 : les pertes moyennes diffèrent
    n: int
    mean_loss_difference: float
    kernel: str               # « rectangulaire » ou « bartlett » (repli si la variance estimée est négative)


def _loss(error: np.ndarray, loss: str) -> np.ndarray:
    if loss == "squared":
        return error ** 2
    if loss == "absolute":
        return np.abs(error)
    raise ValueError(f"fonction de perte inconnue : {loss}")


def diebold_mariano(error_reference: np.ndarray, error_model: np.ndarray, horizon: int, loss: str = "squared") -> DMResult:
    """Test de Diebold-Mariano avec la correction de Harvey, Leybourne et Newbold (1997).

    - H0 : les deux prévisions ont la même perte moyenne.
    - Différence de perte : d_t = L(erreur de la référence) - L(erreur du modèle).
    - Une prévision à l'horizon h a des erreurs autocorrélées jusqu'à l'ordre h - 1 : la variance de
      long terme de d utilise donc h - 1 autocovariances (noyau rectangulaire, comme l'article d'origine).
    - Correction HLN pour les petits échantillons, loi de Student à T - 1 degrés de liberté.
    """
    d = _loss(np.asarray(error_reference, float), loss) - _loss(np.asarray(error_model, float), loss)
    d = d[~np.isnan(d)]
    n = d.size
    if n < 2 * horizon + 2:
        return DMResult(float("nan"), float("nan"), float("nan"), n, float("nan"), "aucun")
    mean, centered = d.mean(), d - d.mean()
    gamma = [float(centered[k:] @ centered[: n - k]) / n for k in range(horizon)]
    variance, kernel = gamma[0] + 2 * sum(gamma[1:]), "rectangulaire"
    if variance <= 0:
        # Le noyau rectangulaire peut donner une variance négative : le noyau de Bartlett ne le peut pas.
        variance = gamma[0] + 2 * sum((1 - k / horizon) * gamma[k] for k in range(1, horizon))
        kernel = "bartlett"
    if variance <= 0:
        return DMResult(float("nan"), float("nan"), float("nan"), n, float(mean), "aucun")
    statistic = mean / np.sqrt(variance / n)
    statistic *= np.sqrt((n + 1 - 2 * horizon + horizon * (horizon - 1) / n) / n)      # correction HLN
    p_two = float(2 * stats.t.sf(abs(statistic), df=n - 1))
    return DMResult(float(statistic), float(stats.t.sf(statistic, df=n - 1)), p_two, n, float(mean), kernel)


def holm(p_values: np.ndarray) -> np.ndarray:
    """p-values ajustées par la méthode de Holm, pour une famille de tests.

    Du plus petit au plus grand, la k-ième p-value est multipliée par (m - k + 1), puis la suite est
    rendue croissante. Les valeurs manquantes sortent de la famille et restent manquantes.
    """
    p = np.asarray(p_values, float)
    adjusted = np.full(p.shape, np.nan)
    valid = np.flatnonzero(~np.isnan(p))
    if valid.size == 0:
        return adjusted
    order = valid[np.argsort(p[valid])]
    m = order.size
    running = np.maximum.accumulate((m - np.arange(m)) * p[order])
    adjusted[order] = np.minimum(running, 1.0)
    return adjusted


def block_bootstrap_mean(values: np.ndarray, block: int, replicates: int, seed: int,
                         level: float = 0.95) -> tuple[float, float, float]:
    """Moyenne et intervalle de confiance par bootstrap à blocs glissants.

    Les erreurs de prévision sont autocorrélées : tirer des jours isolés sous-estimerait
    l'incertitude. On tire donc des blocs de jours consécutifs.
    """
    values = np.asarray(values, float)
    values = values[~np.isnan(values)]
    n = values.size
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    block = max(1, min(block, n))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - block + 1, size=(replicates, int(np.ceil(n / block))))
    index = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(replicates, -1)[:, :n]
    means = values[index].mean(axis=1)
    alpha = (1 - level) / 2
    return float(values.mean()), float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))
