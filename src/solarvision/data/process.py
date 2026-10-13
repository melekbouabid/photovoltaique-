"""Du cache brut aux tables journalières : agrégation, imputation des trous PVGIS, qualité, manifeste.

Aucun appel réseau ici : tout se reconstruit depuis le cache (option --reprocess).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from solarvision.config import DATA, LEGACY_RAW, ROOT, City, load_cities, load_params
from solarvision.data import ingest

PV_COLUMN = "pv_{}_kwh_kwc"
IMPUTED = "jour_impute_pvgis"
LICENCES = {
    "pvgis": "PVGIS 5.3 © Union européenne (JRC) ; rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source",
    "open_meteo": "Open-Meteo Historical Weather API (ERA5, Copernicus/ECMWF), CC BY 4.0",
    "nasa_power": "NASA Langley Research Center, projet POWER (MERRA-2, CERES), données ouvertes",
}


def pv_columns() -> list[str]:
    return [PV_COLUMN.format(t) for t in load_params()["pv"]["technologies"]]


def astronomy(dates: pd.DatetimeIndex, lat: float) -> pd.DataFrame:
    """Grandeurs astronomiques, connues à l'avance pour toute date (donc utilisables ex ante).

    Rayonnement extraterrestre journalier sur plan horizontal (Duffie et Beckman), durée du jour
    et hauteur du soleil à midi solaire. Mêmes formules que la v1.
    """
    j = dates.dayofyear.to_numpy()
    phi = np.radians(lat)
    decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + j) / 365)          # déclinaison (Cooper, 1969)
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)                             # excentricité de l'orbite
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(decl), -1, 1))              # angle horaire du coucher
    h0 = 24 / np.pi * 1.367 * dr * (ws * np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.sin(ws))
    return pd.DataFrame({"irr_extraterrestre_kwh_m2": h0, "duree_jour_astro_h": 24 / np.pi * ws,
                         "hauteur_soleil_midi_deg": 90 - np.degrees(np.abs(phi - decl)), "jour_annee": j}, index=dates)


def aggregate_daily(city: City) -> pd.DataFrame:
    """Passage de l'horaire au journalier (jour UTC : à ces longitudes, minuit UTC ne coupe aucune heure de soleil)."""
    ref = load_params()["pv"]["reference_technology"]
    daily: dict[str, pd.Series] = {}
    for tech in load_params()["pv"]["technologies"]:
        h = ingest.load_hourly(city, tech)
        if h is None:
            raise FileNotFoundError(f"{city.id} : série PVGIS {tech} absente du cache")
        day = h.index.floor("D")
        daily[PV_COLUMN.format(tech)] = h["P"].astype("float64").groupby(day).sum() / 1000     # Wh -> kWh
        if tech == ref:
            # Météo et géométrie viennent de la même réponse pour toutes les technologies : on les lit une fois.
            g = h.astype("float64").groupby(day)
            daily["irr_poa_kwh_m2"] = g["G"].sum() / 1000
            daily["hauteur_soleil_max_deg"] = g["H_sun"].max()
            daily["t2m_moy_c"], daily["t2m_max_c"], daily["t2m_min_c"] = g["T2m"].mean(), g["T2m"].max(), g["T2m"].min()
            daily["t2m_jour_c"] = h["T2m"].astype("float64").where(h["H_sun"] > 0).groupby(day).mean()
            daily["vent_moy_ms"] = g["WS10m"].mean()
            daily["heures_reconstruites"] = g["Int"].sum()
    hz = ingest.load_hourly(city, ingest.HORIZONTAL)
    if hz is None:
        raise FileNotFoundError(f"{city.id} : série PVGIS horizontale absente du cache")
    daily["ghi_pvgis_kwh_m2"] = hz["G"].astype("float64").groupby(hz.index.floor("D")).sum() / 1000
    d = pd.DataFrame(daily)
    d.index.name = "date"
    d["amplitude_thermique_c"] = d["t2m_max_c"] - d["t2m_min_c"]
    return d


