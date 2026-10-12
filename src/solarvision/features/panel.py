"""Panel de modélisation : une ligne par ville et par jour, variables ex ante et ex post séparées.

Convention : la ligne du jour t contient la cible du jour t.
- Une variable **ex ante** de la ligne t ne dépend que d'informations connues avant t
  (calendrier, astronomie, normale saisonnière de l'apprentissage, valeurs observées jusqu'à t-1).
- Une variable **ex post** est la météo observée le jour t : elle n'est connue qu'après coup et ne
  sert qu'à mesurer ce qu'apporterait une prévision météo parfaite.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from solarvision.config import DATA, City, load_cities, load_params, split_index
from solarvision.data.process import IMPUTED, pv_columns

ID_COLUMNS = ["ville", "nom", "pays", "code_pays", "lat", "lon", "altitude"]
# Météo du jour même : connue seulement après coup.
EX_POST_COLUMNS = [
    "nebulosite_pct", "ensoleillement_h", "precipitation_mm", "humidite_pct", "point_rosee_c", "pression_hpa",
    "rafales_max_kmh", "et0_mm", "ghi_era5_kwh_m2", "ghi_nasa_kwh_m2", "ghi_ciel_clair_kwh_m2", "indice_clarte",
    "nebulosite_nasa_pct", "aerosols_aod", "ghi_pvgis_kwh_m2", "irr_poa_kwh_m2", "t2m_moy_c", "t2m_max_c",
    "t2m_min_c", "amplitude_thermique_c", "vent_moy_ms",
]
# Météo de la veille : observée, donc disponible au moment de prévoir.
LAGGED_WEATHER = ["nebulosite_pct", "t2m_moy_c", "humidite_pct", "precipitation_mm", "aerosols_aod", "indice_clarte"]


def fourier_terms(dates: pd.DatetimeIndex, harmonics: int) -> pd.DataFrame:
    """Cycle annuel déterministe : sinus et cosinus du rang du jour dans l'année (connus à l'avance)."""
    angle = 2 * np.pi * dates.dayofyear.to_numpy() / 365.25
    return pd.DataFrame({f"fourier_{f}_{k}": fn(k * angle) for k in range(1, harmonics + 1)
                         for f, fn in (("sin", np.sin), ("cos", np.cos))}, index=dates)


def climatology(series: pd.Series, n_train: int, window: int | None = None) -> np.ndarray:
    """Normale saisonnière : moyenne par jour de l'année sur l'apprentissage seul, lissée sur 31 jours.

    Le lissage est circulaire (décembre et janvier se suivent). Le 29 février est rangé avec le
    jour 365. Aucune valeur du test n'entre dans le calcul : la normale est utilisable ex ante.
    """
    window = window or load_params()["features"]["climatology_window_days"]
    day = np.minimum(series.index.dayofyear.to_numpy(), 365)
    mean = series.iloc[:n_train].groupby(day[:n_train]).mean().reindex(range(1, 366)).interpolate().to_numpy()
    half = window // 2
    padded = np.concatenate([mean[-half:], mean, mean[:half]])
    smooth = np.convolve(padded, np.ones(window) / window, mode="valid")
    return smooth[day - 1]


def build_city_features(d: pd.DataFrame, city: City, n_train: int) -> pd.DataFrame:
    """Variables d'une ville à partir de sa table journalière (fonction pure, testée contre les fuites)."""
    cfg = load_params()["features"]
    out = pd.DataFrame(index=d.index)
    out["annee"], out["mois"], out["jour_annee"] = d.index.year, d.index.month, d.index.dayofyear
    out = out.join(fourier_terms(d.index, cfg["fourier_harmonics"]))
    out = out.join(d[["irr_extraterrestre_kwh_m2", "duree_jour_astro_h", "hauteur_soleil_midi_deg"]])
    for column in pv_columns():
        tech = column.removeprefix("pv_").removesuffix("_kwh_kwc")
        out[column] = d[column]
        out[f"normale_{tech}"] = climatology(d[column], n_train)
        for lag in cfg["lags_days"]:
            out[f"{column}_lag{lag}"] = d[column].shift(lag)
        # shift(1) avant la moyenne : la fenêtre s'arrête à la veille, jamais au jour prévu.
        out[f"{column}_moy{cfg['rolling_window_days']}_passe"] = d[column].shift(1).rolling(cfg["rolling_window_days"]).mean()
    for column in LAGGED_WEATHER:
        out[f"{column}_lag1"] = d[column].shift(1)
    out = out.join(d[EX_POST_COLUMNS].add_prefix("expost_"))
    out[IMPUTED] = d[IMPUTED]
    for key, value in (("ville", city.id), ("nom", city.nom), ("pays", city.pays), ("code_pays", city.code_pays),
                       ("lat", city.lat), ("lon", city.lon), ("altitude", city.altitude)):
        out[key] = value
    out.index.name = "date"
    return out.reset_index()[["date", *ID_COLUMNS, *[c for c in out.columns if c not in ID_COLUMNS]]]


