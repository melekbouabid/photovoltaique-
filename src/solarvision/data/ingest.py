"""Ingestion des sources : PVGIS, Open-Meteo (ERA5) et NASA POWER.

Principes :
- un cache par source et par ville (data/raw/<source>/<ville>/), jamais modifié après écriture ;
- écriture atomique (fichier .part puis remplacement) : une coupure ne laisse pas de fichier tronqué ;
- reprise : un fichier présent n'est jamais retéléchargé ;
- le cache de la v1 (data/brut/) est relu tel quel pour les 9 villes historiques ;
- un quota dépassé arrête la source proprement et note l'heure de reprise dans data/failures.json ;
- aucune donnée n'est simulée : une ville incomplète reste manquante.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from solarvision.config import DATA, LEGACY_RAW, City, load_params

RAW = DATA / "raw"
FAILURES = DATA / "failures.json"
LOG = DATA / "ingest.log"

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
HEADERS = {"User-Agent": "SolarVision-TS/2.0 (mini-projet universitaire de series temporelles)"}

# Dix variables au plus : au-delà, Open-Meteo compte la requête comme plusieurs appels.
OPEN_METEO_VARIABLES = {
    "cloud_cover_mean": "nebulosite_pct", "sunshine_duration": "ensoleillement_h",
    "daylight_duration": "duree_jour_h", "precipitation_sum": "precipitation_mm",
    "relative_humidity_2m_mean": "humidite_pct", "dew_point_2m_mean": "point_rosee_c",
    "pressure_msl_mean": "pression_hpa", "wind_gusts_10m_max": "rafales_max_kmh",
    "et0_fao_evapotranspiration": "et0_mm", "shortwave_radiation_sum": "ghi_era5_kwh_m2",
}
NASA_VARIABLES = {
    "ALLSKY_SFC_SW_DWN": "ghi_nasa_kwh_m2", "CLRSKY_SFC_SW_DWN": "ghi_ciel_clair_kwh_m2",
    "ALLSKY_KT": "indice_clarte", "TOA_SW_DWN": "rayonnement_toa_kwh_m2", "CLOUD_AMT": "nebulosite_nasa_pct",
    "AOD_55": "aerosols_aod", "ALLSKY_SFC_UV_INDEX": "indice_uv", "ALLSKY_SRF_ALB": "albedo",
    "ALLSKY_SFC_PAR_TOT": "par_kwh_m2",
}
HORIZONTAL = "horizontal"

_log_lock = threading.Lock()


class QuotaExceeded(RuntimeError):
    """Quota d'une API dépassé pour longtemps : on s'arrête et on note quand reprendre."""

    def __init__(self, source: str, resume_at: datetime, reason: str = ""):
        super().__init__(f"{source} : quota dépassé, reprise possible à {resume_at:%Y-%m-%d %H:%M} UTC ({reason})")
        self.source, self.resume_at, self.reason = source, resume_at, reason


def log(message: str) -> None:
    """Journal horodaté, à l'écran et dans data/ingest.log (la collecte tourne en tâche de fond)."""
    line = f"{datetime.now():%H:%M:%S} {message}"
    with _log_lock:
        print(line, flush=True)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def atomic_write(path: Path, content: bytes) -> None:
    """Écrit d'abord un fichier .part : un fichier final présent est donc toujours complet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(content)
    os.replace(tmp, path)


def _quota_wait_seconds(response: requests.Response) -> tuple[float, str]:
    """Durée d'attente après un HTTP 429 : en-tête Retry-After, sinon message du service."""
    reason = response.text[:160].replace("\n", " ")
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header), reason
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()), reason
            except (TypeError, ValueError):
                pass
    now = datetime.now(UTC)
    text = reason.lower()
    if "daily" in text or "tomorrow" in text:
        # Quota journalier : il repart à minuit UTC.
        return ((now + timedelta(days=1)).replace(hour=0, minute=0, second=30, microsecond=0) - now).total_seconds(), reason
    if "hour" in text:
        # Quota horaire : il repart à l'heure pile UTC.
        return ((now + timedelta(hours=1)).replace(minute=0, second=30, microsecond=0) - now).total_seconds(), reason
    return 65.0, reason                                   # quota à la minute


