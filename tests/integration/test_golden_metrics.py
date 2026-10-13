"""Non-régression : les erreurs de référence de Tunis ne doivent pas bouger sans raison.

Les valeurs attendues viennent de l'étude historique (resultats/py_metriques.csv). La tolérance est écrite
pour chaque modèle : étroite pour les références, qui sont déterministes ; plus large pour les modèles
réajustés, dont le résultat dépend des versions de bibliothèques.
"""
from __future__ import annotations

import pandas as pd
import pytest

from solarvision.config import REPORTS

# modèle -> (RMSE attendu en kWh/kWc, tolérance absolue)
GOLDEN_TUNIS = {
    "climatologie": (1.1002, 0.0005),
    "persistance": (1.4335, 0.0005),
    "arima_fourier": (1.0892, 0.0050),
    "xgboost": (1.0834, 0.0100),
    "prophet": (1.0969, 0.0100),
}


@pytest.fixture(scope="module")
def tunis() -> pd.Series:
    for reports in (REPORTS, REPORTS / "fast"):
        path = reports / "metrics_wide.csv"
        if path.exists():
            wide = pd.read_csv(path, dtype={"horizon": str})
            block = wide[(wide["ville"] == "tunis") & (wide["technologie"] == "crystSi") & (wide["horizon"] == "tous")]
            if len(block):
                return block.set_index("modele")["RMSE"]
    pytest.skip("métriques absentes : lancer python -m solarvision.cli pipeline --fast")


@pytest.mark.parametrize("model", list(GOLDEN_TUNIS))
def test_tunis_rmse_stays_within_tolerance(tunis, model):
    expected, tolerance = GOLDEN_TUNIS[model]
    assert tunis[model] == pytest.approx(expected, abs=tolerance)


def test_tunis_ranking_is_the_expected_one(tunis):
    # La persistance est la moins bonne ; les modèles ex ante se tiennent à moins de 3 % de la climatologie.
    assert tunis["persistance"] > tunis["climatologie"]
    for model in ("arima_fourier", "xgboost"):
        assert 0.97 * tunis["climatologie"] < tunis[model] < tunis["climatologie"]


def test_every_origin_is_evaluated():
    for reports in (REPORTS, REPORTS / "fast"):
        path = reports / "forecasts" / "tunis.parquet"
        if path.exists():
            forecasts = pd.read_parquet(path)
            block = forecasts[(forecasts["modele"] == "climatologie") & (forecasts["technologie"] == "crystSi")]
            # 688 origines (du dernier jour d'apprentissage au dernier jour qui laisse 7 jours) x 7 horizons.
            assert block["origine"].nunique() == 688 and len(block) == 688 * 7
            assert str(block["origine"].min().date()) == "2022-02-05"
            return
    pytest.skip("prévisions absentes")
