"""API FastAPI : prévision de la production PV et de l'éclairement (9 villes), données et assistant RAG.

Lancement (depuis app/backend) : uvicorn main:app --port 8000
Documentation interactive : http://localhost:8000/docs
Si le frontend a été construit (app/frontend/dist), il est servi à la racine : http://localhost:8000
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from modele import NOMS_MODELES, RACINE, VARIABLES, Previsionniste, catalogue, metriques_etude

sys.path.insert(0, str(RACINE))
from rag.moteur import MODELE_LLM, MoteurRAG  # noqa: E402

Variable = Literal["pv_kwh_kwc", "ghi_kwh_m2"]
Modele = Literal["lstm", "arima", "climatologie", "persistance"]


# ---------------------------------------------------------------------- schémas
class Site(BaseModel):
    site: str
    ville: str
    pays: str
    code_pays: str
    latitude: float
    longitude: float
    pente_optimale_deg: float
    productible_kwh_kwc_an: float
    irradiation_plan_kwh_m2_an: float


class Info(BaseModel):
    debut: date
    fin: date
    fin_apprentissage: date
    origine_min: date
    origine_max: date
    horizon_max: int
    sites: list[Site]
    variables: dict[str, dict[str, str]]
    modeles: dict[str, str]


class Point(BaseModel):
    date: date
    valeur: float


class ValeurRecente(Point):
    source: str


class DemandePrevision(BaseModel):
    site: str = Field("tunis", description="Identifiant de la ville (voir /api/info)")
    variable: Variable = "pv_kwh_kwc"
    modele: Modele = "lstm"
    origine: date = Field(description="Dernier jour supposé observé ; les jours suivants sont prévus")
    horizon: int = Field(7, ge=1, le=10)
    puissance_kwc: float = Field(1.0, gt=0, le=10000, description="Puissance crête de l'installation")
    conso_kwh_jour: float | None = Field(None, ge=0, description="Consommation journalière à couvrir (facultatif)")
    valeurs_recentes: list[float] | None = Field(None, max_length=28,
                                                 description="Dernières valeurs observées, la plus récente en dernier")


class PointPrevision(BaseModel):
    date: date
    horizon: int
    prevision: float
    bas: float | None
    haut: float | None
    normale: float
    observe: float | None


class PointHistorique(Point):
    source: str


class Prevision(BaseModel):
    site: str
    ville: str
    pays: str
    variable: str
    unite: str
    modele: str
    nom_modele: str
    origine: date
    horizon: int
    puissance_kwc: float
    conso_kwh_jour: float | None
    valeurs_saisies: int
    hors_donnees: bool
    dans_apprentissage: bool
    mae_prevision: float | None
    total: float
    total_bas: float | None
    total_haut: float | None
    total_normale: float
    ecart_normale_pct: float
    mae_test_modele: float | None
    reponse: str
    historique: list[PointHistorique]
    previsions: list[PointPrevision]


class DemandeAssistant(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    contexte: str | None = Field(None, max_length=4000, description="Résumé d'une prévision affichée, facultatif")
    llm: bool = Field(True, description="Rédaction par le LLM (API Groq) ; sinon réponse extractive")


class SourceRAG(BaseModel):
    rang: int
    titre: str
    source: str
    score: float
    extrait: str


class ReponseAssistant(BaseModel):
    question: str
    reponse: str
    mode: str
    sources: list[SourceRAG]
    prevision: Prevision | None = None


# ---------------------------------------------------------------------- application
@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    # Données et modèles chargés une fois au démarrage (quelques secondes).
    app.state.prev = await run_in_threadpool(Previsionniste)
    app.state.rag = await run_in_threadpool(MoteurRAG)
    yield


app = FastAPI(title="SolarVision - Séries temporelles",
              description="Prévision de la production photovoltaïque et de l'éclairement (France, Tunisie, Espagne), "
                          "données PVGIS issues des liens du rapport SolarVision, assistant RAG.",
              version="2.0.0", lifespan=cycle_de_vie)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])


def prev(request: Request) -> Previsionniste:
    return request.app.state.prev


@app.get("/api/health")
async def sante(request: Request):
    p = prev(request)
    return {"statut": "ok", "sites": len(p.sites), "modeles": list(NOMS_MODELES), "passages_rag": len(request.app.state.rag.passages),
            "llm": {"fournisseur": "Groq", "modele": MODELE_LLM, "cle_configuree": bool(os.environ.get("GROQ_API_KEY", "").strip())}}


@app.get("/api/info", response_model=Info)
async def info(request: Request):
    p = prev(request)
    return {**p.bornes(), "sites": list(p.sites.values()), "variables": VARIABLES, "modeles": NOMS_MODELES}


@app.get("/api/catalogue")
async def jeux_de_donnees():
    return catalogue()


@app.get("/api/series", response_model=list[Point])
async def series(request: Request, site: str = "tunis", variable: Variable = "pv_kwh_kwc",
                 debut: date | None = None, fin: date | None = None,
                 pas: Literal["jour", "semaine", "mois"] = "jour"):
    p = prev(request)
    if site not in p.sites:
        raise HTTPException(422, f"site inconnu : {site}")
    if debut and fin and debut > fin:
        raise HTTPException(422, "debut doit précéder fin")
    return p.serie(site, variable, debut, fin, pas)


@app.get("/api/profils")
async def profils(request: Request, variable: Variable = "pv_kwh_kwc"):
    return prev(request).profils_mensuels(variable)


@app.get("/api/valeurs_recentes", response_model=list[ValeurRecente])
async def valeurs_recentes(request: Request, site: str = "tunis", variable: Variable = "pv_kwh_kwc",
                           origine: date = Query(...), n: int = Query(14, ge=1, le=28)):
    try:
        return prev(request).valeurs_recentes(site, variable, origine, n)
    except ValueError as err:
        raise HTTPException(422, str(err)) from err


@app.post("/api/prevision", response_model=Prevision)
async def prevision(request: Request, d: DemandePrevision):
    try:
        # Calcul bloquant (filtre de Kalman, réseau) : délégué pour ne pas figer la boucle d'événements.
        return await run_in_threadpool(prev(request).prevoir, d.site, d.variable, d.modele, d.origine, d.horizon,
                                       d.puissance_kwc, d.conso_kwh_jour, d.valeurs_recentes)
    except ValueError as err:
        raise HTTPException(422, str(err)) from err


@app.get("/api/modeles")
async def modeles(request: Request):
    return {"etude": metriques_etude(), "application": prev(request).validation}


@app.get("/api/profil_horaire")
async def profil_horaire(request: Request, site: str = "tunis", mois: int = Query(6, ge=1, le=12)):
    """Journée moyenne (heure solaire) d'un mois en 2023 : puissance PV, éclairement énergétique et lumineux."""
    try:
        return prev(request).profil_horaire(site, mois)
    except ValueError as err:
        raise HTTPException(422, str(err)) from err