def feature_roles(columns: list[str]) -> dict[str, list[str]]:
    """Rôle de chaque colonne du panel : sert aux modèles et au test anti-fuite."""
    targets = pv_columns()
    ex_post = [c for c in columns if c.startswith("expost_")]
    ids = ["date", *ID_COLUMNS]
    flags = [IMPUTED]
    ex_ante = [c for c in columns if c not in {*targets, *ex_post, *ids, *flags}]
    return {"identifiants": ids, "cibles": targets, "ex_ante": ex_ante, "ex_post": ex_post, "drapeaux": flags}


def build_panel(root: Path = DATA, allow_partial: bool = False, cities: list[City] | None = None) -> pd.DataFrame:
    """Assemble le panel, écrit les découpages et la liste des villes manquantes."""
    cities = cities or list(load_cities().values())
    frames, splits, missing = [], {}, []
    for city in cities:
        path = root / "interim" / f"{city.id}.parquet"
        if not path.exists():
            missing.append(city.id)
            continue
        d = pd.read_parquet(path)
        n, n_train = len(d), split_index(len(d))
        frames.append(build_city_features(d, city, n_train))
        splits[city.id] = {"n": n, "n_train": n_train, "n_test": n - n_train,
                           "train_debut": str(d.index[0].date()), "train_fin": str(d.index[n_train - 1].date()),
                           "test_debut": str(d.index[n_train].date()), "test_fin": str(d.index[-1].date())}
    if missing and not allow_partial:
        raise RuntimeError(f"villes sans table traitée : {missing}. Relancer l'ingestion ou utiliser --allow-partial.")
    if not frames:
        raise RuntimeError("aucune ville traitée : lancer d'abord l'ingestion")
    panel = pd.concat(frames, ignore_index=True)
    out = root / "processed"
    out.mkdir(parents=True, exist_ok=True)
    roles = feature_roles(list(panel.columns))
    meta = {"villes_presentes": sorted(splits), "villes_manquantes": missing, "n_villes": len(splits),
            "lignes": len(panel), "colonnes": len(panel.columns)}
    table = pa.Table.from_pandas(panel, preserve_index=False)
    # La liste des villes manquantes voyage avec le fichier : un panel partiel ne peut pas passer pour complet.
    table = table.replace_schema_metadata({**(table.schema.metadata or {}),
                                           b"villes_manquantes": ",".join(missing).encode(),
                                           b"n_villes": str(len(splits)).encode()})
    name = f"panel_journalier_{len(splits)}_villes.parquet"
    # Un panel construit avec un autre nombre de villes est périmé : on ne le laisse pas traîner à côté du bon.
    for stale in out.glob("panel_journalier_*_villes.parquet"):
        if stale.name != name:
            stale.unlink()
    pq.write_table(table, out / name)
    pq.write_table(table, out / "panel_journalier.parquet")           # alias stable, lu par le reste du pipeline
    (out / "splits_90_10.yaml").write_text(yaml.safe_dump(
        {"regle": "découpage chronologique, coupure à int(n * 0.9)", "villes": splits}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    (out / "panel_meta.yaml").write_text(yaml.safe_dump({**meta, "fichier": name, "roles": roles}, allow_unicode=True,
                                                        sort_keys=False), encoding="utf-8")
    return panel


def load_panel(root: Path = DATA) -> pd.DataFrame:
    return pd.read_parquet(root / "processed" / "panel_journalier.parquet")


def load_splits(root: Path = DATA) -> dict:
    return yaml.safe_load((root / "processed" / "splits_90_10.yaml").read_text(encoding="utf-8"))["villes"]


def load_roles(root: Path = DATA) -> dict[str, list[str]]:
    return yaml.safe_load((root / "processed" / "panel_meta.yaml").read_text(encoding="utf-8"))["roles"]


def legacy_view(panel: pd.DataFrame) -> pd.DataFrame:
    """Vue compatible avec l'ancien panel à 9 villes : mêmes noms de colonnes pour les champs communs."""
    ref = PV_REFERENCE()
    view = panel.rename(columns={"ville": "site", "nom": "ville", "lat": "latitude", "lon": "longitude", ref: "pv_kwh_kwc"})
    return view[["date", "site", "ville", "pays", "code_pays", "latitude", "longitude", "pv_kwh_kwc", IMPUTED]]


def PV_REFERENCE() -> str:  # noqa: N802 - constante dérivée de la configuration
    return f"pv_{load_params()['pv']['reference_technology']}_kwh_kwc"
