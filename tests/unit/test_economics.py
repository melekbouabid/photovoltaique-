"""Formules financières vérifiées sur des cas calculés à la main."""
from __future__ import annotations

import numpy as np
import pytest

from solarvision.economics import finance, simulate

FLOWS = np.full((1, 5), 300.0)        # 300 par an pendant 5 ans, pour un investissement de 1 000


def test_npv_matches_the_annuity_formula():
    # 300 x (1 - 1,1^-5) / 0,1 - 1000 = 137,236
    assert finance.npv(1000.0, FLOWS, 0.10)[0] == pytest.approx(137.236, abs=1e-3)
    assert finance.npv(1000.0, FLOWS, 0.0)[0] == pytest.approx(500.0)


def test_payback_is_interpolated_within_the_year():
    assert finance.payback_years(1000.0, FLOWS)[0] == pytest.approx(1000 / 300)
    assert finance.payback_years(300.0, FLOWS)[0] == pytest.approx(1.0)
    assert np.isinf(finance.payback_years(2000.0, FLOWS)[0])               # jamais remboursé en 5 ans


def test_irr_cancels_the_npv():
    rate = finance.irr(1000.0, FLOWS)
    assert rate[0] == pytest.approx(0.15238, abs=1e-4)                     # valeur connue pour ces flux
    assert finance.npv(1000.0, FLOWS, rate)[0] == pytest.approx(0.0, abs=1e-6)
    assert np.isnan(finance.irr(1e9, FLOWS, low=0.0)[0])                   # pas de racine positive


def test_lcoe_without_discounting_is_total_cost_over_total_energy():
    # (1000 + 5 x 20) / (5 x 1000 kWh) = 0,22 par kWh
    assert finance.lcoe(1000.0, np.full((1, 5), 20.0), np.full((1, 5), 1000.0), 0.0)[0] == pytest.approx(0.22)


def test_cash_flows_follow_the_stated_model():
    p = {k: np.array([v]) for k, v in {"degradation": 0.01, "inflation": 0.02, "self_consumption": 0.4, "retail_price": 0.2,
                                        "export_price": 0.1, "capex_per_kwp": 1000.0, "capex_multiplier": 1.1, "om_share": 0.02}.items()}
    flows = simulate.cash_flows(np.array([1500.0]), p, peak_kwp=2.0, years=3)
    assert flows["capex"][0] == pytest.approx(2200.0)
    assert flows["production"][0, 0] == pytest.approx(3000.0)
    assert flows["production"][0, 2] == pytest.approx(3000.0 * 0.99 ** 2)
    assert flows["savings"][0, 0] == pytest.approx(3000 * 0.4 * 0.2)
    assert flows["export"][0, 1] == pytest.approx(3000 * 0.99 * 0.6 * 0.1 * 1.02)
    assert flows["costs"][0, 0] == pytest.approx(44.0)
    assert flows["net"][0, 0] == pytest.approx(240 + 180 - 44)


def test_every_economic_parameter_is_flagged_for_verification():
    cfg = simulate.load_economics_config()
    assert cfg["status"] == "TODO_VERIFY"
    for country in cfg["countries"].values():
        assert country["source_a_confirmer"]
        for key, value in country.items():
            if isinstance(value, list):
                assert len(value) == 3 and value[0] <= value[1] <= value[2], key