@app.get("/api/orientations")
async def orientations(request: Request, site: str = "tunis"):
    """Production annuelle et mensuelle d'1 kWc selon l'inclinaison et l'orientation (scénarios PVGIS)."""
    try:
        return prev(request).scenarios_orientation(site)
    except ValueError as err:
        raise HTTPException(422, str(err)) from err


# ---------------------------------------------------------------------- assistant
VILLES = {"tunis": "tunis", "sfax": "sfax", "tozeur": "tozeur", "paris": "paris", "lyon": "lyon",
          "marseille": "marseille", "madrid": "madrid", "seville": "seville", "sevilla": "seville",
          "barcelone": "barcelone", "barcelona": "barcelone"}
MOTS_PREVISION = ("prevision", "prevoir", "prevois", "prevoit", "demain", "prochain", "produira", "attendre",
                  "attendue", "attendu", "va produire", "semaine")


def _sans_accents(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def demande_de_prevision(question: str, p: Previsionniste) -> dict | None:
    """Détecte une question de prévision (« combien produira Tunis demain ? ») et en extrait les paramètres."""
    q = _sans_accents(question)
    if not any(m in q for m in MOTS_PREVISION):
        return None
    site = next((v for k, v in VILLES.items() if re.search(rf"\b{k}\b", q)), None)
    if site is None:
        return None
    variable = "ghi_kwh_m2" if re.search(r"eclairement|irradiation|rayonnement|lumiere|lux|ghi", q) else "pv_kwh_kwc"
    horizon = 1 if "demain" in q and "apres-demain" not in q else 7
    m = re.search(r"(\d{1,2})\s*(?:prochains\s*)?jours", q)
    if m:
        horizon = max(1, min(10, int(m.group(1))))
    kwc = re.search(r"(\d+(?:[.,]\d+)?)\s*kwc", q)
    origine = p.bornes()["fin"]
    d = re.search(r"(\d{4})-(\d{2})-(\d{2})|(\d{1,2})/(\d{1,2})/(\d{4})", q)
    if d:
        try:
            origine = (datetime(int(d.group(1)), int(d.group(2)), int(d.group(3))) if d.group(1) else
                       datetime(int(d.group(6)), int(d.group(5)), int(d.group(4)))).date()
        except ValueError:
            pass
    modele = "arima" if "arima" in q else "lstm"
    return {"site": site, "var": variable, "modele": modele, "origine": origine, "horizon": horizon,
            "puissance_kwc": float(kwc.group(1).replace(",", ".")) if kwc else 1.0}


@app.post("/api/assistant", response_model=ReponseAssistant)
async def assistant(request: Request, d: DemandeAssistant):
    p, rag = prev(request), request.app.state.rag
    contexte, prevu = d.contexte, None
    params = demande_de_prevision(d.question, p)
    if params:
        try:
            prevu = await run_in_threadpool(p.prevoir, **params)
            contexte = prevu["reponse"] + (f" {contexte}" if contexte else "")
        except ValueError:
            prevu = None
    rep = await run_in_threadpool(rag.repondre, d.question, 4, contexte, d.llm)
    return {**rep, "prevision": prevu}


# Téléchargement des jeux de données (lecture seule, ce seul dossier).
DONNEES = RACINE / "data" / "datasets"
if DONNEES.exists():
    app.mount("/donnees", StaticFiles(directory=DONNEES), name="donnees")

# Frontend construit (npm run build) servi à la racine, pour une démonstration en une seule commande.
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