def fetch(source: str, url: str, params: dict) -> bytes:
    """GET avec reprises. Un 429 long lève QuotaExceeded ; une requête invalide (4xx) n'est pas rejouée."""
    cfg = load_params()["ingest"]
    last: object = None
    for attempt in range(cfg["retries"]):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=(30, cfg["timeout_s"]))
        except requests.RequestException as err:           # coupure réseau : on patiente puis on réessaie
            last = err
            time.sleep(15 * (attempt + 1))
            continue
        if r.status_code == 429:
            wait, reason = _quota_wait_seconds(r)
            if wait > cfg["max_wait_on_429_s"]:
                raise QuotaExceeded(source, datetime.now(UTC) + timedelta(seconds=wait), reason)
            log(f"{source} : HTTP 429, attente de {wait:.0f} s")
            time.sleep(wait + 2)
            last = "HTTP 429"
            continue
        if 400 <= r.status_code < 500:
            raise ValueError(f"HTTP {r.status_code} : {r.text[:200]}")
        if r.status_code >= 500:                           # service saturé : nouvelle tentative plus tard
            last = f"HTTP {r.status_code}"
            time.sleep(20 * (attempt + 1))
            continue
        return r.content
    raise RuntimeError(f"échec après {cfg['retries']} essais ({last})")


# ------------------------------------------------------------------------------------------- PVGIS
def _chunks() -> list[tuple[int, int]]:
    return [tuple(c) for c in load_params()["ingest"]["pvgis_chunks"]]


def _technologies() -> list[str]:
    return list(load_params()["pv"]["technologies"])


def legacy_hourly_path(city: City) -> Path:
    return LEGACY_RAW / "pvgis" / f"{city.id}_horaire.parquet"


def pvcalc(city: City) -> dict:
    """Synthèse PVcalc : pente optimale et productible annuel d'1 kWc (moyenne de la période)."""
    path = RAW / "pvgis" / city.id / "pvcalc.json"
    legacy = LEGACY_RAW / "pvgis" / f"{city.id}_pvcalc.json"
    if not path.exists() and legacy.exists():
        return json.loads(legacy.read_text(encoding="utf-8"))
    if not path.exists():
        pv = load_params()["pv"]
        content = fetch("pvgis", f"{PVGIS_URL}/PVcalc", {
            "lat": city.lat, "lon": city.lon, "peakpower": pv["peak_power_kwp"], "loss": pv["system_loss_pct"],
            "optimalinclination": 1, "aspect": pv["aspect_deg"], "outputformat": "json"})
        json.loads(content)                                # une réponse illisible ne doit pas entrer dans le cache
        atomic_write(path, content)
    return json.loads(path.read_text(encoding="utf-8"))


def optimal_slope(city: City) -> float:
    return float(pvcalc(city)["inputs"]["mounting_system"]["fixed"]["slope"]["value"])


def series_path(city: City, kind: str, start: int, end: int) -> Path:
    return RAW / "pvgis" / city.id / f"series_{kind}_{start}_{end}.csv.gz"


def pending_series(city: City) -> list[tuple[str, int, int]]:
    """Appels horaires PVGIS encore à faire pour une ville (ni dans le nouveau cache, ni dans celui de la v1)."""
    todo = []
    for kind in [*_technologies(), HORIZONTAL]:
        # La v1 a déjà la série du silicium cristallin et le plan horizontal des 9 villes historiques.
        if kind in (load_params()["pv"]["reference_technology"], HORIZONTAL) and legacy_hourly_path(city).exists():
            continue
        todo += [(kind, a, b) for a, b in _chunks() if not series_path(city, kind, a, b).exists()]
    return todo


def parse_pvgis_csv(content: bytes) -> pd.DataFrame:
    """Bloc de données d'une réponse CSV de PVGIS (entre l'en-tête descriptif et la légende finale)."""
    text = content.decode("utf-8", errors="replace").replace("\r\n", "\n")
    start = text.index("time,")
    end = text.find("\n\n", start)
    table = pd.read_csv(io.StringIO(text[start:end if end > 0 else None]))
    table.index = pd.to_datetime(table.pop("time"), format="%Y%m%d:%H%M")
    return table.rename(columns={"G(i)": "G"})


def download_series(city: City, kind: str, start: int, end: int) -> None:
    pv = load_params()["pv"]
    params = {"lat": city.lat, "lon": city.lon, "startyear": start, "endyear": end, "outputformat": "csv",
              "components": 0}
    if kind == HORIZONTAL:
        params.update(pvcalculation=0, angle=0, aspect=0)
    else:
        params.update(pvcalculation=1, peakpower=pv["peak_power_kwp"], loss=pv["system_loss_pct"],
                      angle=optimal_slope(city), aspect=pv["aspect_deg"], pvtechchoice=kind)
    t0 = time.time()
    content = fetch("pvgis", f"{PVGIS_URL}/seriescalc", params)
    table = parse_pvgis_csv(content)
    # Contrôle avant mise en cache : toutes les heures de la tranche doivent être là.
    expected = len(pd.date_range(f"{start}-01-01", f"{end}-12-31 23:00", freq="h"))
    if len(table) != expected:
        raise ValueError(f"{city.id} {kind} {start}-{end} : {len(table)} heures reçues, {expected} attendues")
    atomic_write(series_path(city, kind, start, end), gzip.compress(content, compresslevel=6))
    log(f"PVGIS {city.id} {kind} {start}-{end} : {len(content) / 1e6:.1f} Mo en {time.time() - t0:.0f} s")