def impute_pvgis_gaps(d: pd.DataFrame, energy_columns: list[str], intensive_columns: list[str]) -> pd.DataFrame:
    """Repère et corrige les jours où la base satellitaire SARAH3 a un trou, que PVGIS enregistre comme des zéros.

    Un jour est suspect si :
    (1) la hauteur maximale du soleil donnée par PVGIS est inférieure de plus de 5° à la hauteur
        astronomique à midi (PVGIS met aussi la hauteur à zéro quand l'image manque) ; ou
    (2) l'irradiation PVGIS vaut moins du quart de celle de NASA POWER, alors que NASA POWER
        voit une journée claire (plus de 1,5 kWh/m²). Comme en v1, ERA5 doit confirmer.
    Correction : irradiation NASA POWER du jour multipliée par le rapport médian PVGIS / NASA des
    jours valides voisins (fenêtre centrée de 31 jours). Le même procédé s'applique à chaque
    technologie : la correction reste cohérente entre elles. Le jour reste signalé.
    """
    cfg = load_params()["imputation"]
    d = d.copy()
    gap = d["hauteur_soleil_midi_deg"] - d["hauteur_soleil_max_deg"]
    inconsistent = (d["ghi_pvgis_kwh_m2"] < cfg["ghi_ratio_threshold"] * d["ghi_nasa_kwh_m2"]) \
        & (d["ghi_nasa_kwh_m2"] > cfg["ghi_nasa_min_kwh_m2"])
    if cfg["require_era5_agreement"] and "ghi_era5_kwh_m2" in d:
        inconsistent &= d["ghi_pvgis_kwh_m2"] < cfg["ghi_ratio_threshold"] * d["ghi_era5_kwh_m2"]
    hole = (gap > cfg["sun_height_gap_deg"]) | inconsistent
    d[IMPUTED] = hole.astype(int)
    if not hole.any():
        return d
    d.loc[hole, energy_columns + intensive_columns] = np.nan
    ref = d["ghi_nasa_kwh_m2"]
    for column in energy_columns:
        # Les jours suspects sont déjà à NaN : la médiane ne s'appuie que sur des jours valides.
        ratio = (d[column] / ref).where(ref > cfg["ref_min_kwh_m2"]) \
            .rolling(cfg["window_days"], center=True, min_periods=cfg["min_periods"]).median()
        d.loc[hole, column] = (ratio * ref)[hole]
    d[intensive_columns] = d[intensive_columns].interpolate(limit_area="inside")
    return d


def build_daily(city: City) -> pd.DataFrame:
    """Table journalière complète d'une ville : PVGIS, Open-Meteo, NASA POWER, astronomie, imputation."""
    weather, nasa = ingest.load_open_meteo(city), ingest.load_nasa(city)
    if weather is None or nasa is None:
        raise FileNotFoundError(f"{city.id} : Open-Meteo ou NASA POWER absent du cache")
    d = aggregate_daily(city).join(weather, how="left").join(nasa, how="left")
    d = d.join(astronomy(d.index, city.lat))
    # Petits trous des sources complémentaires : interpolation sur 3 jours au plus, sinon la valeur reste manquante.
    exo = [*ingest.OPEN_METEO_VARIABLES.values(), *ingest.NASA_VARIABLES.values()]
    d[exo] = d[exo].interpolate(limit=load_params()["imputation"]["exo_interpolation_limit_days"], limit_area="inside")
    d = impute_pvgis_gaps(d, [*pv_columns(), "irr_poa_kwh_m2", "ghi_pvgis_kwh_m2"],
                          ["hauteur_soleil_max_deg", "t2m_jour_c"])
    return d.asfreq("D")


def expected_days() -> int:
    p = load_params()["period"]
    return len(pd.date_range(f"{p['start_year']}-01-01", f"{p['end_year']}-12-31", freq="D"))


