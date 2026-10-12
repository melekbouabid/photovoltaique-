"""Collecte des données : des liens du rapport SolarVision aux jeux de données du mini-projet.

Étapes (chaque téléchargement est mis en cache dans data/brut/, une relance ne refait que ce qui manque) :
1. Lecture des hyperliens du PDF « Rapport_SolarVision_MLOps_complet.pdf » et classement
   (source de séries temporelles, article, jeu d'images, documentation). Chaque lien est visité ;
   le résultat est archivé dans sources/liens_rapport_solarvision.json.
2. Le seul lien qui donne accès à des séries temporelles est PVGIS (re.jrc.ec.europa.eu/pvg_tools).
   Son API fournit, pour 9 villes (3 par pays) et 2005-2023 : la production PV horaire d'une
   installation de 1 kWc, l'éclairement horaire sur le plan des modules et sur le plan horizontal,
   la température et le vent (ERA5), la synthèse annuelle (PVcalc) et l'année météo type (TMY).
3. Variables exogènes complémentaires, indispensables pour la nébulosité, l'humidité ou les aérosols
   que PVGIS ne fournit pas : Open-Meteo (réanalyse ERA5) et NASA POWER (MERRA-2, CERES).
4. Séries mesurées sur les réseaux électriques, pour une validation externe : production solaire
   nationale de la France (RTE éCO2mix, portail ODRÉ) et de l'Espagne (REE, apidatos).
5. Agrégation journalière, construction de plus de 50 variables et écriture de 14 jeux de données,
   d'un catalogue (data/catalogue_datasets.json) et des fiches descriptives (data/LISEZMOI_donnees.md).

Usage : python python/collecte_donnees.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RACINE = Path(__file__).resolve().parents[1]
DATA, SOURCES = RACINE / "data", RACINE / "sources"
BRUT, JEUX = DATA / "brut", DATA / "datasets"
PDF_SOLARVISION = SOURCES / "Rapport_SolarVision_MLOps_complet.pdf"

AN_DEBUT, AN_FIN = 2005, 2023            # période couverte par la base de rayonnement PVGIS-SARAH3
TRANCHES = [(2005, 2009), (2010, 2014), (2015, 2019), (2020, 2023)]   # une réponse de 19 ans dépasse 20 Mo
PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3"
PERTES_SYSTEME = 14                      # % de pertes (câbles, onduleur, salissures) : valeur par défaut de PVGIS
# Efficacités lumineuses moyennes (lm/W) du rayonnement direct et diffus : elles convertissent
# l'éclairement énergétique (W/m²) en éclairement lumineux (lux). Ordres de grandeur de la littérature
# (Littlefair, 1985 ; Perez et al., 1990) : approximation suffisante pour un indicateur journalier.
EFFICACITE_DIRECT, EFFICACITE_DIFFUS = 100.0, 125.0
SEUIL_LUX = 10_000                       # au-dessus, la lumière du jour suffit à éclairer un local (FLJ ≈ 2 %)
FIN_CLIMATOLOGIE = "2020-12-31"          # normales calculées sur 2005-2020, à l'intérieur de tout échantillon d'apprentissage
ENTETE = {"User-Agent": "SolarVision-TS/1.0 (mini-projet universitaire de series temporelles)"}

# Trois villes par pays, choisies pour couvrir chaque gradient de climat (nord-sud, côte-intérieur).
SITES = {
    "paris": {"ville": "Paris", "pays": "France", "code_pays": "FR", "lat": 48.8566, "lon": 2.3522},
    "lyon": {"ville": "Lyon", "pays": "France", "code_pays": "FR", "lat": 45.7640, "lon": 4.8357},
    "marseille": {"ville": "Marseille", "pays": "France", "code_pays": "FR", "lat": 43.2965, "lon": 5.3698},
    "tunis": {"ville": "Tunis", "pays": "Tunisie", "code_pays": "TN", "lat": 36.8065, "lon": 10.1815},
    "sfax": {"ville": "Sfax", "pays": "Tunisie", "code_pays": "TN", "lat": 34.7406, "lon": 10.7603},
    "tozeur": {"ville": "Tozeur", "pays": "Tunisie", "code_pays": "TN", "lat": 33.9197, "lon": 8.1335},
    "madrid": {"ville": "Madrid", "pays": "Espagne", "code_pays": "ES", "lat": 40.4168, "lon": -3.7038},
    "seville": {"ville": "Séville", "pays": "Espagne", "code_pays": "ES", "lat": 37.3891, "lon": -5.9845},
    "barcelone": {"ville": "Barcelone", "pays": "Espagne", "code_pays": "ES", "lat": 41.3874, "lon": 2.1686},
}
PAYS = {"FR": "France", "TN": "Tunisie", "ES": "Espagne"}

OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
# Dix variables au plus : au-delà, Open-Meteo compte la requête comme plusieurs appels (quota gratuit).
OPEN_METEO_VARIABLES = {
    "cloud_cover_mean": "nebulosite_pct", "sunshine_duration": "ensoleillement_h",
    "daylight_duration": "duree_jour_h", "precipitation_sum": "precipitation_mm",
    "relative_humidity_2m_mean": "humidite_pct", "dew_point_2m_mean": "point_rosee_c",
    "pressure_msl_mean": "pression_hpa", "wind_gusts_10m_max": "rafales_max_kmh",
    "et0_fao_evapotranspiration": "et0_mm", "shortwave_radiation_sum": "ghi_era5_kwh_m2",
}
NASA_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_VARIABLES = {
    "ALLSKY_SFC_SW_DWN": "ghi_nasa_kwh_m2", "CLRSKY_SFC_SW_DWN": "ghi_ciel_clair_kwh_m2",
    "ALLSKY_KT": "indice_clarte", "TOA_SW_DWN": "rayonnement_toa_kwh_m2", "CLOUD_AMT": "nebulosite_nasa_pct",
    "AOD_55": "aerosols_aod", "ALLSKY_SFC_UV_INDEX": "indice_uv", "ALLSKY_SRF_ALB": "albedo",
    "ALLSKY_SFC_PAR_TOT": "par_kwh_m2",
}
ODRE_RTE = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-cons-def/exports/csv"
REE_BALANCE = "https://apidatos.ree.es/es/datos/balance/balance-electrico"


# ------------------------------------------------------------------------------------------- outils
def obtenir(url, params=None, essais=5, delai=15, timeout=600):
    """GET avec reprises : les API publiques coupent parfois la connexion ou limitent le débit (code 429)."""
    dernier = None
    for k in range(essais):
        try:
            r = requests.get(url, params=params, headers=ENTETE, timeout=timeout)
            if r.status_code == 429:                  # quota momentanément dépassé : on patiente puis on réessaie
                time.sleep(70 * (k + 1))
                dernier = "HTTP 429"
                continue
            if 400 <= r.status_code < 500:            # requête invalide : inutile d'insister
                raise ValueError(f"HTTP {r.status_code} : {r.text[:300]}")
            r.raise_for_status()
            return r
        except (requests.RequestException, json.JSONDecodeError) as err:
            dernier = err
            time.sleep(delai * (k + 1))
    raise RuntimeError(f"échec après {essais} essais : {url} ({dernier})")


def journal(*args):
    print(*args, flush=True)


# ------------------------------------------------------------------- 1. liens du rapport SolarVision
def extraire_liens(pdf: Path) -> list[dict]:
    """Hyperliens cliquables du PDF (annotations /URI), dans l'ordre d'apparition, sans doublon."""
    from pypdf import PdfReader
    vus, liens = set(), []
    for num, page in enumerate(PdfReader(pdf).pages, start=1):
        for annot in page.get("/Annots") or []:
            action = annot.get_object().get("/A")
            url = action.get("/URI") if action else None
            if url and url not in vus:
                vus.add(url)
                liens.append({"page": num, "url": str(url)})
    return liens


def classer(url: str) -> str:
    if "re.jrc.ec.europa.eu/pvg_tools" in url:
        return "série temporelle"
    if any(s in url for s in ("arxiv.org", "nature.com", "papers.nips.cc", "pmc.ncbi")):
        return "article"
    if any(s in url for s in ("inria", "figshare", "whu.edu", "spacenet", "huggingface.co/datasets")):
        return "jeu d'images"
    return "documentation"


def titre_page(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def meta_description(html: str) -> str:
    m = re.search(r'<meta[^>]+name="(?:description|dc\.description|citation_abstract)"[^>]+content="([^"]+)"', html, re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def visiter_liens(liens: list[dict]) -> list[dict]:
    """Visite chaque lien et garde ce qui est utile au projet (métadonnées, résumés d'articles).

    Les jeux d'images (dizaines de Go) ne sont pas téléchargés : ce ne sont pas des séries
    temporelles. Les résumés des articles alimentent le corpus du RAG.
    """
    arxiv_ids = [re.search(r"arxiv\.org/(?:pdf|abs)/([\d.]+)", l["url"]).group(1)
                 for l in liens if "arxiv.org" in l["url"]]
    resumes_arxiv = {}
    if arxiv_ids:
        try:
            r = obtenir("http://export.arxiv.org/api/query",
                        {"id_list": ",".join(arxiv_ids), "max_results": len(arxiv_ids)}, essais=3)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for e in ET.fromstring(r.content).findall("a:entry", ns):
                ident = e.find("a:id", ns).text.rsplit("/", 1)[-1].split("v")[0]
                resumes_arxiv[ident] = {
                    "titre": re.sub(r"\s+", " ", e.find("a:title", ns).text).strip(),
                    "auteurs": ", ".join(a.find("a:name", ns).text for a in e.findall("a:author", ns)),
                    "date": e.find("a:published", ns).text[:10],
                    "resume": re.sub(r"\s+", " ", e.find("a:summary", ns).text).strip()}
        except Exception as err:          # noqa: BLE001 - un échec d'arXiv ne doit pas bloquer la collecte
            journal("  arXiv indisponible :", err)

    sortie = []
    for l in liens:
        url, cat = l["url"], classer(l["url"])
        fiche = {**l, "categorie": cat, "statut": "", "titre": "", "resume": "", "usage": ""}
        try:
            if "arxiv.org" in url:
                ident = re.search(r"arxiv\.org/(?:pdf|abs)/([\d.]+)", url).group(1)
                info = resumes_arxiv.get(ident)
                fiche.update(info or {}, statut="résumé arXiv" if info else "non trouvé")
                fiche["usage"] = "corpus du RAG (résumé)"
            elif url.endswith(".pdf"):
                r = obtenir(url, essais=2, timeout=120)
                if r.content[:4] == b"%PDF":
                    from pypdf import PdfReader
                    import io
                    texte = PdfReader(io.BytesIO(r.content)).pages[0].extract_text() or ""
                    fiche.update(statut=f"PDF {len(r.content) // 1024} ko", titre=texte.strip().splitlines()[0][:200],
                                 resume=re.sub(r"\s+", " ", texte)[:2500], usage="corpus du RAG (première page)")
                else:                     # l'éditeur renvoie une page HTML : on lit la page de l'article
                    r = obtenir(url[:-4], essais=2, timeout=60)
                    fiche.update(statut=f"page de l'article (HTTP {r.status_code})", titre=titre_page(r.text),
                                 resume=meta_description(r.text), usage="corpus du RAG (résumé)")
            elif "figshare.com/collections" in url:
                col = re.search(r"/(\d+)$", url.rstrip("/")).group(1)
                arts = obtenir(f"https://api.figshare.com/v2/collections/{col}/articles", {"page_size": 100}, essais=2).json()
                fiche.update(statut=f"{len(arts)} articles figshare", titre="Bradbury et al. (2016), panneaux PV (Californie)",
                             resume="; ".join(a["title"] for a in arts[:8]),
                             usage="métadonnées seulement : images aériennes, pas une série temporelle")
            elif "huggingface.co/datasets" in url:
                depot = url.split("huggingface.co/datasets/")[1].strip("/")
                info = obtenir(f"https://huggingface.co/api/datasets/{depot}", essais=2).json()
                fiche.update(statut="métadonnées Hugging Face", titre=info.get("id", depot),
                             resume=f"{len(info.get('siblings', []))} fichiers ; téléchargements : {info.get('downloads')}",
                             usage="métadonnées seulement : images aériennes, pas une série temporelle")
            else:
                r = obtenir(url, essais=2, timeout=60)
                fiche.update(statut=f"HTTP {r.status_code}", titre=titre_page(r.text), resume=meta_description(r.text))
                if cat == "série temporelle":
                    fiche["usage"] = "API PVGIS : production PV, éclairement, température, vent (2005-2023), 9 villes"
                elif cat == "article":
                    fiche["usage"] = "corpus du RAG (résumé)"
                elif cat == "jeu d'images":
                    fiche["usage"] = "métadonnées seulement : images, pas une série temporelle"
                else:
                    fiche["usage"] = "documentation logicielle (hors périmètre séries temporelles)"
        except Exception as err:          # noqa: BLE001 - on archive l'échec et on continue
            fiche["statut"] = f"échec : {str(err)[:150]}"
        sortie.append(fiche)
        journal(f"  [{cat:16s}] {fiche['statut'][:30]:30s} {url[:80]}")
    return sortie


# ------------------------------------------------------------------------------------ 2. PVGIS
def pvgis_synthese(site: str) -> dict:
    """PVcalc : inclinaison optimale, productible annuel et mensuel d'1 kWc (moyenne 2005-2023)."""
    f = BRUT / "pvgis" / f"{site}_pvcalc.json"
    if not f.exists():
        s = SITES[site]
        r = obtenir(f"{PVGIS}/PVcalc", {"lat": s["lat"], "lon": s["lon"], "peakpower": 1, "loss": PERTES_SYSTEME,
                                        "optimalinclination": 1, "aspect": 0, "outputformat": "json"})
        f.write_text(r.text, encoding="utf-8")
    return json.loads(f.read_text(encoding="utf-8"))


def _horaire(js: dict) -> pd.DataFrame:
    h = pd.DataFrame(js["outputs"]["hourly"])
    h.index = pd.to_datetime(h.pop("time"), format="%Y%m%d:%H%M")
    return h


def pvgis_horaire(site: str, pente: float) -> pd.DataFrame:
    """Série horaire 2005-2023 : plan des modules (pente optimale, plein sud) et plan horizontal.

    Deux appels par tranche d'années : le premier simule l'installation (puissance P et éclairement
    sur le plan incliné), le second donne l'éclairement horizontal, base de l'éclairement lumineux.
    """
    f = BRUT / "pvgis" / f"{site}_horaire.parquet"
    if f.exists():
        return pd.read_parquet(f)
    s = SITES[site]
    commun = {"lat": s["lat"], "lon": s["lon"], "components": 1, "outputformat": "json"}
    morceaux = []
    for a0, a1 in TRANCHES:
        incl = _horaire(obtenir(f"{PVGIS}/seriescalc", {**commun, "startyear": a0, "endyear": a1, "pvcalculation": 1,
                                                        "peakpower": 1, "loss": PERTES_SYSTEME, "angle": pente,
                                                        "aspect": 0}).json())
        hori = _horaire(obtenir(f"{PVGIS}/seriescalc", {**commun, "startyear": a0, "endyear": a1, "pvcalculation": 0,
                                                        "angle": 0, "aspect": 0}).json())
        if not incl.index.equals(hori.index):
            raise ValueError(f"{site} {a0}-{a1} : horodatages différents entre les deux appels PVGIS")
        morceaux.append(pd.DataFrame({
            "P": incl["P"], "Gb_i": incl["Gb(i)"], "Gd_i": incl["Gd(i)"], "Gr_i": incl["Gr(i)"],
            "Gb_h": hori["Gb(i)"], "Gd_h": hori["Gd(i)"], "H_sun": incl["H_sun"], "T2m": incl["T2m"],
            "WS10m": incl["WS10m"], "Int": incl["Int"]}))
        journal(f"  PVGIS {site} {a0}-{a1} : {len(incl)} heures")
    h = pd.concat(morceaux).astype("float32")
    h.index.name = "heure_utc"
    h.to_parquet(f)
    return h


# Scénarios d'installation : inclinaisons et orientations d'une toiture ou d'une façade (0° = plein sud,
# -90° = est, +90° = ouest, convention PVGIS). C'est la question d'un architecte, utilisateur visé par SolarVision.
INCLINAISONS = [15, 30, 45, 60, 90]
AZIMUTS = {-90: "est", -45: "sud-est", 0: "sud", 45: "sud-ouest", 90: "ouest"}


def pvgis_scenario(site: str, angle: float, aspect: float) -> dict:
    """PVcalc pour une inclinaison et une orientation données (moyennes mensuelles 2005-2023)."""
    f = BRUT / "pvgis" / "scenarios" / f"{site}_{angle:g}_{aspect:g}.json"
    if not f.exists():
        s = SITES[site]
        r = obtenir(f"{PVGIS}/PVcalc", {"lat": s["lat"], "lon": s["lon"], "peakpower": 1, "loss": PERTES_SYSTEME,
                                        "angle": angle, "aspect": aspect, "outputformat": "json"})
        f.write_text(r.text, encoding="utf-8")
    return json.loads(f.read_text(encoding="utf-8"))


def pvgis_tmy(site: str) -> pd.DataFrame:
    """Année météorologique type (8 760 heures représentatives de 2005-2023)."""
    f = BRUT / "pvgis" / f"{site}_tmy.json"
    if not f.exists():
        s = SITES[site]
        f.write_text(obtenir(f"{PVGIS}/tmy", {"lat": s["lat"], "lon": s["lon"], "outputformat": "json"}).text,
                     encoding="utf-8")
    js = json.loads(f.read_text(encoding="utf-8"))
    t = pd.DataFrame(js["outputs"]["tmy_hourly"])
    t.insert(0, "site", site)
    return t


# --------------------------------------------------------------------- 3. variables exogènes
def open_meteo(site: str) -> pd.DataFrame:
    f = BRUT / "open_meteo" / f"{site}.csv"
    if not f.exists():
        s = SITES[site]
        r = obtenir(OPEN_METEO, {"latitude": s["lat"], "longitude": s["lon"], "start_date": f"{AN_DEBUT}-01-01",
                                 "end_date": f"{AN_FIN}-12-31", "daily": ",".join(OPEN_METEO_VARIABLES),
                                 "timezone": "auto"})
        d = pd.DataFrame(r.json()["daily"]).rename(columns={"time": "date"})
        d.to_csv(f, index=False)
        journal(f"  Open-Meteo {site} : {len(d)} jours")
        time.sleep(65)                    # quota gratuit : environ 500 « appels pondérés » par requête
    d = pd.read_csv(f, parse_dates=["date"]).set_index("date").rename(columns=OPEN_METEO_VARIABLES)
    # Conversions d'unités : secondes -> heures, MJ/m² -> kWh/m².
    d["ensoleillement_h"] /= 3600
    d["duree_jour_h"] /= 3600
    d["ghi_era5_kwh_m2"] /= 3.6
    return d


def nasa_power(site: str) -> pd.DataFrame:
    f = BRUT / "nasa_power" / f"{site}.csv"
    if not f.exists():
        s = SITES[site]
        r = obtenir(NASA_POWER, {"parameters": ",".join(NASA_VARIABLES), "community": "RE", "latitude": s["lat"],
                                 "longitude": s["lon"], "start": f"{AN_DEBUT}0101", "end": f"{AN_FIN}1231",
                                 "format": "JSON"})
        par = r.json()["properties"]["parameter"]
        d = pd.DataFrame(par)
        d.index = pd.to_datetime(d.index, format="%Y%m%d")
        d.rename_axis("date").to_csv(f)
        journal(f"  NASA POWER {site} : {len(d)} jours")
    d = pd.read_csv(f, parse_dates=["date"]).set_index("date").rename(columns=NASA_VARIABLES)
    return d.replace(-999.0, np.nan)      # valeur de remplissage de NASA POWER pour une donnée manquante


# Météo horaire ERA5 (heure UTC, comme PVGIS) : nuages par étage, humidité, pluie, pression, rayonnement.
OPEN_METEO_HORAIRE = {
    "cloud_cover": "nebulosite_pct", "cloud_cover_low": "nebulosite_basse_pct", "cloud_cover_mid": "nebulosite_moyenne_pct",
    "cloud_cover_high": "nebulosite_haute_pct", "relative_humidity_2m": "humidite_pct", "precipitation": "precipitation_mm",
    "wind_direction_10m": "direction_vent_deg", "surface_pressure": "pression_surface_hpa",
    "shortwave_radiation": "ghi_era5_w_m2", "direct_normal_irradiance": "dni_era5_w_m2",
    "diffuse_radiation": "dhi_era5_w_m2", "apparent_temperature": "temperature_ressentie_c",
}


def open_meteo_horaire(site: str, an: int = AN_FIN) -> pd.DataFrame:
    f = BRUT / "open_meteo" / f"{site}_horaire_{an}.csv"
    if not f.exists():
        s = SITES[site]
        r = obtenir(OPEN_METEO, {"latitude": s["lat"], "longitude": s["lon"], "start_date": f"{an}-01-01",
                                 "end_date": f"{an}-12-31", "hourly": ",".join(OPEN_METEO_HORAIRE), "timezone": "GMT"})
        pd.DataFrame(r.json()["hourly"]).rename(columns={"time": "heure_utc"}).to_csv(f, index=False)
        journal(f"  Open-Meteo horaire {site} {an}")
        time.sleep(3)
    d = pd.read_csv(f, parse_dates=["heure_utc"]).set_index("heure_utc")
    return d.rename(columns=OPEN_METEO_HORAIRE)


def hauteur_soleil(heures_utc: pd.DatetimeIndex, lat: float, lon: float) -> np.ndarray:
    """Hauteur du soleil (degrés) à des instants UTC : déclinaison de Cooper, équation du temps de Spencer."""
    j = heures_utc.dayofyear.to_numpy()
    b = 2 * np.pi * (j - 1) / 365
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(b) - 0.032077 * np.sin(b) - 0.014615 * np.cos(2 * b)
                    - 0.040849 * np.sin(2 * b))                       # minutes
    heure = heures_utc.hour.to_numpy() + heures_utc.minute.to_numpy() / 60
    t_solaire = heure + lon / 15 + eot / 60
    omega = np.radians(15 * (t_solaire - 12))
    decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + j) / 365)
    phi = np.radians(lat)
    return np.degrees(np.arcsin(np.clip(np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(omega), -1, 1)))