def load_hourly(city: City, kind: str) -> pd.DataFrame | None:
    """Série horaire UTC d'une technologie (P en W, G en W/m², H_sun...) ou du plan horizontal (G)."""
    files = [series_path(city, kind, a, b) for a, b in _chunks()]
    if all(f.exists() for f in files):
        return pd.concat(parse_pvgis_csv(gzip.decompress(f.read_bytes())) for f in files).astype("float32")
    legacy = legacy_hourly_path(city)
    if legacy.exists() and kind == load_params()["pv"]["reference_technology"]:
        h = pd.read_parquet(legacy)
        return pd.DataFrame({"P": h["P"], "G": h["Gb_i"] + h["Gd_i"] + h["Gr_i"], "H_sun": h["H_sun"],
                             "T2m": h["T2m"], "WS10m": h["WS10m"], "Int": h["Int"]})
    if legacy.exists() and kind == HORIZONTAL:
        h = pd.read_parquet(legacy)
        return pd.DataFrame({"G": h["Gb_h"] + h["Gd_h"]})
    return None


# ---------------------------------------------------------------------- Open-Meteo et NASA POWER
def _period() -> tuple[int, int]:
    p = load_params()["period"]
    return p["start_year"], p["end_year"]


def open_meteo_path(city: City) -> Path:
    a, b = _period()
    return RAW / "open_meteo" / city.id / f"daily_{a}_{b}.json"


def has_open_meteo(city: City) -> bool:
    return open_meteo_path(city).exists() or (LEGACY_RAW / "open_meteo" / f"{city.id}.csv").exists()


def download_open_meteo(city: City) -> None:
    a, b = _period()
    content = fetch("open_meteo", OPEN_METEO_URL, {
        "latitude": city.lat, "longitude": city.lon, "start_date": f"{a}-01-01", "end_date": f"{b}-12-31",
        "daily": ",".join(OPEN_METEO_VARIABLES), "timezone": "auto"})
    n = len(json.loads(content)["daily"]["time"])
    atomic_write(open_meteo_path(city), content)
    log(f"Open-Meteo {city.id} : {n} jours")


def load_open_meteo(city: City) -> pd.DataFrame | None:
    """Météo journalière ERA5, colonnes renommées et converties (secondes -> heures, MJ/m² -> kWh/m²)."""
    path, legacy = open_meteo_path(city), LEGACY_RAW / "open_meteo" / f"{city.id}.csv"
    if path.exists():
        d = pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["daily"]).rename(columns={"time": "date"})
    elif legacy.exists():
        d = pd.read_csv(legacy)
    else:
        return None
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").rename(columns=OPEN_METEO_VARIABLES).astype("float64")
    d["ensoleillement_h"] /= 3600
    d["duree_jour_h"] /= 3600
    d["ghi_era5_kwh_m2"] /= 3.6
    return d


def nasa_path(city: City) -> Path:
    a, b = _period()
    return RAW / "nasa_power" / city.id / f"daily_{a}_{b}.json"


def has_nasa(city: City) -> bool:
    return nasa_path(city).exists() or (LEGACY_RAW / "nasa_power" / f"{city.id}.csv").exists()


def download_nasa(city: City) -> None:
    a, b = _period()
    content = fetch("nasa_power", NASA_URL, {
        "parameters": ",".join(NASA_VARIABLES), "community": "RE", "latitude": city.lat, "longitude": city.lon,
        "start": f"{a}0101", "end": f"{b}1231", "format": "JSON"})
    n = len(json.loads(content)["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"])
    atomic_write(nasa_path(city), content)
    log(f"NASA POWER {city.id} : {n} jours")


def load_nasa(city: City) -> pd.DataFrame | None:
    """Rayonnement, clarté et aérosols journaliers ; -999 est la valeur de remplissage de NASA POWER."""
    path, legacy = nasa_path(city), LEGACY_RAW / "nasa_power" / f"{city.id}.csv"
    if path.exists():
        d = pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["properties"]["parameter"])
        d.index = pd.to_datetime(d.index, format="%Y%m%d")
    elif legacy.exists():
        d = pd.read_csv(legacy, parse_dates=["date"]).set_index("date")
    else:
        return None
    d.index.name = "date"
    return d.rename(columns=NASA_VARIABLES).astype("float64").replace(-999.0, np.nan)


