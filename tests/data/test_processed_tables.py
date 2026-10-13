"""Tables traitées : schéma, nombre de lignes, couverture des technologies, cohérence de l'imputation."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from solarvision.config import DATA, ROOT, load_cities, load_params
from solarvision.data import process, schemas

# Dates relevées dans le jeu de données de la v1 (tn_photovoltaique_journalier.csv), indépendamment de ce code.
TUNIS_IMPUTED_DATES = ["2005-04-18", "2008-01-23", "2008-03-01", "2008-03-06", "2008-05-17", "2008-05-18", "2009-04-18",
                       "2009-04-19", "2009-08-15", "2009-08-16", "2014-12-02", "2016-10-16", "2016-10-17"]
LEGACY_TUNISIA = ROOT / "data" / "datasets" / "tn_photovoltaique_journalier.csv"


def _read(root, city: str) -> pd.DataFrame:
    return pd.read_csv(root / "processed" / f"{city}.csv", parse_dates=["date"]).set_index("date")


def test_each_processed_table_respects_its_schema(data_root, processed_cities):
    for city in processed_cities:
        schemas.processed_schema().validate(_read(data_root, city), lazy=True)


def test_each_table_has_all_days_and_three_technologies(data_root, processed_cities):
    for city in processed_cities:
        d = _read(data_root, city)
        assert len(d) == process.expected_days() == 6939, city
        assert list(d.columns) == [*process.pv_columns(), process.IMPUTED], city
        assert d[process.pv_columns()].notna().all().all(), city


def test_tunis_imputed_dates_match_the_v1_dataset(data_root):
    """Vérification non circulaire : la liste attendue vient du jeu de la v1, pas de la règle testée."""
    d = _read(data_root, "tunis")
    assert [str(x.date()) for x in d.index[d[process.IMPUTED] == 1]] == TUNIS_IMPUTED_DATES


@pytest.mark.skipif(not LEGACY_TUNISIA.exists(), reason="jeu de la v1 absent")
def test_tunis_reference_series_equals_the_v1_series(data_root):
    old = pd.read_csv(LEGACY_TUNISIA, parse_dates=["date"])
    old = old[old["site"] == "tunis"].set_index("date")
    new = _read(data_root, "tunis")
    assert [str(x.date()) for x in old.index[old["jour_impute_pvgis"] == 1]] == TUNIS_IMPUTED_DATES
    # Le fichier de la v1 est arrondi à 4 décimales : l'écart toléré est celui de l'arrondi.
    assert (new["pv_crystSi_kwh_kwc"] - old["pv_kwh_kwc"]).abs().max() < 1e-4


def test_imputed_days_are_plausible_in_every_city(data_root, processed_cities):
    low, high = load_params()["quality"]["expected_imputed_days"]
    for city in processed_cities:
        d = _read(data_root, city)
        days = d[d[process.IMPUTED] == 1]
        assert low <= len(days) <= high, f"{city} : {len(days)} jours imputés"
        # Une valeur imputée est une vraie production : positive, et proche d'une technologie à l'autre.
        assert (days[process.pv_columns()] > 0).all().all(), city
        ratio = days[process.pv_columns()].div(days["pv_crystSi_kwh_kwc"], axis=0)
        assert ratio.min().min() > 0.6 and ratio.max().max() < 1.5, city


def test_technologies_stay_close_to_each_other(data_root, processed_cities):
    # Même site, même ciel : les productions annuelles des trois technologies diffèrent de quelques pour cent.
    for city in processed_cities:
        annual = _read(data_root, city)[process.pv_columns()].sum()
        assert annual.max() / annual.min() < 1.15, city


@pytest.mark.data
def test_all_thirty_cities_are_processed():
    """Critère d'acceptation de l'étude complète : échoue tant qu'une ville manque (jamais de ville simulée)."""
    missing = [c for c in load_cities() if not (DATA / "processed" / f"{c}.csv").exists()]
    assert len(load_cities()) == 30
    assert not missing, f"villes sans table traitée : {missing}"


def test_imputation_recovers_a_known_gap():
    """Cas construit à la main : on efface un jour dont on connaît la vraie valeur et on vérifie la correction."""
    dates = pd.date_range("2010-01-01", periods=120, freq="D")
    rng = np.random.default_rng(0)
    nasa = 4 + np.sin(np.arange(120) / 20) + rng.normal(0, 0.05, 120)
    truth = 0.8 * nasa
    d = pd.DataFrame({"pv_crystSi_kwh_kwc": truth, "ghi_pvgis_kwh_m2": nasa * 1.02, "ghi_nasa_kwh_m2": nasa,
                      "ghi_era5_kwh_m2": nasa * 0.98, "hauteur_soleil_midi_deg": 50.0,
                      "hauteur_soleil_max_deg": 49.0}, index=dates)
    hole_sun, hole_ghi = dates[40], dates[80]
    d.loc[hole_sun, ["pv_crystSi_kwh_kwc", "ghi_pvgis_kwh_m2", "hauteur_soleil_max_deg"]] = 0.0     # image manquante
    d.loc[hole_ghi, ["pv_crystSi_kwh_kwc", "ghi_pvgis_kwh_m2"]] = [0.0, 0.1]                        # zéro injustifié
    out = process.impute_pvgis_gaps(d, ["pv_crystSi_kwh_kwc", "ghi_pvgis_kwh_m2"], ["hauteur_soleil_max_deg"])
    assert list(out.index[out[process.IMPUTED] == 1]) == [hole_sun, hole_ghi]
    assert abs(out.loc[hole_sun, "pv_crystSi_kwh_kwc"] - truth[40]) < 0.1
    assert abs(out.loc[hole_ghi, "pv_crystSi_kwh_kwc"] - truth[80]) < 0.1
    # Un jour réellement sombre (NASA faible aussi) ne doit pas être imputé.
    dark = d.copy()
    dark.loc[dates[60], ["pv_crystSi_kwh_kwc", "ghi_pvgis_kwh_m2", "ghi_nasa_kwh_m2", "ghi_era5_kwh_m2"]] = [0.2, 0.3, 1.0, 1.0]
    assert process.impute_pvgis_gaps(dark, ["pv_crystSi_kwh_kwc"], [])[process.IMPUTED].iloc[60] == 0