# ------------------------------------------------------------------- 4. séries mesurées (réseaux)
# Champs du mix électrique éCO2mix retenus (puissances moyennes en MW au pas de 30 min, taux de CO2 en g/kWh).
RTE_CHAMPS = ["consommation", "prevision_j1", "nucleaire", "eolien", "solaire", "hydraulique", "gaz", "charbon",
              "fioul", "bioenergies", "pompage", "ech_physiques", "taux_co2", "ech_comm_espagne", "ech_comm_italie",
              "ech_comm_angleterre", "ech_comm_suisse", "gaz_ccg", "hydraulique_fil_eau_eclusee", "hydraulique_lacs",
              "hydraulique_step_turbinage", "bioenergies_biomasse"]
RTE_ENERGIES = [c for c in RTE_CHAMPS if c not in ("taux_co2", "prevision_j1", "solaire")]


def calendrier(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Variables de calendrier communes aux séries nationales (la consommation dépend du jour de la semaine)."""
    j = index.dayofyear.to_numpy()
    return pd.DataFrame({"jour_semaine": index.dayofweek, "week_end": (index.dayofweek >= 5).astype(int),
                         "mois": index.month, "jds_sin": np.sin(2 * np.pi * j / 365.25),
                         "jds_cos": np.cos(2 * np.pi * j / 365.25)}, index=index)


def rte_mix() -> pd.DataFrame:
    """Mix électrique national français (RTE éCO2mix), pas de 30 min de 2012 à fin août 2026, agrégé par jour.

    La production solaire est l'objet principal ; le reste du mix (nucléaire, éolien, hydraulique...), la
    consommation, sa prévision à J-1, le taux de CO2 et les échanges décrivent le système qui l'absorbe.
    """
    f = BRUT / "reseaux" / "rte_eco2mix_mix_30min.csv"
    if not f.exists():
        r = obtenir(ODRE_RTE, {"select": ",".join(["date", "heure", "nature"] + RTE_CHAMPS),
                               "where": "solaire is not null", "order_by": "date_heure"}, timeout=1200)
        f.write_bytes(r.content)
    b = pd.read_csv(f, sep=";", encoding="utf-8-sig", low_memory=False)
    for c in RTE_CHAMPS:                    # certains champs sont publiés comme du texte
        b[c] = pd.to_numeric(b[c], errors="coerce")
    g = b.groupby("date")
    moy = g[RTE_CHAMPS].mean()
    j = pd.DataFrame(index=pd.to_datetime(moy.index))
    j.index.name = "date"
    v = lambda c: moy[c].to_numpy()
    j["production_gwh"] = v("solaire") * 24 / 1000                   # moyenne des points (MW) x 24 h
    j["puissance_moyenne_mw"] = v("solaire")
    j["puissance_max_mw"] = g["solaire"].max().to_numpy()
    j["facteur_forme_solaire"] = j["puissance_moyenne_mw"] / j["puissance_max_mw"]   # journée régulière ou hachée
    for c in RTE_ENERGIES:
        j[f"{c}_gwh"] = v(c) * 24 / 1000
    j["taux_co2_g_kwh"] = v("taux_co2")
    j["part_solaire_conso_pct"] = 100 * v("solaire") / v("consommation")
    j["part_renouvelable_conso_pct"] = 100 * (v("solaire") + v("eolien") + v("hydraulique") + v("bioenergies")) / v("consommation")
    j["erreur_prevision_j1_pct"] = 100 * (v("prevision_j1") - v("consommation")) / v("consommation")
    j["n_points"] = g.size().to_numpy()
    j["nature"] = g["nature"].first().to_numpy()
    return j.join(calendrier(j.index)).sort_index()


def _nom_ree(titre: str) -> str:
    """« Solar fotovoltaica » -> « solar_fotovoltaica » (noms de colonnes sans accents)."""
    t = unicodedata.normalize("NFKD", titre.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def ree_balance() -> pd.DataFrame:
    """Bilan électrique journalier du système péninsulaire espagnol (REE, apidatos), 2014 à octobre 2026.

    Toutes les filières (renouvelables, non renouvelables), le stockage (pompage, batteries), les
    échanges et la demande, en GWh par jour ; réponses brutes conservées année par année.
    """
    lignes = {}
    for an in range(2014, 2027):
        f = BRUT / "reseaux" / f"ree_balance_{an}.json"
        if not f.exists():
            fin = f"{an}-12-31T23:59" if an < 2026 else "2026-10-09T23:59"
            try:
                r = obtenir(REE_BALANCE, {"start_date": f"{an}-01-01T00:00", "end_date": fin, "time_trunc": "day",
                                          "geo_trunc": "electric_system", "geo_limit": "peninsular", "geo_ids": 8741},
                            essais=3)
            except Exception as err:      # noqa: BLE001 - une année manquante ne bloque pas les autres
                journal(f"  REE {an} : {err}")
                continue
            f.write_text(r.text, encoding="utf-8")
            time.sleep(1)
        for groupe in json.loads(f.read_text(encoding="utf-8")).get("included", []):
            for serie in groupe["attributes"].get("content", []):
                nom = _nom_ree(serie["attributes"]["title"])
                for val in serie["attributes"]["values"]:
                    lignes.setdefault(val["datetime"][:10], {})[nom] = val["value"] / 1000   # MWh -> GWh
    d = pd.DataFrame.from_dict(lignes, orient="index").sort_index()
    d.index = pd.to_datetime(d.index)
    d.index.name = "date"
    d = d.rename(columns=lambda c: f"{c}_gwh")
    d["produccion_gwh"] = d["solar_fotovoltaica_gwh"]               # nom conservé pour les notebooks
    tot = d["generacion_renovable_gwh"] + d["generacion_no_renovable_gwh"]
    d["part_fotovoltaica_generacion_pct"] = 100 * d["solar_fotovoltaica_gwh"] / tot
    d["part_renovable_generacion_pct"] = 100 * d["generacion_renovable_gwh"] / tot
    d["part_fotovoltaica_demanda_pct"] = 100 * d["solar_fotovoltaica_gwh"] / d["demanda_en_b_c_gwh"]
    return d.join(calendrier(d.index))


# ---------------------------------------------------------------- 5. variables et jeux de données
def astronomie(dates: pd.DatetimeIndex, lat: float) -> pd.DataFrame:
    """Grandeurs astronomiques connues à l'avance pour toute date : elles servent de variables « ex ante ».

    Rayonnement extraterrestre journalier sur plan horizontal (Duffie et Beckman, éq. 1.10.3),
    durée astronomique du jour et hauteur du soleil à midi solaire.
    """
    j = dates.dayofyear.to_numpy()
    phi = np.radians(lat)
    decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + j) / 365)          # déclinaison (Cooper, 1969)
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)                             # excentricité de l'orbite
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(decl), -1, 1))              # angle horaire du coucher
    h0 = 24 / np.pi * 1.367 * dr * (ws * np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.sin(ws))
    return pd.DataFrame({"irr_extraterrestre_kwh_m2": h0, "duree_jour_astro_h": 24 / np.pi * ws,
                         "hauteur_soleil_midi_deg": 90 - np.degrees(np.abs(phi - decl)),
                         "jour_annee": j, "jds_sin": np.sin(2 * np.pi * j / 365.25),
                         "jds_cos": np.cos(2 * np.pi * j / 365.25), "mois": dates.month}, index=dates)


def agreger_jour(h: pd.DataFrame) -> pd.DataFrame:
    """Passage de l'horaire au journalier (jour UTC : à ces longitudes, aucune heure de soleil n'est
    coupée par minuit UTC, les sommes d'énergie sont donc exactes)."""
    g_poa = h["Gb_i"] + h["Gd_i"] + h["Gr_i"]
    lux = EFFICACITE_DIRECT * h["Gb_h"] + EFFICACITE_DIFFUS * h["Gd_h"]
    jour = h["H_sun"] > 0
    aux = pd.DataFrame({
        "pv": h["P"], "prod": (h["P"] > 0).astype(int), "poa": g_poa, "gb_i": h["Gb_i"], "gd_i": h["Gd_i"],
        "gr_i": h["Gr_i"], "gb_h": h["Gb_h"], "gd_h": h["Gd_h"], "lux": lux, "lux_ok": (lux >= SEUIL_LUX).astype(int),
        "hsun": h["H_sun"], "t2m": h["T2m"], "t2m_jour": h["T2m"].where(jour), "ws": h["WS10m"], "int": h["Int"]})
    g = aux.groupby(aux.index.floor("D"))
    d = pd.DataFrame({
        "pv_kwh_kwc": g["pv"].sum() / 1000, "pv_pic_w_kwc": g["pv"].max(), "heures_production": g["prod"].sum(),
        "irr_poa_kwh_m2": g["poa"].sum() / 1000, "irr_poa_direct_kwh_m2": g["gb_i"].sum() / 1000,
        "irr_poa_diffus_kwh_m2": g["gd_i"].sum() / 1000, "irr_poa_reflechi_kwh_m2": g["gr_i"].sum() / 1000,
        "ghi_kwh_m2": (g["gb_h"].sum() + g["gd_h"].sum()) / 1000, "bhi_kwh_m2": g["gb_h"].sum() / 1000,
        "dhi_kwh_m2": g["gd_h"].sum() / 1000, "eclairement_max_klux": g["lux"].max() / 1000,
        "heures_lumiere_10klux": g["lux_ok"].sum(), "dose_lumineuse_klux_h": g["lux"].sum() / 1000,
        "hauteur_soleil_max_deg": g["hsun"].max(), "t2m_moy_c": g["t2m"].mean(), "t2m_max_c": g["t2m"].max(),
        "t2m_min_c": g["t2m"].min(), "t2m_jour_c": g["t2m_jour"].mean(), "vent_moy_ms": g["ws"].mean(),
        "heures_reconstruites": g["int"].sum()})
    d.index.name = "date"
    d["fraction_diffuse_poa"] = (d["irr_poa_diffus_kwh_m2"] / d["irr_poa_kwh_m2"]).where(d["irr_poa_kwh_m2"] > 0.05)
    d["ratio_performance"] = (d["pv_kwh_kwc"] / d["irr_poa_kwh_m2"]).where(d["irr_poa_kwh_m2"] > 0.05)
    d["amplitude_thermique_c"] = d["t2m_max_c"] - d["t2m_min_c"]
    d["besoin_eclairage_h"] = 24 - d["heures_lumiere_10klux"]
    return d.astype("float64")             # le cache horaire est en float32 ; on calcule ensuite en double précision


ENERGIES_PVGIS = ["pv_kwh_kwc", "irr_poa_kwh_m2", "irr_poa_direct_kwh_m2", "irr_poa_diffus_kwh_m2",
                  "irr_poa_reflechi_kwh_m2", "ghi_kwh_m2", "bhi_kwh_m2", "dhi_kwh_m2", "dose_lumineuse_klux_h"]
INTENSIVES_PVGIS = ["pv_pic_w_kwc", "heures_production", "eclairement_max_klux", "heures_lumiere_10klux",
                    "hauteur_soleil_max_deg", "t2m_jour_c", "fraction_diffuse_poa", "ratio_performance"]


def corriger_trous_pvgis(d: pd.DataFrame) -> pd.DataFrame:
    """Jours où la base satellitaire SARAH3 a des trous, enregistrés par PVGIS comme des zéros.

    Deux contrôles de cohérence, indépendants de la météo :
    - la hauteur maximale du soleil donnée par PVGIS est inférieure de plus de 5° à la hauteur
      astronomique à midi (PVGIS met aussi la hauteur à zéro quand l'image manque ; les jours normaux,
      l'écart ne dépasse pas 3°) ;
    - l'irradiation PVGIS vaut moins du quart de celle de NASA POWER ET de celle d'ERA5 (deux sources
      indépendantes qui ne voient pas de journée sombre).
    Ces jours sont signalés (`jour_impute_pvgis`) et remplacés :
    - grandeurs d'énergie : irradiation NASA POWER du jour (corrélation 0,97 avec PVGIS) multipliée par
      le rapport médian PVGIS / NASA des jours valides voisins (± 15 jours) ;
    - grandeurs d'intensité (pic, heures, hauteur du soleil...) : interpolation linéaire dans le temps.
    """
    deficit = d["hauteur_soleil_midi_deg"] - d["hauteur_soleil_max_deg"]
    incoherent = ((d["ghi_kwh_m2"] < 0.25 * d["ghi_nasa_kwh_m2"]) & (d["ghi_kwh_m2"] < 0.25 * d["ghi_era5_kwh_m2"])
                  & (d["ghi_nasa_kwh_m2"] > 1.5))
    trou = (deficit > 5) | incoherent
    d["jour_impute_pvgis"] = trou.astype(int)
    if not trou.any():
        return d
    d.loc[trou, ENERGIES_PVGIS + INTENSIVES_PVGIS] = np.nan
    ref = d["ghi_nasa_kwh_m2"]
    for c in ENERGIES_PVGIS:
        rapport = (d[c] / ref).where(ref > 0.2).rolling(31, center=True, min_periods=10).median()
        d.loc[trou, c] = (rapport * ref)[trou]
    d[INTENSIVES_PVGIS] = d[INTENSIVES_PVGIS].interpolate(limit_area="inside")
    d["besoin_eclairage_h"] = 24 - d["heures_lumiere_10klux"]
    return d


def table_site(site: str, h: pd.DataFrame, om: pd.DataFrame, nasa: pd.DataFrame) -> pd.DataFrame:
    """Tableau journalier complet d'un site : PVGIS + Open-Meteo + NASA POWER + astronomie + retards."""
    s = SITES[site]
    d = agreger_jour(h)
    d = d.join(om, how="left").join(nasa, how="left")
    d = d.join(astronomie(d.index, s["lat"]))
    # Trous éventuels des sources complémentaires : interpolation limitée à 3 jours consécutifs
    # (au-delà, la valeur reste manquante et le trou est signalé dans le catalogue).
    exo = list(OPEN_METEO_VARIABLES.values()) + list(NASA_VARIABLES.values())
    d[exo] = d[exo].interpolate(limit=3, limit_area="inside")
    d = corriger_trous_pvgis(d)
    # Variables retardées : uniquement le passé (t-1, t-7...), donc utilisables pour prévoir t.
    d["pv_veille"] = d["pv_kwh_kwc"].shift(1)
    d["pv_j7"] = d["pv_kwh_kwc"].shift(7)
    d["pv_moy7_passe"] = d["pv_kwh_kwc"].shift(1).rolling(7).mean()
    d["pv_ecart_type7_passe"] = d["pv_kwh_kwc"].shift(1).rolling(7).std()
    d["ghi_veille"] = d["ghi_kwh_m2"].shift(1)
    d["ghi_moy7_passe"] = d["ghi_kwh_m2"].shift(1).rolling(7).mean()
    d["nebulosite_veille"] = d["nebulosite_pct"].shift(1)
    d = d.assign(site=site, ville=s["ville"], pays=s["pays"], code_pays=s["code_pays"],
                 latitude=s["lat"], longitude=s["lon"])
    return d[ID + [c for c in d.columns if c not in ID]].asfreq("D")


# Dictionnaire des variables : unité, description et source. Il produit le catalogue et les fiches.
DICTIONNAIRE = {
    "date": ("jour", "Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER)", "-"),
    "site": ("-", "Identifiant du site", "-"), "ville": ("-", "Ville", "-"), "pays": ("-", "Pays", "-"),
    "code_pays": ("-", "Code ISO du pays", "-"), "latitude": ("°", "Latitude", "-"), "longitude": ("°", "Longitude", "-"),
    "pv_kwh_kwc": ("kWh/kWc", "Énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque", "PVGIS"),
    "pv_pic_w_kwc": ("W/kWc", "Puissance horaire maximale de la journée", "PVGIS"),
    "heures_production": ("h", "Nombre d'heures avec une production non nulle", "PVGIS"),
    "irr_poa_kwh_m2": ("kWh/m²", "Irradiation globale reçue sur le plan des modules", "PVGIS"),
    "irr_poa_direct_kwh_m2": ("kWh/m²", "Composante directe sur le plan des modules", "PVGIS"),
    "irr_poa_diffus_kwh_m2": ("kWh/m²", "Composante diffuse sur le plan des modules", "PVGIS"),
    "irr_poa_reflechi_kwh_m2": ("kWh/m²", "Composante réfléchie par le sol sur le plan des modules", "PVGIS"),
    "fraction_diffuse_poa": ("-", "Part du diffus dans l'irradiation du plan des modules (indicateur de couverture nuageuse)", "PVGIS, calculé"),
    "ratio_performance": ("-", "Énergie produite / irradiation reçue (pertes thermiques et système)", "PVGIS, calculé"),
    "ghi_kwh_m2": ("kWh/m²", "Irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement", "PVGIS"),
    "bhi_kwh_m2": ("kWh/m²", "Irradiation directe horizontale", "PVGIS"),
    "dhi_kwh_m2": ("kWh/m²", "Irradiation diffuse horizontale", "PVGIS"),
    "eclairement_max_klux": ("klux", "Éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus)", "PVGIS, calculé"),
    "heures_lumiere_10klux": ("h", "Heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant)", "PVGIS, calculé"),
    "dose_lumineuse_klux_h": ("klux·h", "Exposition lumineuse cumulée de la journée", "PVGIS, calculé"),
    "besoin_eclairage_h": ("h", "Heures où la lumière naturelle est insuffisante (24 - heures au-dessus de 10 000 lux)", "PVGIS, calculé"),
    "hauteur_soleil_max_deg": ("°", "Hauteur maximale du soleil sur l'horizon (pas horaire)", "PVGIS"),
    "t2m_moy_c": ("°C", "Température moyenne de l'air à 2 m", "PVGIS (ERA5)"),
    "t2m_max_c": ("°C", "Température maximale", "PVGIS (ERA5)"), "t2m_min_c": ("°C", "Température minimale", "PVGIS (ERA5)"),
    "t2m_jour_c": ("°C", "Température moyenne pendant les heures de jour (influe sur le rendement des modules)", "PVGIS (ERA5)"),
    "amplitude_thermique_c": ("°C", "Écart entre maximum et minimum de température (ciel clair = forte amplitude)", "PVGIS, calculé"),
    "vent_moy_ms": ("m/s", "Vitesse moyenne du vent à 10 m (refroidit les modules)", "PVGIS (ERA5)"),
    "heures_reconstruites": ("h", "Heures dont le rayonnement a été reconstruit par PVGIS (indicateur de qualité)", "PVGIS"),
    "jour_impute_pvgis": ("0/1", "1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées", "calculé"),
    "nebulosite_pct": ("%", "Couverture nuageuse moyenne", "Open-Meteo (ERA5)"),
    "ensoleillement_h": ("h", "Durée d'ensoleillement (rayonnement direct > 120 W/m²)", "Open-Meteo (ERA5)"),
    "duree_jour_h": ("h", "Durée du jour (lever au coucher du soleil)", "Open-Meteo"),
    "precipitation_mm": ("mm", "Cumul de précipitations", "Open-Meteo (ERA5)"),
    "humidite_pct": ("%", "Humidité relative moyenne à 2 m", "Open-Meteo (ERA5)"),
    "point_rosee_c": ("°C", "Point de rosée moyen à 2 m", "Open-Meteo (ERA5)"),
    "pression_hpa": ("hPa", "Pression moyenne ramenée au niveau de la mer", "Open-Meteo (ERA5)"),
    "rafales_max_kmh": ("km/h", "Rafale maximale à 10 m", "Open-Meteo (ERA5)"),
    "et0_mm": ("mm", "Évapotranspiration de référence FAO-56", "Open-Meteo (ERA5)"),
    "ghi_era5_kwh_m2": ("kWh/m²", "Irradiation globale horizontale selon la réanalyse ERA5 (seconde source)", "Open-Meteo (ERA5)"),
    "ghi_nasa_kwh_m2": ("kWh/m²", "Irradiation globale horizontale selon NASA POWER (troisième source)", "NASA POWER"),
    "ghi_ciel_clair_kwh_m2": ("kWh/m²", "Irradiation horizontale par ciel clair (sans nuages)", "NASA POWER"),
    "indice_clarte": ("-", "Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère)", "NASA POWER"),
    "rayonnement_toa_kwh_m2": ("kWh/m²", "Irradiation au sommet de l'atmosphère", "NASA POWER"),
    "nebulosite_nasa_pct": ("%", "Couverture nuageuse (satellite)", "NASA POWER"),
    "aerosols_aod": ("-", "Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution)", "NASA POWER (MERRA-2)"),
    "indice_uv": ("-", "Indice UV par tout ciel", "NASA POWER"),
    "albedo": ("-", "Albédo de surface (part du rayonnement réfléchi par le sol)", "NASA POWER"),
    "par_kwh_m2": ("kWh/m²", "Rayonnement photosynthétiquement actif (lumière visible utile aux plantes)", "NASA POWER"),
    "irr_extraterrestre_kwh_m2": ("kWh/m²", "Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance)", "calcul astronomique"),
    "duree_jour_astro_h": ("h", "Durée astronomique du jour, calculée (connue à l'avance)", "calcul astronomique"),
    "hauteur_soleil_midi_deg": ("°", "Hauteur du soleil à midi solaire, calculée (connue à l'avance)", "calcul astronomique"),
    "jour_annee": ("-", "Rang du jour dans l'année", "calendrier"), "jds_sin": ("-", "sin(2π jour/365,25)", "calendrier"),
    "jds_cos": ("-", "cos(2π jour/365,25)", "calendrier"), "mois": ("-", "Mois (1 à 12)", "calendrier"),
    "pv_veille": ("kWh/kWc", "Production de la veille (t-1)", "calculé"), "pv_j7": ("kWh/kWc", "Production à t-7", "calculé"),
    "pv_moy7_passe": ("kWh/kWc", "Moyenne de la production sur les 7 jours précédents", "calculé"),
    "pv_ecart_type7_passe": ("kWh/kWc", "Écart-type de la production sur les 7 jours précédents (volatilité récente)", "calculé"),
    "ghi_veille": ("kWh/m²", "Irradiation horizontale de la veille", "calculé"),
    "ghi_moy7_passe": ("kWh/m²", "Moyenne de l'irradiation horizontale sur les 7 jours précédents", "calculé"),
    "nebulosite_veille": ("%", "Nébulosité de la veille", "calculé"),
}
ID = ["site", "ville", "pays", "code_pays", "latitude", "longitude"]
COL_PV = ["pv_kwh_kwc", "pv_pic_w_kwc", "heures_production", "irr_poa_kwh_m2", "irr_poa_direct_kwh_m2",
          "irr_poa_diffus_kwh_m2", "irr_poa_reflechi_kwh_m2", "fraction_diffuse_poa", "ratio_performance",
          "t2m_moy_c", "t2m_max_c", "t2m_min_c", "t2m_jour_c", "amplitude_thermique_c", "vent_moy_ms",
          "nebulosite_pct", "ensoleillement_h", "precipitation_mm", "humidite_pct", "rafales_max_kmh",
          "aerosols_aod", "indice_clarte", "ghi_ciel_clair_kwh_m2", "irr_extraterrestre_kwh_m2", "duree_jour_astro_h",
          "hauteur_soleil_midi_deg", "jds_sin", "jds_cos", "mois", "heures_reconstruites", "jour_impute_pvgis",
          "pv_veille", "pv_j7", "pv_moy7_passe", "pv_ecart_type7_passe", "nebulosite_veille"]
COL_ECL = ["ghi_kwh_m2", "bhi_kwh_m2", "dhi_kwh_m2", "eclairement_max_klux", "heures_lumiere_10klux",
           "dose_lumineuse_klux_h", "besoin_eclairage_h", "ghi_era5_kwh_m2", "ghi_nasa_kwh_m2", "ghi_ciel_clair_kwh_m2",
           "indice_clarte", "rayonnement_toa_kwh_m2", "par_kwh_m2", "indice_uv", "albedo", "aerosols_aod",
           "nebulosite_pct", "nebulosite_nasa_pct", "ensoleillement_h", "duree_jour_h", "duree_jour_astro_h",
           "hauteur_soleil_max_deg", "hauteur_soleil_midi_deg", "irr_extraterrestre_kwh_m2", "humidite_pct",
           "point_rosee_c", "pression_hpa", "precipitation_mm", "et0_mm", "t2m_moy_c", "jds_sin", "jds_cos", "mois",
           "jour_impute_pvgis", "ghi_veille", "ghi_moy7_passe", "nebulosite_veille"]


# Colonnes d'identification (lieu, date) : elles ne comptent pas comme variables explicatives.
ID_COLONNES = {"date", "heure_utc", "site", "ville", "pays", "code_pays", "latitude", "longitude", "jour_annee"}
MIN_LIGNES, MIN_VARIABLES = 1000, 20          # exigence : plus de 1 000 lignes et au moins 20 variables par jeu

DICTIONNAIRE.update({
    # Séries nationales (RTE, REE) et calendrier
    "production_gwh": ("GWh", "Production solaire photovoltaïque nationale de la journée", "RTE"),
    "puissance_moyenne_mw": ("MW", "Puissance solaire moyenne de la journée (points à 30 min)", "RTE"),
    "puissance_max_mw": ("MW", "Puissance solaire maximale de la journée", "RTE"),
    "facteur_forme_solaire": ("-", "Puissance solaire moyenne / maximale (journée régulière ou hachée par les nuages)", "RTE, calculé"),
    "taux_co2_g_kwh": ("g/kWh", "Intensité carbone moyenne de l'électricité produite", "RTE"),
    "part_solaire_conso_pct": ("%", "Part de la consommation couverte par le solaire", "RTE, calculé"),
    "part_renouvelable_conso_pct": ("%", "Part de la consommation couverte par solaire, éolien, hydraulique et bioénergies", "RTE, calculé"),
    "erreur_prevision_j1_pct": ("%", "Écart entre la prévision de consommation de RTE à J-1 et la consommation réalisée", "RTE, calculé"),
    "n_points": ("-", "Nombre de points à 30 min agrégés dans la journée (48 attendus)", "RTE"),
    "nature": ("-", "Statut des données RTE (définitives ou consolidées)", "RTE"),
    "jour_semaine": ("-", "Jour de la semaine (0 = lundi)", "calendrier"), "week_end": ("0/1", "1 le samedi et le dimanche", "calendrier"),
    "produccion_gwh": ("GWh", "Production photovoltaïque de la journée, système péninsulaire (copie de solar_fotovoltaica_gwh)", "REE"),
    "part_fotovoltaica_generacion_pct": ("%", "Part du photovoltaïque dans la production totale", "REE, calculé"),
    "part_renovable_generacion_pct": ("%", "Part des renouvelables dans la production totale", "REE, calculé"),
    "part_fotovoltaica_demanda_pct": ("%", "Part de la demande couverte par le photovoltaïque", "REE, calculé"),
    "pvgis_pv_moyen_kwh_kwc": ("kWh/kWc", "Production PVGIS moyenne des 3 villes du pays le même jour (lien avec la météo, jusqu'en 2023)", "PVGIS"),
    "pvgis_ghi_moyen_kwh_m2": ("kWh/m²", "Irradiation horizontale PVGIS moyenne des 3 villes du pays le même jour", "PVGIS"),
    "nebulosite_moyenne_pays_pct": ("%", "Nébulosité moyenne des 3 villes du pays le même jour", "Open-Meteo (ERA5)"),
    "t2m_moyenne_pays_c": ("°C", "Température moyenne des 3 villes du pays le même jour", "PVGIS (ERA5)"),
    # Mensuel
    "annee": ("-", "Année", "calendrier"), "jours_pluie": ("jours", "Jours du mois avec au moins 1 mm de pluie", "Open-Meteo, calculé"),
    "jours_couverts": ("jours", "Jours du mois avec une nébulosité d'au moins 80 %", "Open-Meteo, calculé"),
    "jours_clairs": ("jours", "Jours du mois avec un indice de clarté d'au moins 0,65", "NASA POWER, calculé"),
    "jours_poussiere": ("jours", "Jours du mois avec une épaisseur optique des aérosols d'au moins 0,8", "NASA POWER, calculé"),
    "jours_imputes": ("jours", "Jours du mois dont le rayonnement PVGIS a été imputé", "calculé"),
    # Climatologie
    "proba_pluie": ("-", "Probabilité d'au moins 1 mm de pluie ce jour de l'année (2005-2020)", "Open-Meteo, calculé"),
    "proba_ciel_couvert": ("-", "Probabilité d'une nébulosité d'au moins 80 % ce jour de l'année (2005-2020)", "Open-Meteo, calculé"),
    "n_annees": ("-", "Nombre d'années ayant servi au calcul", "calculé"),
    # Horaire 2023
    "p_w_kwc": ("W/kWc", "Puissance photovoltaïque d'1 kWc pendant l'heure", "PVGIS"),
    "gb_poa_w_m2": ("W/m²", "Éclairement direct sur le plan des modules", "PVGIS"),
    "gd_poa_w_m2": ("W/m²", "Éclairement diffus sur le plan des modules", "PVGIS"),
    "gr_poa_w_m2": ("W/m²", "Éclairement réfléchi sur le plan des modules", "PVGIS"),
    "gb_h_w_m2": ("W/m²", "Éclairement direct horizontal", "PVGIS"), "gd_h_w_m2": ("W/m²", "Éclairement diffus horizontal", "PVGIS"),
    "hauteur_soleil_deg": ("°", "Hauteur du soleil sur l'horizon", "PVGIS ou calcul astronomique"),
    "t2m_c": ("°C", "Température de l'air à 2 m", "PVGIS (ERA5)"), "vent_ms": ("m/s", "Vitesse du vent à 10 m", "PVGIS (ERA5)"),
    "reconstruit": ("0/1", "1 si le rayonnement de l'heure a été reconstruit par PVGIS", "PVGIS"),
    "ghi_w_m2": ("W/m²", "Éclairement global horizontal", "PVGIS"), "poa_w_m2": ("W/m²", "Éclairement global sur le plan des modules", "PVGIS, calculé"),
    "fraction_diffuse_h": ("-", "Part du diffus dans l'éclairement horizontal", "PVGIS, calculé"),
    "g0_horizontal_w_m2": ("W/m²", "Éclairement extraterrestre sur plan horizontal (calcul astronomique)", "calculé"),
    "indice_clarte_h": ("-", "Indice de clarté horaire (éclairement au sol / extraterrestre)", "calculé"),
    "masse_air": ("-", "Masse d'air traversée par le rayonnement (1 / sin de la hauteur du soleil)", "calculé"),
    "eclairement_lux": ("lux", "Éclairement lumineux horizontal (100 lm/W direct, 125 lm/W diffus)", "calculé"),
    "eclairement_direct_lux": ("lux", "Part directe de l'éclairement lumineux horizontal", "calculé"),
    "eclairement_diffus_lux": ("lux", "Part diffuse de l'éclairement lumineux horizontal", "calculé"),
    "lumiere_suffisante": ("0/1", "1 si l'éclairement lumineux dépasse 10 000 lux (éclairage naturel suffisant)", "calculé"),
    "t_module_c": ("°C", "Température estimée des modules (modèle NOCT : T air + éclairement / 800 x 25 °C)", "calculé"),
    "ratio_performance_h": ("-", "Puissance produite / éclairement reçu pendant l'heure", "calculé"),
    "heure_solaire": ("h", "Heure solaire locale (heure UTC + longitude / 15)", "calculé"),
    "h_sin": ("-", "sin(2π heure/24)", "calendrier"), "h_cos": ("-", "cos(2π heure/24)", "calendrier"),
    "nebulosite_basse_pct": ("%", "Couverture nuageuse basse (sous 2 km)", "Open-Meteo (ERA5)"),
    "nebulosite_moyenne_pct": ("%", "Couverture nuageuse moyenne (2 à 6 km)", "Open-Meteo (ERA5)"),
    "nebulosite_haute_pct": ("%", "Couverture nuageuse haute (au-dessus de 6 km)", "Open-Meteo (ERA5)"),
    "direction_vent_deg": ("°", "Direction d'où vient le vent", "Open-Meteo (ERA5) ou PVGIS"),
    "pression_surface_hpa": ("hPa", "Pression au niveau du sol", "Open-Meteo (ERA5)"),
    "ghi_era5_w_m2": ("W/m²", "Éclairement global horizontal selon ERA5 (seconde source)", "Open-Meteo (ERA5)"),
    "dni_era5_w_m2": ("W/m²", "Éclairement direct normal selon ERA5", "Open-Meteo (ERA5)"),
    "dhi_era5_w_m2": ("W/m²", "Éclairement diffus horizontal selon ERA5", "Open-Meteo (ERA5)"),
    "temperature_ressentie_c": ("°C", "Température ressentie", "Open-Meteo (ERA5)"),
    # Année météorologique type
    "heure": ("h", "Heure UTC", "PVGIS"), "annee_source": ("-", "Année d'où provient le mois retenu dans l'année type", "PVGIS"),
    "dni_w_m2": ("W/m²", "Éclairement direct normal", "PVGIS"), "dhi_w_m2": ("W/m²", "Éclairement diffus horizontal", "PVGIS"),
    "infrarouge_w_m2": ("W/m²", "Rayonnement infrarouge descendant", "PVGIS"), "pression_pa": ("Pa", "Pression au sol", "PVGIS"),
    "bhi_w_m2": ("W/m²", "Éclairement direct horizontal (direct normal x sin de la hauteur du soleil)", "calculé"),
    "vent_u_ms": ("m/s", "Composante est-ouest du vent", "calculé"), "vent_v_ms": ("m/s", "Composante nord-sud du vent", "calculé"),
    "pv_horizontale_estimee_w_kwc": ("W/kWc", "Puissance estimée d'1 kWc posé à plat (pertes 14 %, -0,4 %/°C au-delà de 25 °C)", "calculé"),
    # Scénarios d'orientation
    "inclinaison_deg": ("°", "Inclinaison des modules (0 = à plat, 90 = façade verticale)", "PVGIS"),
    "azimut_deg": ("°", "Orientation des modules (0 = sud, -90 = est, 90 = ouest)", "PVGIS"),
    "orientation": ("-", "Orientation en clair", "PVGIS"), "est_optimal": ("0/1", "1 pour la pente optimale plein sud du site", "PVGIS"),
    "mois_sin": ("-", "sin(2π mois/12)", "calendrier"), "mois_cos": ("-", "cos(2π mois/12)", "calendrier"),
    "e_jour_kwh_kwc": ("kWh/kWc", "Production journalière moyenne du mois", "PVGIS"),
    "e_mois_kwh_kwc": ("kWh/kWc", "Production mensuelle moyenne", "PVGIS"),
    "h_jour_kwh_m2": ("kWh/m²", "Irradiation journalière moyenne du mois sur le plan des modules", "PVGIS"),
    "h_mois_kwh_m2": ("kWh/m²", "Irradiation mensuelle moyenne sur le plan des modules", "PVGIS"),
    "ecart_type_mois_kwh": ("kWh", "Écart-type de la production mensuelle d'une année à l'autre", "PVGIS"),
    "e_an_kwh_kwc": ("kWh/kWc", "Production annuelle moyenne de ce scénario", "PVGIS"),
    "h_an_kwh_m2": ("kWh/m²", "Irradiation annuelle sur le plan des modules", "PVGIS"),
    "ecart_type_an_kwh": ("kWh", "Écart-type de la production annuelle", "PVGIS"),
    "perte_incidence_pct": ("%", "Pertes par angle d'incidence (réflexion)", "PVGIS"),
    "perte_spectrale_pct": ("%", "Effet spectral", "PVGIS"),
    "perte_temperature_pct": ("%", "Pertes dues à la température et au faible éclairement", "PVGIS"),
    "perte_totale_pct": ("%", "Pertes totales (y compris 14 % de pertes système)", "PVGIS"),
    "part_productible_optimal_pct": ("%", "Production annuelle du scénario rapportée à celle de la pente optimale plein sud", "calculé"),
    "ratio_mensuel_vs_optimal": ("-", "Production du mois rapportée à celle de la pente optimale plein sud le même mois", "calculé"),
    "pente_optimale_site_deg": ("°", "Pente optimale du site (plein sud)", "PVGIS"),
    "productible_optimal_kwh_kwc": ("kWh/kWc", "Production annuelle à la pente optimale plein sud", "PVGIS"),
})
SUFFIXES = {"_somme": "Somme mensuelle de", "_moy": "Moyenne mensuelle de", "_min": "Minimum mensuel de",
            "_max": "Maximum mensuel de", "_et": "Écart-type mensuel de", "_moyenne": "Moyenne (jour de l'année, 2005-2020) de",
            "_ecart_type": "Écart-type (jour de l'année, 2005-2020) de", "_p10": "10e centile (jour de l'année) de",
            "_p50": "Médiane (jour de l'année) de", "_p90": "90e centile (jour de l'année) de"}


def decrire(nom: str) -> tuple[str, str, str]:
    """Unité, description et source d'une colonne : dictionnaire, suffixes d'agrégation, puis règles par source."""
    if nom in DICTIONNAIRE:
        return DICTIONNAIRE[nom]
    for suf, libelle in SUFFIXES.items():
        base = nom[: -len(suf)]
        if nom.endswith(suf) and base in DICTIONNAIRE:
            u, d, s = DICTIONNAIRE[base]
            return u, f"{libelle} : {d[0].lower()}{d[1:]}", s
    if nom.endswith("_gwh"):
        base = nom[:-4]
        if base in RTE_CHAMPS:
            return "GWh", f"Énergie journalière de la filière ou du poste « {base.replace('_', ' ')} » (puissance moyenne x 24 h)", "RTE"
        return "GWh", f"Énergie journalière du bilan électrique : « {base.replace('_', ' ')} »", "REE"
    return "-", nom, "-"


def ecrire(df: pd.DataFrame, nom: str, catalogue: list, description: str, sources: list[str], theme: str,
           pays: str, index_label="date", dossier=None, **kw) -> None:
    chemin = (dossier or JEUX) / nom
    df.to_csv(chemin, index=index_label is not None, index_label=index_label, float_format="%.4f", **kw)
    if dossier is not None:                  # table de référence, hors catalogue des jeux de données
        journal(f"  (référence) {nom:36s} {len(df):>8d} lignes")
        return
    cols = ([index_label] if index_label else []) + list(df.columns)
    variables = [c for c in cols if c not in ID_COLONNES]
    conforme = len(df) > MIN_LIGNES and len(variables) >= MIN_VARIABLES
    est_date = isinstance(df.index, pd.DatetimeIndex)
    catalogue.append({
        "fichier": f"data/datasets/{nom}", "description": description, "theme": theme, "pays": pays,
        "sources": sources, "lignes": int(len(df)), "colonnes": len(cols), "variables_explicatives": len(variables),
        "conforme": bool(conforme),
        "periode": [str(df.index.min())[:10], str(df.index.max())[:10]] if est_date else None,
        "taille_ko": round(chemin.stat().st_size / 1024, 1),
        "valeurs_manquantes_pct": round(100 * float(df.isna().to_numpy().mean()), 3),
        "variables": [dict(zip(("unite", "description", "source"), decrire(c)), nom=c) for c in cols]})
    journal(f"  {nom:44s} {len(df):>8d} lignes  {len(variables):>3d} variables  {'conforme' if conforme else 'NON CONFORME'}")


SOURCES_DOC = {
    "PVGIS": "PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ "
             "(rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source)",
    "Open-Meteo": "Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0)",
    "NASA POWER": "NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov",
    "RTE": "RTE éCO2mix via le portail ODRÉ, jeu eco2mix-national-cons-def - https://odre.opendatasoft.com (Licence Ouverte v2.0)",
    "REE": "Red Eléctrica (REData API, bilan électrique) - https://apidatos.ree.es (réutilisation avec mention « Fuente: Red Eléctrica »)",
}


def avec_id(df: pd.DataFrame, site: str) -> pd.DataFrame:
    s = SITES[site]
    df = df.assign(site=site, ville=s["ville"], pays=s["pays"], code_pays=s["code_pays"], latitude=s["lat"], longitude=s["lon"])
    return df[ID + [c for c in df.columns if c not in ID]]


def jeu_mensuel(tables: dict) -> pd.DataFrame:
    """Totaux, moyennes, extrêmes et comptages de jours par mois et par ville."""
    somme = ["pv_kwh_kwc", "irr_poa_kwh_m2", "irr_poa_direct_kwh_m2", "irr_poa_diffus_kwh_m2", "ghi_kwh_m2", "bhi_kwh_m2",
             "dhi_kwh_m2", "ensoleillement_h", "precipitation_mm", "dose_lumineuse_klux_h", "heures_lumiere_10klux",
             "besoin_eclairage_h", "irr_extraterrestre_kwh_m2", "et0_mm", "heures_production"]
    moyenne = ["t2m_moy_c", "t2m_max_c", "t2m_min_c", "nebulosite_pct", "humidite_pct", "pression_hpa", "vent_moy_ms",
               "aerosols_aod", "indice_clarte", "fraction_diffuse_poa", "ratio_performance", "duree_jour_astro_h",
               "eclairement_max_klux"]
    out = []
    for site, t in tables.items():
        r = t.resample("MS")
        m = r[somme].sum().add_suffix("_somme").join(r[moyenne].mean().add_suffix("_moy"))
        m["pv_kwh_kwc_min"], m["pv_kwh_kwc_max"], m["pv_kwh_kwc_et"] = r["pv_kwh_kwc"].min(), r["pv_kwh_kwc"].max(), r["pv_kwh_kwc"].std()
        m["aerosols_aod_max"], m["rafales_max_kmh_max"] = r["aerosols_aod"].max(), r["rafales_max_kmh"].max()
        m["jours_pluie"] = (t["precipitation_mm"] >= 1).resample("MS").sum()
        m["jours_couverts"] = (t["nebulosite_pct"] >= 80).resample("MS").sum()
        m["jours_clairs"] = (t["indice_clarte"] >= 0.65).resample("MS").sum()
        m["jours_poussiere"] = (t["aerosols_aod"] >= 0.8).resample("MS").sum()
        m["jours_imputes"] = r["jour_impute_pvgis"].sum()
        m["annee"], m["mois"] = m.index.year, m.index.month
        m.index.name = "date"
        out.append(avec_id(m, site))
    return pd.concat(out).round(4)


def jeu_climatologie(tables: dict) -> pd.DataFrame:
    """Normales par jour de l'année (2005-2020) : moyennes, écarts-types, centiles et probabilités."""
    vars_ = ["pv_kwh_kwc", "ghi_kwh_m2", "irr_poa_kwh_m2", "nebulosite_pct", "t2m_moy_c", "heures_lumiere_10klux",
             "ensoleillement_h", "precipitation_mm", "aerosols_aod", "indice_clarte", "eclairement_max_klux", "duree_jour_h"]
    out = []
    for site, t in tables.items():
        base = t.loc[:FIN_CLIMATOLOGIE]
        g = base.groupby(base.index.dayofyear)
        c = g[vars_].agg(["mean", "std"])
        c.columns = [f"{a}_{'moyenne' if b == 'mean' else 'ecart_type'}" for a, b in c.columns]
        for q in (10, 50, 90):
            c[f"pv_kwh_kwc_p{q}"] = g["pv_kwh_kwc"].quantile(q / 100)
        for q in (10, 90):
            c[f"ghi_kwh_m2_p{q}"] = g["ghi_kwh_m2"].quantile(q / 100)
        c["proba_pluie"] = (base["precipitation_mm"] >= 1).groupby(base.index.dayofyear).mean()
        c["proba_ciel_couvert"] = (base["nebulosite_pct"] >= 80).groupby(base.index.dayofyear).mean()
        c["n_annees"] = g.size()
        c.index.name = "jour_annee"
        out.append(avec_id(c, site))
    return pd.concat(out).round(4)


def jeu_horaire(horaires: dict, om_h: dict) -> pd.DataFrame:
    """Année 2023 au pas horaire : PVGIS, météo horaire ERA5 et grandeurs dérivées (éclairage, clarté, modules)."""
    out = []
    for site, h in horaires.items():
        s = SITES[site]
        x = h.loc[str(AN_FIN)].astype("float64").copy()
        x.index = x.index.floor("h")                     # PVGIS horodate à HH:10, Open-Meteo à HH:00
        x = x.rename(columns={"P": "p_w_kwc", "Gb_i": "gb_poa_w_m2", "Gd_i": "gd_poa_w_m2", "Gr_i": "gr_poa_w_m2",
                              "Gb_h": "gb_h_w_m2", "Gd_h": "gd_h_w_m2", "H_sun": "hauteur_soleil_deg", "T2m": "t2m_c",
                              "WS10m": "vent_ms", "Int": "reconstruit"})
        ghi = x["gb_h_w_m2"] + x["gd_h_w_m2"]
        poa = x["gb_poa_w_m2"] + x["gd_poa_w_m2"] + x["gr_poa_w_m2"]
        sin_h = np.sin(np.radians(x["hauteur_soleil_deg"].clip(lower=0)))
        jour = x.index.dayofyear.to_numpy()
        g0 = 1367 * (1 + 0.033 * np.cos(2 * np.pi * jour / 365)) * sin_h
        lux = EFFICACITE_DIRECT * x["gb_h_w_m2"] + EFFICACITE_DIFFUS * x["gd_h_w_m2"]
        heure_sol = (x.index.hour + x.index.minute / 60 + s["lon"] / 15) % 24
        x = x.assign(ghi_w_m2=ghi, poa_w_m2=poa, fraction_diffuse_h=(x["gd_h_w_m2"] / ghi).where(ghi > 10),
                     g0_horizontal_w_m2=g0, indice_clarte_h=(ghi / g0).where(g0 > 20).clip(0, 1.2),
                     masse_air=(1 / sin_h).where(x["hauteur_soleil_deg"] > 3),
                     eclairement_lux=lux, eclairement_direct_lux=EFFICACITE_DIRECT * x["gb_h_w_m2"],
                     eclairement_diffus_lux=EFFICACITE_DIFFUS * x["gd_h_w_m2"], lumiere_suffisante=(lux >= SEUIL_LUX).astype(int),
                     t_module_c=x["t2m_c"] + poa / 800 * 25, ratio_performance_h=(x["p_w_kwc"] / poa).where(poa > 50),
                     heure_solaire=heure_sol, h_sin=np.sin(2 * np.pi * heure_sol / 24), h_cos=np.cos(2 * np.pi * heure_sol / 24),
                     jour_annee=jour, mois=x.index.month, jds_sin=np.sin(2 * np.pi * jour / 365.25),
                     jds_cos=np.cos(2 * np.pi * jour / 365.25))
        x = x.join(om_h[site], how="left")
        x.index.name = "heure_utc"
        out.append(avec_id(x, site))
    return pd.concat(out)


def jeu_tmy(tmy: list) -> pd.DataFrame:
    """Année météorologique type PVGIS enrichie : géométrie solaire, éclairage, point de rosée, vent, modules."""
    out = []
    for t in tmy:
        site = t["site"].iloc[0]
        s = SITES[site]
        temps = pd.to_datetime(t["time(UTC)"], format="%Y%m%d:%H%M")
        ref = pd.DatetimeIndex(pd.to_datetime({"year": 2023, "month": temps.dt.month, "day": temps.dt.day, "hour": temps.dt.hour}))
        x = pd.DataFrame({"t2m_c": t["T2m"].to_numpy(), "humidite_pct": t["RH"].to_numpy(), "ghi_w_m2": t["G(h)"].to_numpy(),
                          "dni_w_m2": t["Gb(n)"].to_numpy(), "dhi_w_m2": t["Gd(h)"].to_numpy(), "infrarouge_w_m2": t["IR(h)"].to_numpy(),
                          "vent_ms": t["WS10m"].to_numpy(), "direction_vent_deg": t["WD10m"].to_numpy(),
                          "pression_pa": t["SP"].to_numpy()}, index=ref)
        hs = hauteur_soleil(ref, s["lat"], s["lon"])
        sin_h = np.sin(np.radians(np.clip(hs, 0, None)))
        g0 = 1367 * (1 + 0.033 * np.cos(2 * np.pi * ref.dayofyear.to_numpy() / 365)) * sin_h
        bhi = x["dni_w_m2"] * sin_h
        lux = EFFICACITE_DIRECT * bhi + EFFICACITE_DIFFUS * x["dhi_w_m2"]
        a, b = 17.62, 243.12                                   # formule de Magnus (point de rosée)
        gamma = np.log(x["humidite_pct"].clip(lower=1) / 100) + a * x["t2m_c"] / (b + x["t2m_c"])
        t_mod = x["t2m_c"] + x["ghi_w_m2"] / 800 * 25
        x = x.assign(annee_source=temps.dt.year.to_numpy(), heure=ref.hour, mois=ref.month, jour_annee=ref.dayofyear,
                     jds_sin=np.sin(2 * np.pi * ref.dayofyear / 365.25), jds_cos=np.cos(2 * np.pi * ref.dayofyear / 365.25),
                     h_sin=np.sin(2 * np.pi * ref.hour / 24), h_cos=np.cos(2 * np.pi * ref.hour / 24),
                     hauteur_soleil_deg=hs, bhi_w_m2=bhi, fraction_diffuse_h=(x["dhi_w_m2"] / x["ghi_w_m2"]).where(x["ghi_w_m2"] > 10),
                     g0_horizontal_w_m2=g0, indice_clarte_h=(x["ghi_w_m2"] / g0).where(g0 > 20).clip(0, 1.2),
                     eclairement_lux=lux, lumiere_suffisante=(lux >= SEUIL_LUX).astype(int),
                     point_rosee_c=b * gamma / (a - gamma),
                     vent_u_ms=-x["vent_ms"] * np.sin(np.radians(x["direction_vent_deg"])),
                     vent_v_ms=-x["vent_ms"] * np.cos(np.radians(x["direction_vent_deg"])), t_module_c=t_mod,
                     pv_horizontale_estimee_w_kwc=(x["ghi_w_m2"] * (1 - PERTES_SYSTEME / 100)
                                                   * (1 - 0.004 * (t_mod - 25).clip(lower=0))).clip(lower=0))
        x.index.name = "heure_utc"
        out.append(avec_id(x, site))
    return pd.concat(out)


def jeu_orientations(synth: dict) -> pd.DataFrame:
    """Scénarios PVcalc : production mensuelle pour 27 couples inclinaison x orientation par ville."""
    taches = []
    for site in SITES:
        pente = synth[site]["inputs"]["mounting_system"]["fixed"]["slope"]["value"]
        taches += [(site, 0, 0)] + [(site, a, z) for a in INCLINAISONS for z in AZIMUTS] + [(site, pente, 0)]
    with ThreadPoolExecutor(max_workers=6) as pool:     # PVGIS accepte jusqu'à 30 requêtes par seconde
        reponses = dict(zip(taches, pool.map(lambda tz: pvgis_scenario(*tz), taches)))
    lignes = []
    for (site, angle, aspect), js in reponses.items():
        s = SITES[site]
        opt = synth[site]
        pente = opt["inputs"]["mounting_system"]["fixed"]["slope"]["value"]
        e_opt = opt["outputs"]["totals"]["fixed"]["E_y"]
        e_opt_mois = {m["month"]: m["E_m"] for m in opt["outputs"]["monthly"]["fixed"]}
        tot = js["outputs"]["totals"]["fixed"]
        for m in js["outputs"]["monthly"]["fixed"]:
            lignes.append({
                "site": site, "ville": s["ville"], "pays": s["pays"], "code_pays": s["code_pays"], "latitude": s["lat"],
                "longitude": s["lon"], "inclinaison_deg": angle, "azimut_deg": aspect,
                "orientation": "horizontale" if angle == 0 else AZIMUTS[aspect], "est_optimal": int(angle == pente and aspect == 0),
                "mois": m["month"], "mois_sin": np.sin(2 * np.pi * m["month"] / 12), "mois_cos": np.cos(2 * np.pi * m["month"] / 12),
                "e_jour_kwh_kwc": m["E_d"], "e_mois_kwh_kwc": m["E_m"], "h_jour_kwh_m2": m["H(i)_d"], "h_mois_kwh_m2": m["H(i)_m"],
                "ecart_type_mois_kwh": m["SD_m"], "e_an_kwh_kwc": tot["E_y"], "h_an_kwh_m2": tot["H(i)_y"],
                "ecart_type_an_kwh": tot["SD_y"], "perte_incidence_pct": tot["l_aoi"], "perte_spectrale_pct": tot["l_spec"],
                "perte_temperature_pct": tot["l_tg"], "perte_totale_pct": tot["l_total"],
                "part_productible_optimal_pct": 100 * tot["E_y"] / e_opt,
                "ratio_mensuel_vs_optimal": m["E_m"] / e_opt_mois[m["month"]], "pente_optimale_site_deg": pente,
                "productible_optimal_kwh_kwc": e_opt})
    return pd.DataFrame(lignes).sort_values(["site", "inclinaison_deg", "azimut_deg", "mois"]).reset_index(drop=True)


def meteo_pays(panel: pd.DataFrame, code: str) -> pd.DataFrame:
    """Moyennes quotidiennes des 3 villes d'un pays : relie les séries nationales mesurées à la météo."""
    p = panel[panel["code_pays"] == code].groupby(level=0)
    return pd.DataFrame({"pvgis_pv_moyen_kwh_kwc": p["pv_kwh_kwc"].mean(), "pvgis_ghi_moyen_kwh_m2": p["ghi_kwh_m2"].mean(),
                         "nebulosite_moyenne_pays_pct": p["nebulosite_pct"].mean(), "t2m_moyenne_pays_c": p["t2m_moy_c"].mean()})


def construire_jeux(tables: dict[str, pd.DataFrame], synth: dict, tmy: list, rte: pd.DataFrame,
                    ree: pd.DataFrame, horaires: dict, om_h: dict) -> list:
    """Écrit les 14 jeux de données (plus de 1 000 lignes et au moins 20 variables chacun) et renvoie le catalogue."""
    cat: list = []
    panel = pd.concat(tables.values())
    src_jour = [SOURCES_DOC["PVGIS"], SOURCES_DOC["Open-Meteo"], SOURCES_DOC["NASA POWER"]]
    tous = "France, Tunisie, Espagne"
    for code, nom_pays in PAYS.items():
        sous = panel[panel["code_pays"] == code]
        ecrire(sous[ID + COL_PV], f"{code.lower()}_photovoltaique_journalier.csv", cat,
               f"Photovoltaïque - {nom_pays} : production journalière d'1 kWc et {len(COL_PV) - 1} variables explicatives, 3 villes",
               src_jour, "photovoltaïque", nom_pays)
        ecrire(sous[ID + COL_ECL], f"{code.lower()}_eclairement_journalier.csv", cat,
               f"Éclairement et éclairage naturel - {nom_pays} : irradiation horizontale, éclairement lumineux "
               f"et {len(COL_ECL) - 1} variables explicatives, 3 villes", src_jour, "éclairement", nom_pays)
    ecrire(panel, "panel_9_villes_journalier.csv", cat,
           "Panel complet : 9 villes x 6 939 jours, toutes les variables (table de modélisation)", src_jour,
           "photovoltaïque et éclairement", tous)
    ecrire(jeu_mensuel(tables), "mensuel_9_villes.csv", cat,
           "Mensuel : totaux, moyennes, extrêmes et nombre de jours de pluie, de ciel couvert ou de poussières par ville (2005-2023)",
           src_jour, "photovoltaïque et éclairement", tous)
    ecrire(jeu_climatologie(tables), "climatologie_9_villes.csv", cat,
           "Normales par jour de l'année (2005-2020) : moyennes, écarts-types, centiles et probabilités de pluie ou de ciel couvert",
           src_jour, "photovoltaïque et éclairement", tous, index_label="jour_annee")
    ecrire(jeu_horaire(horaires, om_h), "horaire_9_villes_2023.csv.gz", cat,
           "Horaire 2023 : puissance PV, éclairement (plan incliné, horizontal, lux), nuages par étage et météo ERA5, grandeurs dérivées",
           [SOURCES_DOC["PVGIS"], SOURCES_DOC["Open-Meteo"]], "photovoltaïque et éclairement", tous,
           index_label="heure_utc", compression="gzip")
    ecrire(jeu_tmy(tmy), "tmy_9_villes.csv", cat,
           "Année météorologique type PVGIS (8 760 h par ville) enrichie : géométrie solaire, éclairage, point de rosée, vent, modules",
           [SOURCES_DOC["PVGIS"]], "éclairement", tous, index_label="heure_utc")
    ecrire(jeu_orientations(synth), "pvgis_orientations_9_villes.csv", cat,
           "Scénarios d'installation PVGIS : production mensuelle d'1 kWc pour 27 inclinaisons et orientations par ville",
           [SOURCES_DOC["PVGIS"]], "photovoltaïque", tous, index_label=None)
    ecrire(rte.join(meteo_pays(panel, "FR")), "fr_solaire_national_rte_journalier.csv", cat,
           "Production solaire nationale mesurée et mix électrique français (journalier, 2012-2026), avec la météo des 3 villes",
           [SOURCES_DOC["RTE"], SOURCES_DOC["PVGIS"]], "photovoltaïque (mesuré)", "France")
    ecrire(ree.join(meteo_pays(panel, "ES")), "es_fotovoltaica_ree_journalier.csv", cat,
           "Production photovoltaïque mesurée et bilan électrique espagnol péninsulaire (journalier, 2014-2026), avec la météo des 3 villes",
           [SOURCES_DOC["REE"], SOURCES_DOC["PVGIS"]], "photovoltaïque (mesuré)", "Espagne")

    # Table de référence (9 lignes, une par ville) : utile aux notebooks, mais trop courte pour être un jeu de données.
    lignes = []
    for site, js in synth.items():
        tot, mounting = js["outputs"]["totals"]["fixed"], js["inputs"]["mounting_system"]["fixed"]
        ligne = {"site": site, "ville": SITES[site]["ville"], "pays": SITES[site]["pays"],
                 "pente_optimale_deg": mounting["slope"]["value"], "productible_kwh_kwc_an": tot["E_y"],
                 "irradiation_plan_kwh_m2_an": tot["H(i)_y"], "ecart_type_interannuel_kwh": tot["SD_y"],
                 "pertes_totales_pct": tot["l_total"]}
        for m in js["outputs"]["monthly"]["fixed"]:
            ligne[f"productible_m{m['month']:02d}_kwh_kwc"] = m["E_m"]
        lignes.append(ligne)
    (DATA / "reference").mkdir(exist_ok=True)
    ecrire(pd.DataFrame(lignes).set_index("site"), "pvgis_synthese_9_villes.csv", cat, "", [], "", "",
           index_label="site", dossier=DATA / "reference")

    non = [c["fichier"] for c in cat if not c["conforme"]]
    journal(f"Conformité ({MIN_LIGNES} lignes et {MIN_VARIABLES} variables au moins) : "
            + ("tous les jeux sont conformes" if not non else f"NON CONFORMES : {non}"))
    return cat


def ecrire_fiches(cat: list, liens: list) -> None:
    """Fiches descriptives des jeux de données (Markdown) : elles alimentent aussi le corpus du RAG."""
    l = ["# Jeux de données du projet SolarVision - Séries temporelles", "",
         "Ce document est produit automatiquement par `python/collecte_donnees.py`.", "",
         "## Origine : les liens du rapport SolarVision", "",
         f"Le rapport `Rapport_SolarVision_MLOps_complet.pdf` contient {len(liens)} liens. Un seul donne accès à des "
         "séries temporelles : **PVGIS** (re.jrc.ec.europa.eu/pvg_tools), l'outil de la Commission européenne que "
         "le rapport recommande pour remplacer l'hypothèse G = 1 800 kWh/m²/an à Tunis. Les autres liens sont des "
         "articles scientifiques (résumés récupérés pour le RAG) et des jeux d'images aériennes (métadonnées "
         "seulement). Détail : `sources/liens_rapport_solarvision.json`.", "",
         "| Catégorie | Nombre de liens | Usage |", "|---|---|---|"]
    for c in ("série temporelle", "article", "jeu d'images", "documentation"):
        n = sum(1 for x in liens if x["categorie"] == c)
        usage = {"série temporelle": "API interrogée : séries horaires 2005-2023 pour 9 villes",
                 "article": "résumés intégrés au corpus du RAG", "jeu d'images": "métadonnées archivées",
                 "documentation": "titre archivé"}[c]
        l.append(f"| {c} | {n} | {usage} |")
    l += ["", "## Sources complémentaires", ""] + [f"- **{k}** : {v}" for k, v in SOURCES_DOC.items()]
    l += ["", "## Sites", "", "| Site | Ville | Pays | Latitude | Longitude |", "|---|---|---|---|---|"]
    l += [f"| {k} | {s['ville']} | {s['pays']} | {s['lat']} | {s['lon']} |" for k, s in SITES.items()]
    l += ["", "## Liste des jeux de données", "",
          f"Exigence : plus de {MIN_LIGNES:,} lignes et au moins {MIN_VARIABLES} variables explicatives (hors identifiants : "
          "date, heure, ville, pays, coordonnées) pour chaque jeu.".replace(",", " "), "",
          "| Fichier | Thème | Pays | Lignes | Variables | Période | Conforme |", "|---|---|---|---|---|---|---|"]
    for c in cat:
        per = f"{c['periode'][0]} au {c['periode'][1]}" if c["periode"] else "-"
        l.append(f"| `{c['fichier'].split('/')[-1]}` | {c['theme']} | {c['pays']} | {c['lignes']:,} | "
                 f"{c['variables_explicatives']} | {per} | {'oui' if c['conforme'] else 'non'} |".replace(",", " "))
    for c in cat:
        l += ["", f"### {c['fichier'].split('/')[-1]}", "", c["description"] + ".", "",
              f"Lignes : {c['lignes']:,} ; colonnes : {c['colonnes']} dont {c['variables_explicatives']} variables explicatives ; "
              f"valeurs manquantes : {c['valeurs_manquantes_pct']} %.".replace(",", " "),
              "", "Sources : " + " ; ".join(c["sources"]), "", "| Variable | Unité | Description | Source |", "|---|---|---|---|"]
        l += [f"| `{v['nom']}` | {v['unite']} | {v['description']} | {v['source']} |" for v in c["variables"]]
    l += ["", "## Transformations et précautions", "",
          "- **PVGIS** : rayonnement estimé par satellite (base SARAH3) et non mesuré au sol ; température et vent "
          "issus de la réanalyse ERA5. La puissance P est simulée pour 1 kWc de modules au silicium cristallin, "
          "inclinés à la pente optimale du site et orientés plein sud, avec 14 % de pertes système (modèle de "
          "Huld et al., 2011, qui tient compte de la température des modules et des effets spectraux). Les heures "
          "dont le rayonnement a été reconstruit sont signalées (`heures_reconstruites`).",
          "- **Trous de la base SARAH3** : certains jours, PVGIS renvoie un rayonnement nul pendant tout ou partie de "
          "la journée alors que le soleil est levé (images satellite manquantes). Deux contrôles les repèrent : la "
          "hauteur maximale du soleil fournie par PVGIS inférieure de plus de 5° à la hauteur astronomique à midi "
          "(les jours normaux, l'écart reste sous 3°), ou une irradiation PVGIS inférieure au quart de celles de NASA "
          "POWER et d'ERA5. Ces jours (11 à 13 par ville sur 6 939, surtout en 2008, 2009, 2014 et 2016) sont signalés "
          "(`jour_impute_pvgis` = 1) et remplacés : énergies par l'irradiation NASA POWER du jour multipliée par le "
          "rapport médian PVGIS/NASA des 31 jours voisins, autres grandeurs par interpolation linéaire.",
          "- **Jour UTC** : PVGIS horodate en temps universel. À ces longitudes (-6° à +11°), le soleil ne se lève "
          "jamais avant minuit UTC ni ne se couche après : les sommes journalières d'énergie sont exactes.",
          "- **Éclairement lumineux** : calculé à partir des composantes horizontales avec des efficacités "
          "lumineuses moyennes (100 lm/W pour le direct, 125 lm/W pour le diffus). C'est une approximation : "
          "l'efficacité réelle varie avec la hauteur du soleil et l'humidité (modèle de Perez et al., 1990).",
          "- **Sources complémentaires** : les trous d'au plus 3 jours sont interpolés linéairement ; au-delà, la "
          "valeur reste manquante. Les trois sources d'irradiation (SARAH3, ERA5, NASA POWER) ne coïncident pas : "
          "leur écart mesure l'incertitude de la donnée elle-même.",
          "- **Variables retardées** (`*_veille`, `*_passe`, `pv_j7`) : calculées uniquement sur le passé, elles "
          "sont manquantes les 7 premiers jours de chaque site.",
          "- **RTE** : 22 champs du mix éCO2mix au pas de 30 min, agrégés par jour (énergie = puissance moyenne x 24 h). "
          "Données « définitives » puis « consolidées » (colonne `nature`). La production nationale croît avec le parc "
          "installé : elle n'est pas comparable d'une année à l'autre sans normalisation.",
          "- **REE** : bilan électrique complet du système péninsulaire (hors Baléares et Canaries) ; certaines filières "
          "n'existent pas toutes les années (batteries), leurs colonnes sont alors vides.",
          "- **Variables météo des séries nationales** : moyennes des 3 villes du pays, disponibles jusqu'en 2023 "
          "(fin de PVGIS) ; vides ensuite.",
          "- **Horaire 2023** : les heures PVGIS (HH:10 UTC) sont ramenées à l'heure pleine pour la jointure avec la "
          "météo horaire ERA5 (HH:00 UTC). Température des modules par le modèle NOCT (approximation).",
          "- **Année type (TMY)** : les mois proviennent d'années différentes (`annee_source`) ; la géométrie solaire est "
          "calculée pour une année de référence. La puissance « à plat » est une estimation simple, pas une sortie de PVGIS.",
          "- **Scénarios d'orientation** : moyennes 2005-2023 calculées par l'outil PVcalc de PVGIS (pertes système 14 %), "
          "pour une inclinaison de 0 à 90° et une orientation de l'est à l'ouest.",
          "- **Table de référence** `data/reference/pvgis_synthese_9_villes.csv` : pente optimale et productible par ville "
          "(9 lignes) ; utilisée par les notebooks, elle n'est pas comptée parmi les jeux de données."]
    (DATA / "LISEZMOI_donnees.md").write_text("\n".join(l) + "\n", encoding="utf-8")


def assurer_donnees(forcer: bool = False) -> None:
    """Point d'entrée : ne fait rien si les jeux de données existent déjà (sauf forcer=True)."""
    if (DATA / "catalogue_datasets.json").exists() and not forcer:
        journal("Jeux de données déjà présents :", JEUX)
        return
    for d in (BRUT / "pvgis" / "scenarios", BRUT / "open_meteo", BRUT / "nasa_power", BRUT / "reseaux", JEUX, SOURCES,
              DATA / "reference"):
        d.mkdir(parents=True, exist_ok=True)

    journal("1. Liens du rapport SolarVision")
    f_liens = SOURCES / "liens_rapport_solarvision.json"
    if f_liens.exists() and not forcer:
        liens = json.loads(f_liens.read_text(encoding="utf-8"))
    else:
        liens = visiter_liens(extraire_liens(PDF_SOLARVISION))
        f_liens.write_text(json.dumps(liens, indent=2, ensure_ascii=False), encoding="utf-8")

    journal("2. PVGIS : synthèse, séries horaires, année type")
    synth = {s: pvgis_synthese(s) for s in SITES}
    pentes = {s: js["inputs"]["mounting_system"]["fixed"]["slope"]["value"] for s, js in synth.items()}
    journal("  pentes optimales (°) :", pentes)
    # Les sources sont indépendantes : on télécharge en parallèle (PVGIS accepte 30 requêtes/s,
    # Open-Meteo impose un rythme lent, d'où un fil dédié).
    with ThreadPoolExecutor(max_workers=8) as pool:
        f_om = pool.submit(lambda: ({s: open_meteo(s) for s in SITES}, {s: open_meteo_horaire(s) for s in SITES}))
        f_nasa = pool.submit(lambda: {s: nasa_power(s) for s in SITES})
        f_res = pool.submit(lambda: (rte_mix(), ree_balance()))
        f_h = {s: pool.submit(pvgis_horaire, s, pentes[s]) for s in SITES}
        horaires = {s: f.result() for s, f in f_h.items()}
        tmy = [pvgis_tmy(s) for s in SITES]
        (om, om_h), nasa = f_om.result(), f_nasa.result()
        rte, ree = f_res.result()

    journal("3. Construction des tables journalières")
    tables = {s: table_site(s, horaires[s], om[s], nasa[s]) for s in SITES}
    journal("4. Écriture des jeux de données")
    cat = construire_jeux(tables, synth, tmy, rte, ree, horaires, om_h)
    (DATA / "catalogue_datasets.json").write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
    ecrire_fiches(cat, liens)
    journal(f"Terminé : {len(cat)} jeux de données dans {JEUX}")


if __name__ == "__main__":
    assurer_donnees(forcer="--forcer" in sys.argv)
