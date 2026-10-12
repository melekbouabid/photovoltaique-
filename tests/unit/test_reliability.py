"""Score de fiabilité des technologies : normalisation, sens des critères, front de Pareto."""
from __future__ import annotations

import pandas as pd
import pytest

from solarvision.recommender import reliability

CFG = reliability.load_reliability_config()
WEIGHTS = {k: v["weight"] for k, v in CFG["criteria"].items()}


def _criteria(rows: list[dict]) -> pd.DataFrame:
    base = {"pays": "Testland", "previsibilite": 25.0, "stabilite": 0.5, "sensibilite_temperature": 0.5,
            "faible_irradiation": 1.0, "rendement_annuel": 1500.0}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_weights_sum_to_one_and_every_criterion_has_a_direction():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
    assert set(WEIGHTS) == set(reliability.CRITERIA)
    assert all(v["better"] in ("lower", "higher") for v in CFG["criteria"].values())


def test_a_technology_better_on_every_criterion_gets_the_top_score():
    table = _criteria([
        {"ville": "a", "technologie": "X", "previsibilite": 20, "stabilite": 0.2, "sensibilite_temperature": 0.3,
         "faible_irradiation": 1.1, "rendement_annuel": 1700},
        {"ville": "a", "technologie": "Y", "previsibilite": 30, "stabilite": 0.8, "sensibilite_temperature": 0.6,
         "faible_irradiation": 0.9, "rendement_annuel": 1400}])
    scores = reliability.scores(table, WEIGHTS, CFG)
    assert scores.iloc[0] == pytest.approx(1.0) and scores.iloc[1] == pytest.approx(0.0)
    assert reliability.pareto_front(table, CFG) == ["X"]


def test_lower_is_better_criteria_are_reversed():
    # Seule l'erreur de prévision diffère : la technologie qui se prévoit le mieux doit avoir le meilleur score.
    table = _criteria([{"ville": "a", "technologie": "X", "previsibilite": 20}, {"ville": "a", "technologie": "Y", "previsibilite": 30}])
    scores = reliability.scores(table, WEIGHTS, CFG)
    assert scores.iloc[0] > scores.iloc[1]


def test_pareto_front_keeps_both_when_each_wins_somewhere():
    table = _criteria([{"ville": "a", "technologie": "X", "rendement_annuel": 1700, "previsibilite": 30},
                       {"ville": "a", "technologie": "Y", "rendement_annuel": 1400, "previsibilite": 20}])
    assert sorted(reliability.pareto_front(table, CFG)) == ["X", "Y"]


def test_normalisation_is_done_within_each_country():
    table = _criteria([{"ville": "a", "technologie": "X", "rendement_annuel": 1000}, {"ville": "a", "technologie": "Y", "rendement_annuel": 1100},
                       {"ville": "b", "technologie": "X", "rendement_annuel": 1900, "pays": "Autre"},
                       {"ville": "b", "technologie": "Y", "rendement_annuel": 2000, "pays": "Autre"}])
    scores = reliability.scores(table, WEIGHTS, CFG)
    # Dans chaque pays, la meilleure technologie obtient le même score, quel que soit le niveau absolu.
    assert scores.iloc[1] == pytest.approx(scores.iloc[3]) and scores.iloc[0] == pytest.approx(scores.iloc[2])
