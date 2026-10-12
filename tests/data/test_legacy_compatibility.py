"""Compatibilité avec le panel historique à 9 villes : la v2 doit redonner les mêmes séries de référence."""
from __future__ import annotations

import pandas as pd
import pytest

from solarvision.config import ROOT
from solarvision.features import panel as panel_module

LEGACY_PANEL = ROOT / "data" / "datasets" / "panel_9_villes_journalier.csv"


@pytest.mark.skipif(not LEGACY_PANEL.exists(), reason="panel historique absent")
def test_legacy_view_matches_the_nine_city_panel(data_root):
    if not (data_root / "processed" / "panel_journalier.parquet").exists():
        pytest.skip("panel non construit : lancer python -m solarvision.cli features")
    view = panel_module.legacy_view(panel_module.load_panel(data_root))
    old = pd.read_csv(LEGACY_PANEL, usecols=["date", "site", "pv_kwh_kwc", "jour_impute_pvgis"], parse_dates=["date"])
    merged = view.merge(old, on=["date", "site"], suffixes=("_v2", "_v1"))
    common = sorted(merged["site"].unique())
    assert common, "aucune ville commune entre les deux panels"
    # Le fichier historique est arrondi à 4 décimales : l'écart toléré est celui de l'arrondi.
    assert (merged["pv_kwh_kwc_v2"] - merged["pv_kwh_kwc_v1"]).abs().max() < 1e-4
    assert (merged["jour_impute_pvgis_v2"] == merged["jour_impute_pvgis_v1"]).all()
    assert len(merged) == len(common) * 6939
