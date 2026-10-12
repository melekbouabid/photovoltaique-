"""API de SolarVision v2 (routes /v1) et application multi-pages (une adresse par page).

Toutes les valeurs affichées viennent du panel, des tableaux de reports/ ou du registre de modèles :
rien n'est écrit en dur dans les pages. Les prévisions sont toujours étiquetées ex ante ou ex post.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from pydantic import BaseModel, Field

from solarvision import __version__
from solarvision.config import ROOT, load_cities, load_params
from solarvision.economics import simulate
from solarvision.mlops import registry
from solarvision.serving import charts
from solarvision.serving.predictor import PredictionError, Predictor
from solarvision.serving.store import Store

PAGES = [("/", "Accueil"), ("/villes", "Villes"), ("/previsions", "Prévisions"), ("/technologies", "Technologies PV"),
         ("/economie", "Économie"), ("/comparaison", "Comparaison"), ("/modeles", "Modèles"),
         ("/architecture", "Architecture MLOps"), ("/methodologie", "Méthode et limites")]
MODEL_LABELS = {"persistance": "Persistance", "climatologie": "Climatologie", "arima_fourier": "AR(1) à termes de Fourier",
                "xgboost": "XGBoost direct", "prophet": "Prophet", "lstm": "LSTM", "gru": "GRU", "lstm_global": "LSTM global",
                "xgboost_expost": "XGBoost avec météo observée", "lstm_expost": "LSTM avec météo observée",
                "gru_expost": "GRU avec météo observée"}
SCENARIO_LABELS = {"ex_ante": "ex ante (opérationnel)", "ex_post": "ex post (météo observée, borne optimiste)"}


class PredictRequest(BaseModel):
    ville: str = Field(description="Identifiant de la ville (voir /v1/cities)")
    origine: str | None = Field(None, description="Dernier jour connu, AAAA-MM-JJ ; par défaut le plus récent possible")
    puissance_kwc: float = Field(1.0, gt=0, le=10000, description="Puissance installée")


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="SolarVision v2", version=__version__,
                  description="Prévision de la production photovoltaïque journalière, technologies et économie.")
    app.state.store = store or Store()
    app.state.predictor = None
    pages_dir = ROOT / "app" / "pages"
    templates = Jinja2Templates(directory=str(pages_dir))
    app.mount("/static", StaticFiles(directory=str(pages_dir / "static")), name="static")
    request_log = ROOT / load_params()["serving"]["request_log"]

    def data() -> Store:
        return app.state.store

    def predictor() -> Predictor:
        if app.state.predictor is None:
            app.state.predictor = Predictor(data())
        return app.state.predictor

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Journal des requêtes : une ligne JSON par appel (base du suivi d'usage et de latence)."""
        t0 = time.time()
        response = await call_next(request)
        if not request.url.path.startswith("/static"):
            request_log.parent.mkdir(parents=True, exist_ok=True)
            with open(request_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"date": datetime.now().isoformat(timespec="seconds"), "methode": request.method,
                                    "chemin": request.url.path, "parametres": dict(request.query_params),
                                    "statut": response.status_code, "duree_ms": round(1000 * (time.time() - t0), 1)},
                                   ensure_ascii=False) + "\n")
        return response

    # ------------------------------------------------------------------------------------- API /v1
    @app.get("/health")
    def health() -> dict:
        model = data().production_model()
        return {"statut": "ok", "version_service": __version__, "villes_disponibles": len(data().available_cities),
                "modele": None if model is None else {k: model[k] for k in ("nom", "version", "entraine_le", "promu_le", "sha256",
                                                                             "sha256_verifie", "donnees")},
                "donnees": {"periode": data().manifest.get("periode"), "villes_manquantes": data().manifest.get("villes_manquantes")}}

    @app.get("/v1/cities")
    def cities() -> list[dict]:
        return data().cities_table()

    @app.get("/v1/models")
    def models() -> dict:
        return {"production": registry.current(), "versions": registry.list_models()}

    @app.post("/v1/predict")
    def predict(body: PredictRequest) -> dict:
        try:
            return predictor().predict(body.ville, body.origine, body.puissance_kwc)
        except PredictionError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err

    @app.get("/v1/recommend-tech")
    def recommend_tech(ville: str = Query(...)) -> dict:
        table, indicators = data().table("tech_recommendation"), data().table("tech_indicators")
        if table is None or ville not in set(table["ville"]):
            raise HTTPException(status_code=404, detail=f"pas de recommandation pour {ville}")
        row = table[table["ville"] == ville].iloc[0].to_dict()
        return {**_clean(row), "indicateurs": [_clean(r) for r in indicators[indicators["ville"] == ville].to_dict("records")],
                "avertissement": "Productions simulées par PVGIS : ni mesures, ni dégradation, ni fiabilité mécanique."}

    @app.get("/v1/economics")
    def economics(ville: str = Query(...), technologie: str | None = None, puissance_kwc: float | None = Query(None, gt=0),
                  prix_achat: float | None = Query(None, gt=0), prix_rachat: float | None = Query(None, ge=0),
                  autoconsommation: float | None = Query(None, ge=0, le=1), cout_kwc: float | None = Query(None, gt=0),
                  taux_actualisation: float | None = Query(None, ge=0, lt=1)) -> dict:
        try:
            return economics_case(data(), ville, technologie, puissance_kwc, prix_achat, prix_rachat, autoconsommation,
                                  cout_kwc, taux_actualisation)
        except KeyError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err

    # ------------------------------------------------------------------------------------- pages
    def page(request: Request, template: str, **context) -> HTMLResponse:
        return templates.TemplateResponse(request, template, {"pages": PAGES, "current": request.url.path,
                                                              "model_labels": MODEL_LABELS, "scenario_labels": SCENARIO_LABELS,
                                                              "fmt": _fmt, **context})

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        s = data()
        cities_rows, synthese, reco = s.cities_table(), s.table("synthese_ville"), s.table("tech_recommendation")
        best = dict(zip(reco["ville"], reco["technologie_recommandee"], strict=True)) if reco is not None else {}
        period = load_params()["period"]
        kpis = [("Villes étudiées", len(cities_rows), f"sur {len(load_cities())} prévues"),
                ("Jours par ville", _fmt(len(s.panel) // max(len(cities_rows), 1) if s.panel is not None else 0, 0),
                 f"{period['start_year']} à {period['end_year']}"),
                ("Technologies comparées", len(load_params()["pv"]["technologies"]), "silicium cristallin, CIS, CdTe")]
        if synthese is not None:
            kpis.append(("Gain moyen sur la climatologie", f"{_fmt(synthese['gain_vs_climatologie_pct'].mean(), 1)} %",
                         "meilleur modèle ex ante, J+1 à J+7"))
        return page(request, "home.html", kpis=kpis, missing=s.missing("synthese_ville", "tech_recommendation"),
                    map=Markup(charts.map_chart([{**c, "techno": best.get(c["id"])} for c in cities_rows], "techno")),
                    legend=Markup(charts.legend([("France", 1), ("Tunisie", 2), ("Espagne", 3)])),
                    model=s.production_model())

    @app.get("/villes", response_class=HTMLResponse)
    def cities_page(request: Request):
        s = data()
        synthese = s.table("synthese_ville")
        best = synthese.set_index("ville").to_dict("index") if synthese is not None else {}
        return page(request, "villes.html", cities=s.cities_table(), best=best, missing=s.missing("synthese_ville"))

    @app.get("/previsions", response_class=HTMLResponse)
    def forecasts_page(request: Request, ville: str = "tunis", origine: str | None = None, puissance_kwc: float = 3.0):
        s = data()
        context = {"ville": ville, "puissance_kwc": puissance_kwc, "cities": s.cities_table(), "error": None,
                   "forecast": None, "chart": "", "bounds": None, "scenarios": [],
                   "missing": s.missing("metrics_wide")}
        try:
            result = predictor().predict(ville, origine, puissance_kwc)
            context.update(forecast=result, bounds=predictor().origin_bounds(ville),
                           chart=Markup(charts.forecast_chart(result["historique"], result["previsions"], "kWh par jour")))
        except PredictionError as err:
            context["error"] = str(err)
        wide = s.table("metrics_wide")
        if wide is not None:
            m = wide[(wide["ville"] == ville) & (wide["horizon"] == "tous") & (wide["technologie"] == load_params()["pv"]["reference_technology"])]
            context["scenarios"] = m.sort_values(["scenario", "RMSE"]).to_dict("records")
        return page(request, "previsions.html", **context)

    @app.get("/technologies", response_class=HTMLResponse)
    def technologies_page(request: Request):
        s = data()
        reco, indicators, summary = s.table("tech_recommendation"), s.table("tech_indicators"), s.table("tech_recommender_summary")
        chart = ""
        if indicators is not None:
            mean = indicators.groupby("technologie")["rendement_annuel_kwh_kwc"].mean()
            chart = Markup(charts.bar_chart([(t, float(mean[t])) for t in load_params()["pv"]["technologies"]], "kWh/kWc/an",
                                            digits=0, roles=[1, 2, 3]))
        return page(request, "technologies.html", reco=[] if reco is None else reco.to_dict("records"),
                    indicators=[] if indicators is None else indicators.to_dict("records"), chart=chart,
                    loco=None if summary is None else summary.iloc[0].to_dict(),
                    orientations=[] if s.table("tech_orientations") is None else s.table("tech_orientations").to_dict("records"),
                    missing=s.missing("tech_recommendation", "tech_indicators"))

    @app.get("/economie", response_class=HTMLResponse)
    def economics_page(request: Request, ville: str = "tunis", technologie: str | None = None,
                       puissance_kwc: float | None = None, prix_achat: float | None = None, prix_rachat: float | None = None,
                       autoconsommation: float | None = None, cout_kwc: float | None = None,
                       taux_actualisation: float | None = None):
        s = data()
        case, error = None, None
        try:
            case = economics_case(s, ville, technologie, puissance_kwc, prix_achat, prix_rachat, autoconsommation, cout_kwc,
                                  taux_actualisation)
        except KeyError as err:
            error = str(err)
        ranking = s.table("economics_ranking")
        return page(request, "economie.html", case=case, error=error, cities=s.cities_table(), ville=ville,
                    technologies=load_params()["pv"]["technologies"],
                    ranking=[] if ranking is None else ranking.to_dict("records"), missing=s.missing("economics_by_city"))

    @app.get("/comparaison", response_class=HTMLResponse)
    def comparison_page(request: Request):
        s = data()
        synthese = s.table("synthese_ville")
        rows, chart, by_country = [], "", []
        if synthese is not None:
            cities_by_id = {c["id"]: c for c in s.cities_table()}
            reference = load_params()["pv"]["reference_technology"]
            for r in synthese.sort_values("gain_vs_climatologie_pct", ascending=False).to_dict("records"):
                c = cities_by_id.get(r["ville"], {})
                rows.append({**r, "nom": c.get("nom", r["ville"]), "productible": c.get(f"productible_{reference}")})
            chart = Markup(charts.bar_chart([(r["nom"], max(r["gain_vs_climatologie_pct"], 0)) for r in rows], "%", digits=1,
                                            roles=[charts.ROLE_BY_ENTITY.get(r["pays"], 1) for r in rows]))
            by_country = synthese.groupby("pays")[["rmse_meilleur", "rmse_climatologie", "gain_vs_climatologie_pct"]].mean() \
                .reset_index().to_dict("records")
        return page(request, "comparaison.html", rows=rows, chart=chart, by_country=by_country,
                    legend=Markup(charts.legend([("France", 1), ("Tunisie", 2), ("Espagne", 3)])),
                    missing=s.missing("synthese_ville"))

    @app.get("/modeles", response_class=HTMLResponse)
    def models_page(request: Request):
        s = data()
        wide, dm, coverage = s.table("metrics_wide"), s.table("dm_tests"), s.table("coverage")
        rows, chart = [], ""
        if wide is not None:
            reference = load_params()["pv"]["reference_technology"]
            total = wide[(wide["horizon"] == "tous") & (wide["technologie"] == reference)]
            table = total.groupby(["modele", "scenario"])[["RMSE", "MAE", "MAPE", "WAPE", "MSE"]].mean().reset_index()
            by_h = wide[(wide["technologie"] == reference) & wide["horizon"].isin(["1", "7"])] \
                .pivot_table(index="modele", columns="horizon", values="RMSE")
            tests = {}
            if dm is not None:
                d = dm[(dm["technologie"] == reference) & (dm["perte"] == "squared") & dm["horizon"].isin([1, 7])]
                tests = d.groupby(["modele", "horizon"])["meilleur_que_reference"].agg(["sum", "count"]).to_dict("index")
            cov = {} if coverage is None else coverage.groupby("modele")["couverture_ic95"].mean().to_dict()
            for r in table.sort_values(["scenario", "RMSE"]).to_dict("records"):
                r.update(rmse_h1=by_h["1"].get(r["modele"]), rmse_h7=by_h["7"].get(r["modele"]), couverture=cov.get(r["modele"]),
                         dm_h1=tests.get((r["modele"], 1)), dm_h7=tests.get((r["modele"], 7)))
                rows.append(r)
            ex_ante = [r for r in rows if r["scenario"] == "ex_ante"]
            chart = Markup(charts.bar_chart([(MODEL_LABELS.get(r["modele"], r["modele"]), r["RMSE"]) for r in ex_ante],
                                            "kWh/kWc", digits=3))
        return page(request, "modeles.html", rows=rows, chart=chart, n_cities=len(s.available_cities),
                    missing=s.missing("metrics_wide", "dm_tests"))

    @app.get("/architecture", response_class=HTMLResponse)
    def architecture_page(request: Request):
        s = data()
        manifest = s.manifest
        sources = []
        for city, entry in list(manifest.get("villes", {}).items()):
            for source, detail in entry["sources"].items():
                sources.append({"ville": city, "source": source, "origine": detail["origine"], "fichiers": len(detail["fichiers"]),
                                "octets": sum(f["octets"] for f in detail["fichiers"])})
        per_source = pd.DataFrame(sources).groupby("source").agg(villes=("ville", "nunique"), fichiers=("fichiers", "sum"),
                                                                  octets=("octets", "sum")).reset_index().to_dict("records") if sources else []
        return page(request, "architecture.html", manifest=manifest, per_source=per_source, registry=registry.list_models(),
                    production=s.production_model(), monitoring=s.monitoring,
                    missing=[] if manifest else ["Manifeste absent : lancer python -m solarvision.cli ingest"])

    @app.get("/methodologie", response_class=HTMLResponse)
    def methodology_page(request: Request):
        s = data()
        sensitivity = s.table("sensitivity_imputed")
        return page(request, "methodologie.html", params=load_params(), splits=next(iter(s.splits.values()), None),
                    sensitivity=[] if sensitivity is None else sensitivity.to_dict("records"), missing=[])

    return app


def economics_case(store: Store, ville: str, technologie: str | None, puissance_kwc: float | None, prix_achat: float | None,
                   prix_rachat: float | None, autoconsommation: float | None, cout_kwc: float | None,
                   taux_actualisation: float | None) -> dict:
    """Cas central recalculé avec les hypothèses de l'utilisateur, à côté des intervalles de la simulation."""
    cities = load_cities()
    if ville not in store.available_cities:
        raise KeyError(f"ville inconnue ou non traitée : {ville}")
    cfg, params = simulate.load_economics_config(), load_params()
    technologie = technologie or params["pv"]["reference_technology"]
    if technologie not in params["pv"]["technologies"]:
        raise KeyError(f"technologie inconnue : {technologie}")
    country = cities[ville].pays
    p = simulate.central_parameters(cfg, country, technologie)
    overrides = {"retail_price": prix_achat, "export_price": prix_rachat, "self_consumption": autoconsommation,
                 "capex_per_kwp": cout_kwc, "discount_rate": taux_actualisation}
    for key, value in overrides.items():
        if value is not None:
            p[key] = np.array([float(value)])
    peak, years = puissance_kwc or cfg["system"]["peak_power_kwp"], cfg["system"]["lifetime_years"]
    frame = store.city_frame(ville)
    annual = float(frame[f"pv_{technologie}_kwh_kwc"].sum() / (len(frame) / 365.25))
    flows = simulate.cash_flows(np.array([annual]), p, peak, years)
    result = {k: (None if not np.isfinite(v[0]) else float(v[0])) for k, v in simulate.indicators(flows, p).items()}
    stored = store.table("economics_by_city")
    intervals = {}
    if stored is not None:
        row = stored[(stored["ville"] == ville) & (stored["technologie"] == technologie)]
        if len(row):
            intervals = _clean(row.iloc[0].to_dict())
    return {"ville": ville, "pays": country, "technologie": technologie, "puissance_kwc": peak, "duree_vie_ans": years,
            "production_kwh_kwc_an": annual, "investissement_eur": float(flows["capex"][0]),
            "hypotheses": {k: float(v[0]) for k, v in p.items()}, "cas_central": result, "simulation": intervals,
            "source_a_confirmer": cfg["countries"][country]["source_a_confirmer"],
            "avertissement": "Hypothèses non vérifiées (TODO_VERIFY). Résultat indicatif, pas un conseil financier."}


def _clean(row: dict) -> dict:
    """Remplace les valeurs manquantes par None : JSON n'a pas de NaN."""
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in row.items()}


def _fmt(value, digits: int = 2) -> str:
    """Nombre au format français, ou un tiret quand la valeur manque."""
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def default_store() -> Store:
    """Données servies : l'étude complète, ou le sous-ensemble rapide si SOLARVISION_FAST=1."""
    import os

    from solarvision.config import DATA, MODELS, REPORTS
    if os.environ.get("SOLARVISION_FAST") == "1":
        registry.use(MODELS / "registry_fast")
        return Store(DATA / "fast", REPORTS / "fast")
    return Store()


app = create_app(default_store())