def quality_report(city: City, d: pd.DataFrame) -> dict:
    """Contrôles d'une table journalière : lignes, continuité, manquants, jours imputés, valeurs aberrantes."""
    cfg = load_params()["quality"]
    reasons = []
    if len(d) != expected_days():
        reasons.append(f"{len(d)} lignes au lieu de {expected_days()}")
    if not (d.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all():
        reasons.append("dates non continues")
    pv = pv_columns()
    missing_pv = int(d[pv].isna().sum().sum())
    if missing_pv:
        reasons.append(f"{missing_pv} valeurs PV manquantes")
    if (d[pv] < 0).any().any():
        reasons.append("production négative")
    imputed = int(d[IMPUTED].sum())
    low, high = cfg["expected_imputed_days"]
    if not low <= imputed <= high:
        reasons.append(f"{imputed} jours imputés, hors de la plage attendue [{low}, {high}]")
    outliers = {}
    for column in pv:
        # Les bornes sont calculées par mois de l'année : une journée d'hiver n'est pas aberrante parce qu'elle est basse.
        month = d.index.month
        q1, q3 = d[column].groupby(month).transform("quantile", 0.25), d[column].groupby(month).transform("quantile", 0.75)
        k = cfg["iqr_factor"] * (q3 - q1)
        outliers[column] = int(((d[column] < q1 - k) | (d[column] > q3 + k)).sum())
    return {
        "ville": city.id, "pays": city.pays, "lignes": len(d), "debut": str(d.index.min().date()),
        "fin": str(d.index.max().date()), "jours_imputes": imputed,
        "dates_imputees": [str(x.date()) for x in d.index[d[IMPUTED] == 1]],
        "manquants_pct": round(float(d.isna().mean().mean() * 100), 4),
        "manquants_par_colonne_pct": {c: round(float(v * 100), 3) for c, v in d.isna().mean().items() if v > 0},
        "aberrants_iqr": outliers,
        "production_annuelle_kwh_kwc": {c: round(float(d[c].sum() / (len(d) / 365.25)), 1) for c in pv},
        "statut": "failed" if reasons else "ok", "raisons": reasons,
    }


def process_city(city: City, out: Path) -> dict:
    """Construit et écrit les tables d'une ville, puis renvoie son rapport qualité."""
    from solarvision.data import schemas  # import local : schemas dépend de ce module

    d = build_daily(city)
    schemas.validate_city_tables(d)               # contrat de données : une table invalide n'est jamais écrite
    (out / "processed").mkdir(parents=True, exist_ok=True)
    (out / "interim").mkdir(parents=True, exist_ok=True)
    # Table minimale demandée par le protocole : la date, les 3 séries PV et le drapeau d'imputation.
    d[[*pv_columns(), IMPUTED]].to_csv(out / "processed" / f"{city.id}.csv", float_format="%.6f")
    d.to_parquet(out / "interim" / f"{city.id}.parquet")
    report = quality_report(city, d)
    (out / "quality").mkdir(parents=True, exist_ok=True)
    (out / "quality" / f"{city.id}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def write_quality_summary(reports: list[dict], out: Path) -> pd.DataFrame:
    rows = [{"ville": r["ville"], "pays": r["pays"], "lignes": r["lignes"], "jours_imputes": r["jours_imputes"],
             "manquants_pct": r["manquants_pct"], **{f"aberrants_{c}": n for c, n in r["aberrants_iqr"].items()},
             **{f"annuel_{c}": v for c, v in r["production_annuelle_kwh_kwc"].items()},
             "statut": r["statut"], "raisons": " ; ".join(r["raisons"])} for r in reports]
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "quality" / "summary.csv", index=False)
    return summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_entry(path: Path) -> dict:
    return {"fichier": path.relative_to(ROOT).as_posix(), "octets": path.stat().st_size, "sha256": _sha256(path),
            "recupere_le": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")}


def write_manifest(cities: list[City], out: Path) -> Path:
    """Fiche lisible par une machine : pour chaque ville, d'où vient chaque fichier et comment le revérifier."""
    period, pv = load_params()["period"], load_params()["pv"]
    entries = {}
    for city in cities:
        if not ingest.is_complete(city):
            continue
        new, legacy = sorted((ingest.RAW / "pvgis" / city.id).glob("*")), ingest.legacy_hourly_path(city)
        pvgis_files = [f for f in new if f.suffix != ".part"] + ([legacy] if legacy.exists() else [])
        om = ingest.open_meteo_path(city) if ingest.open_meteo_path(city).exists() else LEGACY_RAW / "open_meteo" / f"{city.id}.csv"
        nasa = ingest.nasa_path(city) if ingest.nasa_path(city).exists() else LEGACY_RAW / "nasa_power" / f"{city.id}.csv"
        processed = out / "processed" / f"{city.id}.csv"
        entries[city.id] = {
            "coordonnees": {"lat": city.lat, "lon": city.lon, "altitude_m": city.altitude, "fuseau": city.fuseau},
            "pente_optimale_deg": ingest.optimal_slope(city),
            "sources": {
                "pvgis": {"origine": "cache v1 (data/brut) + téléchargement v2" if legacy.exists() else "téléchargement v2",
                          "fichiers": [_file_entry(f) for f in pvgis_files]},
                "open_meteo": {"origine": "cache v1 (data/brut)" if LEGACY_RAW in om.parents else "téléchargement v2",
                               "fichiers": [_file_entry(om)]},
                "nasa_power": {"origine": "cache v1 (data/brut)" if LEGACY_RAW in nasa.parents else "téléchargement v2",
                               "fichiers": [_file_entry(nasa)]},
            },
            "table_traitee": _file_entry(processed) if processed.exists() else None,
        }
    manifest = {
        "genere_le": datetime.now().isoformat(timespec="seconds"),
        "periode": f"{period['start_year']}-01-01 / {period['end_year']}-12-31",
        "pas": "journalier (agrégé depuis l'horaire PVGIS, jour UTC)",
        "installation": {"puissance_kwc": pv["peak_power_kwp"], "pertes_systeme_pct": pv["system_loss_pct"],
                         "orientation": "plein sud, pente optimale du site", "technologies": pv["technologies"]},
        "unites": {"pv_*_kwh_kwc": "kWh par kWc et par jour", "ghi_*": "kWh/m² par jour", "jour_impute_pvgis": "0/1"},
        "fuseau": "PVGIS : UTC ; Open-Meteo : heure locale ; NASA POWER : heure solaire locale",
        "licences": LICENCES,
        "reconstruction": "python -m solarvision.cli ingest (télécharge ce qui manque), puis --reprocess sans réseau",
        "villes_presentes": sorted(entries), "villes_manquantes": sorted(c.id for c in cities if c.id not in entries),
        "villes": entries,
    }
    path = out / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=140), encoding="utf-8")
    return path


