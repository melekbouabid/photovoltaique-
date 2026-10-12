"""Métriques et tests statistiques, vérifiés contre des valeurs calculées à la main ou par un outil indépendant."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from solarvision.evaluation.metrics import compute_metrics, interval_coverage
from solarvision.evaluation.significance import block_bootstrap_mean, diebold_mariano, holm


def _autocorrelated_errors() -> tuple[np.ndarray, np.ndarray]:
    """Jeu d'erreurs déterministe : le même que celui soumis à forecast::dm.test (R) pour obtenir R_REFERENCE."""
    rng = np.random.default_rng(7)
    n = 300
    common = rng.normal(0, 1, n + 6)
    ma = common[6:] + 0.6 * common[5:-1] + 0.3 * common[4:-2]
    return ma + rng.normal(0, 0.5, n), 0.9 * ma + rng.normal(0, 0.5, n)


# (horizon, perte) -> (statistique, p bilatérale, p unilatérale) renvoyées par forecast::dm.test de R 4.6.0.
R_REFERENCE = {
    (1, "squared"): (3.6398381259, 0.0003213397, 0.0001606699),
    (1, "absolute"): (2.8721390801, 0.0043686116, 0.0021843058),
    (3, "squared"): (3.0098182155, 0.0028367409, 0.0014183704),
    (3, "absolute"): (2.5335289767, 0.0118028262, 0.0059014131),
    (7, "squared"): (3.0395488262, 0.0025787942, 0.0012893971),
    (7, "absolute"): (2.6301321918, 0.0089770757, 0.0044885378),
}


@pytest.mark.parametrize(("horizon", "loss"), list(R_REFERENCE))
def test_diebold_mariano_matches_r(horizon, loss):
    e_ref, e_mod = _autocorrelated_errors()
    result = diebold_mariano(e_ref, e_mod, horizon, loss)
    statistic, p_two, p_one = R_REFERENCE[(horizon, loss)]
    assert result.statistic == pytest.approx(statistic, abs=1e-8)
    assert result.p_two_sided == pytest.approx(p_two, abs=1e-8)
    assert result.p_one_sided == pytest.approx(p_one, abs=1e-8)


def test_diebold_mariano_at_horizon_one_is_a_student_test():
    # À l'horizon 1, la correction HLN ramène le test à un test de Student sur les différences de perte.
    e_ref, e_mod = _autocorrelated_errors()
    expected = stats.ttest_1samp(e_ref ** 2 - e_mod ** 2, 0.0)
    result = diebold_mariano(e_ref, e_mod, 1, "squared")
    assert result.statistic == pytest.approx(expected.statistic, rel=1e-10)
    assert result.p_two_sided == pytest.approx(expected.pvalue, rel=1e-10)


def test_diebold_mariano_sign_and_symmetry():
    e_ref, e_mod = _autocorrelated_errors()
    forward, backward = diebold_mariano(e_ref, e_mod, 3), diebold_mariano(e_mod, e_ref, 3)
    assert forward.statistic > 0                           # le modèle a les plus petites erreurs
    assert backward.statistic == pytest.approx(-forward.statistic)
    assert forward.p_one_sided + backward.p_one_sided == pytest.approx(1.0)
    assert np.isnan(diebold_mariano(e_ref[:5], e_mod[:5], 7).statistic)      # trop peu d'observations


def test_holm_matches_a_hand_computed_example():
    # Triées : 0,005 x 4 = 0,02 ; 0,01 x 3 = 0,03 ; 0,03 x 2 = 0,06 ; 0,04 x 1 = 0,04 remonté à 0,06.
    np.testing.assert_allclose(holm([0.01, 0.04, 0.03, 0.005]), [0.03, 0.06, 0.06, 0.02])
    np.testing.assert_allclose(holm([0.5, 0.9]), [1.0, 1.0])
    assert np.isnan(holm([np.nan, 0.01])[0]) and holm([np.nan, 0.01])[1] == pytest.approx(0.01)


def test_holm_does_not_give_identical_values_to_distinct_models():
    # Garde-fou contre une famille mal définie : des p-values distinctes et faibles restent distinctes.
    adjusted = holm([0.001, 0.004, 0.02])
    assert len(set(np.round(adjusted, 12))) == 3


def test_metrics_on_a_hand_computed_example():
    m = compute_metrics(np.array([2.0, 4.0, 4.0]), np.array([1.0, 4.0, 6.0]))
    assert m["MSE"] == pytest.approx(5 / 3)
    assert m["RMSE"] == pytest.approx(np.sqrt(5 / 3))
    assert m["MAE"] == pytest.approx(1.0)
    assert m["MAPE"] == pytest.approx(100 * (0.5 + 0 + 0.5) / 3)
    assert m["WAPE"] == pytest.approx(100 * 3 / 10)
    assert interval_coverage(np.array([1.0, 2.0, 3.0, 4.0]), np.array([0.0, 2.5, 2.0, 0.0]), np.array([2.0, 3.0, 4.0, 3.0])) == 50.0


def test_block_bootstrap_interval_contains_the_mean_and_widens_with_dependence():
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 1, 2000)
    persistent = np.convolve(noise, np.ones(20) / np.sqrt(20), mode="same")     # même variance, forte dépendance
    mean, low, high = block_bootstrap_mean(noise, block=30, replicates=400, seed=3)
    assert low < mean < high
    _, low_p, high_p = block_bootstrap_mean(persistent, block=30, replicates=400, seed=3)
    assert (high_p - low_p) > 2 * (high - low)
