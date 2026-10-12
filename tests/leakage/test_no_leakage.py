"""Anti-fuite temporelle : une variable ex ante du jour t ne doit dépendre d'aucune information postérieure à t-1.

Méthode : on falsifie toutes les observations à partir d'une date, on recalcule les variables, et on
vérifie que les variables ex ante d'avant cette date n'ont pas bougé. Ce test ne réutilise pas la
logique testée : il observe seulement si le futur a une influence.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from solarvision.config import load_cities, split_index
from solarvision.features import panel as panel_module


@pytest.fixture(scope="module")
def tunis_daily(data_root) -> pd.DataFrame:
    return pd.read_parquet(data_root / "interim" / "tunis.parquet")


def test_ex_ante_features_ignore_the_future(tunis_daily):
    city, n_train = load_cities()["tunis"], split_index(len(tunis_daily))
    reference = panel_module.build_city_features(tunis_daily, city, n_train).set_index("date")
    roles = panel_module.feature_roles(list(reference.reset_index().columns))
    for cut in (n_train, n_train + 200, len(tunis_daily) - 30):
        tampered = tunis_daily.copy()
        observed = [c for c in tampered.columns if c not in ("irr_extraterrestre_kwh_m2", "duree_jour_astro_h",
                                                            "hauteur_soleil_midi_deg", "jour_annee")]
        # Tout ce qui est observé à partir du jour « cut » est remplacé par une valeur absurde.
        tampered.iloc[cut:, [tampered.columns.get_loc(c) for c in observed]] = 999.0
        rebuilt = panel_module.build_city_features(tampered, city, n_train).set_index("date")
        # Les lignes jusqu'au jour « cut » inclus n'utilisent que des observations antérieures à « cut ».
        before = slice(None, cut + 1)
        pd.testing.assert_frame_equal(reference[roles["ex_ante"]].iloc[before], rebuilt[roles["ex_ante"]].iloc[before])


def test_climatology_uses_training_days_only(tunis_daily):
    n_train = split_index(len(tunis_daily))
    series = tunis_daily["pv_crystSi_kwh_kwc"]
    tampered = series.copy()
    tampered.iloc[n_train:] = 999.0
    np.testing.assert_allclose(panel_module.climatology(series, n_train), panel_module.climatology(tampered, n_train))


def test_ex_post_columns_are_flagged_and_never_ex_ante(tunis_daily):
    city, n_train = load_cities()["tunis"], split_index(len(tunis_daily))
    columns = list(panel_module.build_city_features(tunis_daily, city, n_train).columns)
    roles = panel_module.feature_roles(columns)
    assert roles["ex_post"] and all(c.startswith("expost_") for c in roles["ex_post"])
    assert not set(roles["ex_ante"]) & set(roles["ex_post"])
    assert not set(roles["ex_ante"]) & set(roles["cibles"])
    # Chaque colonne du panel a un rôle et un seul.
    assert sorted(sum(roles.values(), [])) == sorted(columns)


def test_split_is_chronological_without_overlap(data_root):
    if not (data_root / "processed" / "splits_90_10.yaml").exists():
        pytest.skip("panel non construit : lancer python -m solarvision.cli features")
    panel, splits = panel_module.load_panel(data_root), panel_module.load_splits(data_root)
    for city, s in splits.items():
        dates = panel.loc[panel["ville"] == city, "date"].reset_index(drop=True)
        assert dates.is_monotonic_increasing and dates.is_unique, city
        assert s["n_train"] == int(s["n"] * 0.9) and s["n_train"] + s["n_test"] == s["n"], city
        assert str(dates.iloc[s["n_train"] - 1].date()) == s["train_fin"] < s["test_debut"] == str(dates.iloc[s["n_train"]].date())


def test_tunis_split_matches_the_validated_one(data_root):
    if not (data_root / "processed" / "splits_90_10.yaml").exists():
        pytest.skip("panel non construit")
    s = panel_module.load_splits(data_root)["tunis"]
    assert (s["n_train"], s["n_test"], s["train_fin"], s["test_debut"]) == (6245, 694, "2022-02-05", "2022-02-06")