# ------------------------------------------------------------------------------------ orchestration
def source_status(city: City) -> dict[str, bool]:
    """Sources complètes pour une ville : sert à la reprise et au panel partiel."""
    return {"pvgis": not pending_series(city), "open_meteo": has_open_meteo(city), "nasa_power": has_nasa(city)}


def is_complete(city: City) -> bool:
    return all(source_status(city).values())


def _record(failures: list[dict], city: str, source: str, call: str, err: Exception) -> None:
    entry = {"ville": city, "source": source, "appel": call, "erreur": str(err)[:300],
             "date": datetime.now(UTC).isoformat(timespec="seconds")}
    if isinstance(err, QuotaExceeded):
        entry["reprise_possible_utc"] = err.resume_at.isoformat(timespec="seconds")
    failures.append(entry)
    log(f"ÉCHEC {source} {city} {call} : {entry['erreur']}")


def run_downloads(cities: list[City]) -> list[dict]:
    """Télécharge ce qui manque. Les trois sources avancent en parallèle : seul PVGIS est volumineux."""
    cfg = load_params()["ingest"]
    failures: list[dict] = []

    def open_meteo_worker() -> None:
        todo = [c for c in cities if not has_open_meteo(c)]
        for i, city in enumerate(todo):
            try:
                download_open_meteo(city)
            except QuotaExceeded as err:                   # inutile d'insister : les villes suivantes échoueraient aussi
                for rest in todo[i:]:
                    _record(failures, rest.id, "open_meteo", "daily", err)
                return
            except Exception as err:                       # noqa: BLE001 - une ville en échec ne bloque pas les autres
                _record(failures, city.id, "open_meteo", "daily", err)
            if i < len(todo) - 1:
                time.sleep(cfg["open_meteo_pause_s"])

    def nasa_worker() -> None:
        for city in [c for c in cities if not has_nasa(c)]:
            try:
                download_nasa(city)
            except Exception as err:                       # noqa: BLE001
                _record(failures, city.id, "nasa_power", "daily", err)
            time.sleep(cfg["nasa_pause_s"])

    def pvgis_task(task: tuple[City, str, int, int]) -> None:
        city, kind, a, b = task
        try:
            download_series(city, kind, a, b)
        except Exception as err:                           # noqa: BLE001
            _record(failures, city.id, "pvgis", f"{kind} {a}-{b}", err)

    side = [threading.Thread(target=open_meteo_worker, daemon=True), threading.Thread(target=nasa_worker, daemon=True)]
    for t in side:
        t.start()
    # La pente optimale (PVcalc) est nécessaire avant les séries horaires : appels courts, faits d'abord.
    ready = []
    for city in cities:
        try:
            optimal_slope(city)
            ready.append(city)
        except Exception as err:                           # noqa: BLE001
            _record(failures, city.id, "pvgis", "PVcalc", err)
    tasks = [(c, kind, a, b) for c in ready for kind, a, b in pending_series(c)]
    log(f"PVGIS : {len(tasks)} appels horaires à faire pour {len(ready)} villes")
    with ThreadPoolExecutor(max_workers=cfg["pvgis_workers"]) as pool:
        list(pool.map(pvgis_task, tasks))
    for t in side:
        t.join()
    # Le journal garde les échecs des villes que cette exécution n'a pas retentées : lancer la collecte sur
    # trois villes ne doit pas effacer les échecs des autres. Une ville devenue complète en sort.
    previous = json.loads(FAILURES.read_text(encoding="utf-8")) if FAILURES.exists() else []
    merged = merge_failures(previous, failures, {c.id for c in cities}, {c.id for c in cities if is_complete(c)})
    atomic_write(FAILURES, json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8"))
    log(f"Téléchargements terminés : {len(failures)} échec(s) dans cette exécution, {len(merged)} au journal (data/failures.json)")
    return failures


def merge_failures(previous: list[dict], new: list[dict], attempted: set[str], complete: set[str]) -> list[dict]:
    """Journal des échecs après une exécution : anciens échecs des villes non retentées, plus les nouveaux."""
    return [f for f in previous if f["ville"] not in attempted] + [f for f in new if f["ville"] not in complete]


def failed_city_ids() -> list[str]:
    """Villes citées dans data/failures.json (option --retry-failed)."""
    if not FAILURES.exists():
        return []
    return sorted({f["ville"] for f in json.loads(FAILURES.read_text(encoding="utf-8"))})