def process_all(cities: list[City], out: Path = DATA) -> pd.DataFrame:
    """Traite toutes les villes complètes ; une ville incomplète est listée, jamais simulée."""
    reports = []
    for city in cities:
        if not ingest.is_complete(city):
            ingest.log(f"{city.id} : sources incomplètes {ingest.source_status(city)}, ville non traitée")
            continue
        try:
            reports.append(process_city(city, out))
            ingest.log(f"{city.id} : table traitée, {reports[-1]['jours_imputes']} jours imputés, statut {reports[-1]['statut']}")
        except Exception as err:                           # noqa: BLE001 - une ville en échec ne bloque pas les autres
            ingest.log(f"ÉCHEC traitement {city.id} : {err}")
    # Le résumé de qualité et le manifeste décrivent TOUTES les villes du dossier, pas seulement celles de cette
    # exécution : retraiter dix villes ne doit pas faire disparaître les vingt autres.
    scope = list(load_cities().values()) if out == DATA else cities
    order = [c.id for c in scope]
    every = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((out / "quality").glob("*.json"))] if (out / "quality").exists() else []
    every = sorted((r for r in every if r["ville"] in order), key=lambda r: order.index(r["ville"]))
    summary = write_quality_summary(every, out) if every else pd.DataFrame()
    write_manifest(scope, out)
    done = {r["ville"] for r in reports}
    return summary[summary["ville"].isin(done)] if len(summary) else summary
