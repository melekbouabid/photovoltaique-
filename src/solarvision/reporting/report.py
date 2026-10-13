"""Rapport de l'étude, généré à partir des fichiers produits par le pipeline.

Aucun chiffre n'est écrit à la main : chaque valeur du texte est lue dans un tableau de reports/, dans le
manifeste des données, dans le registre de modèles ou dans la configuration. Un chapitre par page.
Sorties : reports/rapport/Rapport_SolarVision_v2.docx et .pdf (pandoc, puis impression par Chromium).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pandas as pd
import yaml

from solarvision.config import CONFIGS, DATA, REPORTS, ROOT, load_cities, load_params
from solarvision.mlops import registry
from solarvision.reporting import exploration, figures

NAME = "Rapport_SolarVision_v2"
LEGACY = ROOT / "resultats"                    # tableaux de l'étude historique de Tunis (v1)
LLM_DIR = ROOT / "docs" / "llm"
PAGE_BREAK = '\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n'
MODEL = figures.MODEL_LABELS
SCENARIO = {"ex_ante": "ex ante", "ex_post": "ex post"}
MONTH_NAMES = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
               "novembre", "décembre"]


def n(value, digits: int = 2) -> str:
    """Nombre au format français ; tiret si la valeur manque."""
    if value is None or (isinstance(value, float) and value != value) or value in (float("inf"), float("-inf")):
        return "—"
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def table(frame: pd.DataFrame, caption: str | None = None) -> str:
    """Tableau Markdown (les colonnes sont déjà mises en forme par l'appelant)."""
    head = "| " + " | ".join(str(c) for c in frame.columns) + " |\n|" + "---|" * len(frame.columns) + "\n"
    body = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False))
    return head + body + (f"\n\nTable: {caption}" if caption else "") + "\n"


def _read(path: Path, **kwargs) -> pd.DataFrame | None:
    return pd.read_csv(path, **kwargs) if path.exists() else None


class Context:
    """Tout ce que le rapport lit, chargé une fois."""

    def __init__(self, fast: bool):
        self.fast = fast
        self.data = DATA / "fast" if fast else DATA
        self.reports = REPORTS / "fast" if fast else REPORTS
        self.params, self.cities = load_params(), load_cities()
        self.panel = pd.read_parquet(self.data / "processed" / "panel_journalier.parquet")
        self.splits = yaml.safe_load((self.data / "processed" / "splits_90_10.yaml").read_text(encoding="utf-8"))["villes"]
        self.meta = yaml.safe_load((self.data / "processed" / "panel_meta.yaml").read_text(encoding="utf-8"))
        manifest = self.data / "manifest.yaml"
        self.manifest = yaml.safe_load(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        r = self.reports
        self.wide = _read(r / "metrics_wide.csv", dtype={"horizon": str})
        self.summary, self.dm, self.coverage = _read(r / "synthese_ville.csv"), _read(r / "dm_tests.csv"), _read(r / "coverage.csv")
        self.indicators, self.reco = _read(r / "tech_indicators.csv"), _read(r / "tech_recommendation.csv")
        self.loco = _read(r / "tech_recommender_summary.csv")
        self.orientations = _read(r / "tech_orientations.csv")
        self.eco, self.ranking = _read(r / "economics_by_city.csv"), _read(r / "economics_ranking.csv")
        self.tornado, self.forecast_value = _read(r / "economics_tornado.csv"), _read(r / "forecast_value.csv")
        self.sensitivity = _read(r / "sensitivity_imputed.csv")
        self.walk, self.curves = _read(r / "deep" / "walk_forward_tunis.csv"), _read(r / "deep" / "loss_curves.csv")
        self.quality = _read(self.data / "quality" / "summary.csv")
        self.gap = _read(REPORTS / "diagnostic_ecart_climatologie_tunis.csv")
        monitoring = r / "monitoring" / "summary.json"
        self.monitoring = json.loads(monitoring.read_text(encoding="utf-8")) if monitoring.exists() else {}
        self.exploration = exploration.run(self.panel, self.splits, r)
        self.reference = self.params["pv"]["reference_technology"]
        self.present = sorted(self.splits)
        self.missing = self.meta.get("villes_manquantes", [])
        self.split = next(iter(self.splits.values()))
        self.figures: dict[str, Path] = {}

    def name(self, city: str) -> str:
        return self.cities[city].nom

    def fig(self, key: str, caption: str, width: str = "14cm") -> str:
        path = self.figures.get(key)
        # Chemin relatif au dossier du rapport : le Markdown généré ne contient aucun chemin absolu.
        return f"![{caption}](../figures/{path.name}){{width={width}}}\n" if path else ""

    def mean_rmse(self) -> pd.DataFrame:
        """RMSE moyen par modèle sur la technologie de référence, tous horizons, puis J+1 et J+7."""
        w = self.wide[self.wide["technologie"] == self.reference]
        total = w[w["horizon"] == "tous"].groupby(["modele", "scenario"])[["MSE", "RMSE", "MAE", "MAPE", "WAPE"]].mean()
        by_h = w[w["horizon"].isin(["1", "7"])].pivot_table(index="modele", columns="horizon", values="RMSE")
        out = total.reset_index().merge(by_h.rename(columns={"1": "h1", "7": "h7"}), on="modele", how="left")
        return out.sort_values(["scenario", "RMSE"]).reset_index(drop=True)


def make_figures(c: Context) -> None:
    out = c.reports / "figures"
    cities = [{**c.cities[x].model_dump()} for x in c.present]
    c.figures["map"] = figures.cities_map(cities, out)
    c.figures["season"] = figures.seasonal_profiles(c.panel, out)
    if c.wide is not None:
        c.figures["horizon"] = figures.gain_by_horizon(c.wide, out)
        c.figures["models"] = figures.models_overview(c.wide, out)
    if c.summary is not None:
        c.figures["gain"] = figures.gain_by_city(c.summary, out)
    if c.curves is not None and "tunis" in set(c.curves["ville"]):
        c.figures["loss"] = figures.loss_curves(c.curves, "tunis", out)
    if c.indicators is not None:
        c.figures["tech"] = figures.technology_yield(c.indicators, out)
    if c.reco is not None:
        c.figures["decision"] = figures.technology_decision(c.reco, out)
    if c.eco is not None:
        c.figures["npv"] = figures.npv_by_city(c.eco, out)
    if c.tornado is not None and "tunis" in set(c.tornado["ville"]):
        path = figures.tornado(c.tornado, "tunis", out)
        if path:
            c.figures["tornado"] = path


# ------------------------------------------------------------------------------------------- chapitres
def chapter_introduction(c: Context) -> str:
    countries = c.panel.groupby("pays")["ville"].nunique()
    partial = "" if not c.missing else (
        f" Sur les {len(c.cities)} villes prévues, {len(c.present)} sont traitées ; {len(c.missing)} attendent leurs données "
        f"météo (quota du service Open-Meteo atteint) et ne sont ni simulées ni estimées.")
    return f"""# 1. Introduction

**Thématique.** Nous avons retenu l'option B (environnement et énergie) et la production photovoltaïque journalière,
parce qu'elle pose un vrai problème de séries temporelles : une saisonnalité forte et connue à l'avance, à laquelle
s'ajoute une météo que rien, dans le passé de la série, ne permet de prévoir longtemps.

**Enjeu.** Un exploitant de toitures solaires doit connaître la production des jours suivants pour planifier
l'entretien, piloter une batterie ou s'engager auprès du réseau. Un architecte doit choisir une technologie de modules
et chiffrer ce qu'elle rapportera.

**Questions.**

- Peut-on prévoir de J+1 à J+7 la production journalière d'une installation de 1 kWc, et que gagne-t-on sur la simple normale saisonnière ?
- La réponse dépend-elle de la ville et du climat ?
- Quelle technologie de modules est la plus fiable dans chaque ville, et avec quelle certitude ?
- Que rapporte une installation, compte tenu de l'incertitude sur les prix ?

**Périmètre.** L'étude porte sur {len(c.present)} villes ({", ".join(f"{k} en {p}" for p, k in countries.items())}),
de {c.params['period']['start_year']} à {c.params['period']['end_year']}, soit {n(c.split['n'], 0)} jours par ville, et sur
{len(c.params['pv']['technologies'])} technologies ({", ".join(c.params['pv']['technologies'])}).{partial}
Elle prolonge une première étude sur 9 villes, dont elle garde le socle classique détaillé sur Tunis.

**Démarche.** Chaque choix est justifié par un diagnostic. Tous les modèles sont comparés sur les mêmes dates de test,
avec les mêmes métriques et deux références naïves, et les écarts sont testés. Deux scénarios restent toujours séparés :
*ex ante*, où le modèle ne connaît rien du futur, et *ex post*, où il reçoit la météo observée des jours visés. Seul le
premier est une performance opérationnelle. Les résultats négatifs sont rapportés comme les autres.

**Plan.** Le chapitre 2 présente les données, le chapitre 3 leur exploration, les chapitres 4 et 5 les modèles classiques
et avancés. Les chapitres 6 et 7 traitent des technologies et de l'économie, le chapitre 8 de l'architecture. Le chapitre 9
porte sur l'IA générative, le chapitre 10 sur l'évaluation des prévisions, le chapitre 11 sur les limites.
"""


def chapter_data(c: Context) -> str:
    sources = []
    for source, label, content in (("pvgis", "PVGIS 5.3 (Commission européenne, JRC)", "Puissance horaire d'1 kWc pour 3 technologies, éclairement, température, vent"),
                                   ("open_meteo", "Open-Meteo (réanalyse ERA5)", "Nébulosité, pluie, humidité, pression, rafales"),
                                   ("nasa_power", "NASA POWER", "Rayonnement de contrôle, indice de clarté, aérosols")):
        files = [f for v in c.manifest.get("villes", {}).values() for f in v["sources"][source]["fichiers"]]
        sources.append({"Source": label, "Contenu": content, "Fichiers": len(files), "Volume (Mo)": n(sum(f["octets"] for f in files) / 1e6, 0)})
    yearly = c.panel.groupby("pays")[[f"pv_{t}_kwh_kwc" for t in c.params["pv"]["technologies"]]].sum() \
        .div(c.panel.groupby("pays").size() / 365.25, axis=0)
    per_country = pd.DataFrame({"Pays": yearly.index, "Villes": c.panel.groupby("pays")["ville"].nunique().to_numpy(),
                                **{t: [n(v, 0) for v in yearly[f"pv_{t}_kwh_kwc"]] for t in c.params["pv"]["technologies"]}})
    q = c.quality
    imputation = c.params["imputation"]
    quality = "" if q is None else (
        f"Chaque table compte {n(q['lignes'].min(), 0)} jours. "
        + ("Aucune valeur ne manque. " if q["manquants_pct"].max() == 0 else
           f"Les valeurs manquantes représentent au plus {n(q['manquants_pct'].max(), 3)} % d'une table. ")
        + f"PVGIS enregistre un rayonnement nul certains jours où l'image "
        f"satellitaire manque : {int(q['jours_imputes'].min())} à {int(q['jours_imputes'].max())} jours par ville, soit "
        f"{int(q['jours_imputes'].sum())} au total. {int((q['statut'] == 'ok').sum())} villes sur {len(q)} passent tous les contrôles.")
    tunis = "" if q is None or "tunis" not in set(q["ville"]) else (
        f" À Tunis, les {int(q.loc[q['ville'] == 'tunis', 'jours_imputes'].iloc[0])} dates repérées sont exactement celles de la première "
        f"étude, ce qu'un test automatique vérifie contre l'ancien jeu de données et non contre la règle elle-même.")
    missing = "" if not c.missing else (
        f"\n\n**Villes manquantes.** {', '.join(c.name(x) for x in c.missing)}. Leurs séries PVGIS et NASA POWER sont en cache ; il leur "
        f"manque la météo d'Open-Meteo, dont le quota gratuit a été atteint. Elles seront traitées par "
        f"`python -m solarvision.cli ingest --retry-failed`, sans rien changer aux autres.")
    # Distance maximale à la référence géographique : lue dans le rapport de vérification, pas écrite à la main.
    check = _read(REPORTS / "cities_verification.csv")
    verification = "" if check is None else (
        f"Les coordonnées de chaque ville ont été comparées à une référence indépendante (GeoNames) : aucune ne s'en écarte de plus "
        f"de {n(check['distance_km'].max(), 1)} km. ")
    return f"""# 2. Données et villes

## 2.1 Sources

{table(pd.DataFrame(sources), "Sources de données et volume du cache brut.")}
Toutes les sources sont publiques. PVGIS **simule** la production à partir du rayonnement mesuré par satellite
(base SARAH3) et de la météo ERA5 ; ce ne sont pas des mesures d'installations réelles. L'installation simulée est la
même partout : {c.params['pv']['peak_power_kwp']} kWc, plein sud, pente optimale du site, {c.params['pv']['system_loss_pct']} % de pertes.
L'origine, la licence et l'empreinte SHA256 de chaque fichier sont dans `data/manifest.yaml`.

## 2.2 Villes

{c.fig("map", "Les villes de l'étude.", "11cm")}
{verification}Ajouter une ville revient à ajouter une ligne dans `configs/cities.yaml`.

{table(per_country, "Production annuelle moyenne par pays et par technologie (kWh/kWc/an).")}{missing}

## 2.3 Qualité et imputation

{quality}

Un jour est corrigé si la hauteur du soleil donnée par PVGIS est inférieure de plus de {imputation['sun_height_gap_deg']}° à la
hauteur astronomique à midi, ou si l'irradiation PVGIS vaut moins de {n(100 * imputation['ghi_ratio_threshold'], 0)} % de celle de
NASA POWER un jour où NASA POWER dépasse {n(imputation['ghi_nasa_min_kwh_m2'], 1)} kWh/m². La valeur corrigée est l'irradiation
NASA POWER du jour multipliée par le rapport médian PVGIS / NASA des {imputation['window_days']} jours voisins. La même
correction s'applique aux trois technologies. Le jour reste signalé par la colonne `jour_impute_pvgis`.{tunis}

## 2.4 Découpage

Le découpage est chronologique, sans tirage aléatoire : {n(c.split['n_train'], 0)} jours d'apprentissage (du {c.split['train_debut']} au
{c.split['train_fin']}) et {c.split['n_test']} jours de test (du {c.split['test_debut']} au {c.split['test_fin']}). Le panel de
modélisation compte {n(len(c.panel), 0)} lignes et {c.panel.shape[1]} colonnes. Chaque colonne a un rôle déclaré : identifiant,
cible, variable ex ante ou variable ex post. Un test falsifie le futur et vérifie qu'aucune variable ex ante ne change.
"""


def chapter_exploration(c: Context) -> str:
    e = c.exploration
    by_country = e.groupby("pays").agg(moyenne=("moyenne", "mean"), variance=("variance", "mean"), skewness=("skewness", "mean"),
                                       kurtosis=("kurtosis_exces", "mean"), rapport=("rapport_saisonnier", "mean"),
                                       saison=("part_variance_saisonniere", "mean"), acf1=("acf1_ecart_normale", "mean")).reset_index()
    shown = pd.DataFrame({"Pays": by_country["pays"], "Moyenne": [n(v) for v in by_country["moyenne"]],
                          "Variance": [n(v) for v in by_country["variance"]], "Skewness": [n(v) for v in by_country["skewness"]],
                          "Kurtosis (excès)": [n(v) for v in by_country["kurtosis"]],
                          "Été / hiver": [n(v, 1) for v in by_country["rapport"]],
                          "Variance saisonnière (%)": [n(100 * v, 0) for v in by_country["saison"]],
                          "Autocorrélation à 1 jour": [n(v, 2) for v in by_country["acf1"]]})
    low, high = e.loc[e["rapport_saisonnier"].idxmin()], e.loc[e["rapport_saisonnier"].idxmax()]
    stationary = int(e["stationnaire_ecart_normale"].sum())
    adf_ok, kpss_ok = int((e["adf_p_ecart_normale"] < 0.05).sum()), int((e["kpss_p_ecart_normale"] >= 0.05).sum())
    skew_left = int((e["skewness"] < 0).sum())
    tunis = e[e["ville"] == "tunis"]
    tunis_text = "" if tunis.empty else (
        f" À Tunis, la production moyenne vaut {n(tunis['moyenne'].iloc[0])} kWh/kWc par jour, de {n(tunis['moyenne_mois_bas'].iloc[0])} "
        f"en {MONTH_NAMES[int(tunis['mois_le_plus_bas'].iloc[0]) - 1]} à {n(tunis['moyenne_mois_haut'].iloc[0])} en "
        f"{MONTH_NAMES[int(tunis['mois_le_plus_haut'].iloc[0]) - 1]}.")
    legacy = _read(LEGACY / "py_stationnarite.csv")
    detail = ""
    if legacy is not None:
        prod = legacy[legacy["série"] == "production"].iloc[0]
        detail = (f"\n\n**Étude détaillée de Tunis.** L'exploration complète de la série de Tunis (graphiques, ACF et PACF de la série "
                  f"brute, différenciée et désaisonnalisée, décomposition STL, valeurs aberrantes) est dans le notebook historique "
                  f"`mini_projet_python.ipynb` et dans le notebook R. Sur la série brute, l'ADF vaut {n(prod['ADF stat'], 2)} "
                  f"(p = {n(prod['ADF p'], 3)}) et le KPSS {n(prod['KPSS stat'], 3)} (p = {n(prod['KPSS p'], 2)}) : conclusion "
                  f"« {prod['conclusion à 5 %']} », donc un ordre de différenciation d = 0.")
    return f"""# 3. Analyse exploratoire

## 3.1 Saisonnalité

{c.fig("season", "Production moyenne par mois et par pays.", "12cm")}
La production suit un cycle annuel dans toutes les villes.{tunis_text} Le rapport entre le meilleur et le moins bon mois va de
{n(low['rapport_saisonnier'], 1)} à {c.name(low['ville'])} à {n(high['rapport_saisonnier'], 1)} à {c.name(high['ville'])} : plus on
monte en latitude, plus l'hiver pèse.

## 3.2 Statistiques descriptives

{table(shown, "Statistiques de la production journalière sur l'apprentissage, moyennes par pays (kWh/kWc).")}
- **Asymétrie.** La distribution est asymétrique à gauche dans {skew_left} villes sur {len(e)} : la production est bornée par
  le ciel clair, et les journées couvertes tirent vers le bas.
- **Poids de la saison.** La normale saisonnière explique en moyenne {n(100 * e['part_variance_saisonniere'].mean(), 0)} % de la
  variance journalière. Le reste est la météo de court terme, seule partie à prévoir.
- **Persistance faible.** Une fois la normale retirée, l'autocorrélation à un jour vaut en moyenne
  {n(e['acf1_ecart_normale'].mean(), 2)} (de {n(e['acf1_ecart_normale'].min(), 2)} à {n(e['acf1_ecart_normale'].max(), 2)}) et
  {n(e['acf7_ecart_normale'].mean(), 2)} à sept jours. La météo d'un jour renseigne peu sur le lendemain et presque pas sur la
  semaine suivante : c'est ce qui limitera tous les modèles ex ante.

## 3.3 Stationnarité

Deux tests complémentaires sont appliqués à l'écart à la normale saisonnière de chaque ville. L'ADF a pour hypothèse nulle
une racine unitaire ; le KPSS a pour hypothèse nulle la stationnarité. L'ADF rejette la racine unitaire dans {adf_ok} villes sur
{len(e)} (seuil de 5 %) et le KPSS ne rejette pas la stationnarité dans {kpss_ok} villes. Les deux tests s'accordent sur
{stationary} villes. La série est donc traitée en niveau, sans différenciation, le cycle annuel étant porté par des termes
déterministes.{detail}
"""


def chapter_classical(c: Context) -> str:
    parts = ["# 4. Modélisation classique\n"]
    grid, diag = _read(LEGACY / "py_grille_arima.csv"), _read(LEGACY / "py_diagnostics_arima.csv")
    if grid is not None and diag is not None:
        best, d = grid.sort_values("BIC").iloc[0], diag.iloc[0]
        parts.append(f"""## 4.1 ARIMA à termes de Fourier (Tunis)

L'ACF de la série désaisonnalisée décroît dès le premier retard et la PACF se coupe après lui : la signature d'un AR(1).
Une grille d'ordres p et q faibles, avec K harmoniques annuelles, est classée par BIC. Elle retient l'ordre {best['ordre']}
avec K = {int(best['K'])} (BIC = {n(best['BIC'], 0)}), et la recherche automatique (`pmdarima`, `auto.arima` en R) confirme ce choix.

| Diagnostic des résidus | Valeur | Lecture |
|---|---|---|
| Ljung-Box à 10 retards (p) | {n(d['LB(10) p'], 3)} | pas d'autocorrélation restante |
| Jarque-Bera (p) | {n(d['JB p'], 3)} | normalité rejetée |
| Skewness, kurtosis | {n(d['skewness'], 2)} ; {n(d['kurtosis'], 2)} | erreurs asymétriques à gauche |
| ARCH-LM à 7 retards (p) | {n(d['ARCH-LM(7) p'], 3)} | variance non constante |

Table: Diagnostic de l'ARIMA à termes de Fourier, Tunis.

La structure d'autocorrélation est captée, mais deux hypothèses sont violées : les résidus ne sont pas gaussiens et leur
variance change avec la saison. Les intervalles gaussiens sont donc approximatifs (chapitre 10), et la variance fait l'objet
de la section 4.3. Un SARIMA saisonnier (s = 12) est ajusté sur la série mensuelle dans les deux notebooks.
""")
    var, granger, johansen = _read(LEGACY / "py_var_criteres.csv"), _read(LEGACY / "py_granger.csv"), _read(LEGACY / "py_johansen.csv")
    if var is not None and granger is not None and johansen is not None:
        p_bic, p_aic = int(var.loc[var["BIC"].idxmin(), "p"]), int(var.loc[var["AIC"].idxmin(), "p"])
        strongest = granger.sort_values("F", ascending=False).iloc[0]
        rejected = int((johansen["trace"] > johansen["crit. 95 %"]).sum())
        g = pd.DataFrame({"Cause": granger["cause"], "Effet": granger["effet"], "F": [n(v, 1) for v in granger["F"]],
                          "p": [n(v, 4) for v in granger["p"]]})
        parts.append(f"""## 4.2 VAR, causalité de Granger et cointégration (Tunis)

Un VAR en niveaux relie la production, la nébulosité et la température. Le BIC retient p = {p_bic}, l'AIC p = {p_aic} ; le BIC,
plus parcimonieux, est suivi.

{table(g, "Causalité de Granger deux à deux.")}
Le lien le plus fort va de {strongest['cause']} vers {strongest['effet']} (F = {n(strongest['F'], 1)}). La causalité de Granger
mesure une prévisibilité, pas une cause physique : les trois séries décrivent le même état de l'atmosphère.

Le test de Johansen rejette {rejected} hypothèses de rang sur {len(johansen)} : le rang est plein, le système est stationnaire
en niveaux et la cointégration ne s'applique pas. Un VECM n'est donc pas justifié ici ; il est estimé à titre de vérification,
sur les productions nationales française et espagnole, dans les notebooks.
""")
    garch, gdiag = _read(LEGACY / "py_garch_comparaison.csv", index_col=0), _read(LEGACY / "py_garch_diagnostic.csv", index_col=0)
    if garch is not None and gdiag is not None:
        best = garch["BIC"].idxmin()
        last = gdiag.columns[-1]
        parts.append(f"""## 4.3 Volatilité conditionnelle (Tunis)

Le test ARCH-LM sur les erreurs de l'ARIMA rejette l'homoscédasticité (p = {n(gdiag.loc['ARCH-LM(7) p'].iloc[0], 3)}).
{len(garch)} spécifications sont comparées ; le BIC retient « {best} ». Mais la volatilité estimée suit le calendrier : elle
est forte en hiver et faible en été. Un GARCH seul prend cette saisonnalité pour une persistance des chocs. La variante
« {last} » retire d'abord la variance saisonnière : ses résidus standardisés ne montrent plus d'effet ARCH
(p = {n(gdiag.loc['ARCH-LM(7) p', last], 3)}).
""")
    info = []
    for city in c.present:
        path = c.reports / "forecasts" / f"{city}.json"
        if path.exists():
            info.append({"ville": city, **json.loads(path.read_text(encoding="utf-8"))["arima_fourier"]})
    if info:
        phi = pd.DataFrame(info)
        lo, hi = phi.loc[phi["phi_premier"].idxmin()], phi.loc[phi["phi_premier"].idxmax()]
        parts.append(f"""## 4.4 Le même modèle dans toutes les villes

Le modèle identifié sur Tunis, une régression harmonique à erreurs AR(1), est estimé dans chaque ville et réestimé tous les
{c.params['evaluation']['refit_every_days']} jours. Le coefficient AR(1) vaut en médiane {n(phi['phi_premier'].median(), 2)}, de
{n(lo['phi_premier'], 2)} à {c.name(lo['ville'])} à {n(hi['phi_premier'], 2)} à {c.name(hi['ville'])}. Partout, la mémoire de la série
est courte : l'écart à la saison observé un jour est divisé par {n(1 / phi['phi_premier'].median(), 1)} dès le lendemain.

**R et Python.** Le socle classique est codé dans les deux langages. Le dossier R est autonome : copié seul hors du projet, il
s'exécute de bout en bout et reproduit à l'identique les tableaux de l'étude d'origine.
""")
    return "\n".join(parts)


def chapter_deep(c: Context) -> str:
    deep_cfg = c.params["deep"]
    parts = [f"""# 5. Modélisation avancée

## 5.1 Réseaux récurrents

**Mise en forme.** Chaque réseau reçoit les {deep_cfg['window_days']} derniers jours (écart de la production à sa normale,
nébulosité, température, humidité, pluie, aérosols, position dans l'année) et prévoit d'un coup les sept jours suivants. La
cible est l'écart à la normale saisonnière, divisé par son écart-type : le réseau part de la climatologie et n'apprend que la
correction. La normalisation n'utilise que l'apprentissage. La dernière année de l'apprentissage sert à l'arrêt anticipé.
"""]
    if c.walk is not None:
        w = c.walk.groupby(["fenetre", "taille_cachee", "dropout"]).agg(rmse=("rmse_validation", "mean"), std=("rmse_validation", "std"),
                                                                        clim=("rmse_climatologie", "mean")).reset_index()
        shown = pd.DataFrame({"Fenêtre (jours)": w["fenetre"], "Unités": w["taille_cachee"], "Dropout": [n(v, 1) for v in w["dropout"]],
                              "RMSE moyen": [n(v, 4) for v in w["rmse"]], "Écart-type entre plis": [n(v, 4) for v in w["std"]]})
        spread = w["rmse"].max() - w["rmse"].min()
        parts.append(f"""**Validation glissante.** Les hyperparamètres sont choisis sur l'apprentissage seul, par {deep_cfg['walk_forward_folds']} plis à
fenêtre croissante : on entraîne sur le début, on mesure sur l'année suivante, puis on avance. Jamais de validation croisée
aléatoire, qui mélangerait le futur et le passé.

{table(shown, "Validation glissante du LSTM à Tunis (kWh/kWc).")}
Les configurations se tiennent à {n(spread, 4)} kWh/kWc les unes des autres, pour un écart-type entre plis de
{n(w['std'].mean(), 4)} : les données ne permettent pas de les départager. On retient donc la configuration la plus simple qui ne
perd rien, une fenêtre de {deep_cfg['window_days']} jours, {deep_cfg['hidden_size']} unités et un dropout de {n(deep_cfg['dropout'], 1)}.
Sur les mêmes plis, la climatologie obtient {n(w['clim'].mean(), 4)}.
""")
    if c.curves is not None and "loss" in c.figures:
        t = c.curves[(c.curves["ville"] == "tunis")]
        ante, post = t[t["modele"] == "lstm"], t[t["modele"] == "lstm_expost"]
        if len(ante) and len(post):
            parts.append(f"""{c.fig("loss", "Courbes de perte du LSTM à Tunis.", "13cm")}
Ex ante, la perte de validation cesse de baisser dès l'époque {int(ante['meilleure_epoque'].iloc[0])} : le réseau apprend peu au-delà
de la normale. Ex post, elle descend jusqu'à l'époque {int(post['meilleure_epoque'].iloc[0])} et finit à
{n(post['perte_validation'].min(), 2)} contre {n(ante['perte_validation'].min(), 2)} : la météo des jours visés contient l'information
qui manquait.
""")
    if c.wide is not None:
        m = c.mean_rmse().set_index("modele")
        clim = m.loc["climatologie", "RMSE"]
        w = c.wide[(c.wide["technologie"] == c.reference) & (c.wide["horizon"] == "tous")].pivot_table(index="ville", columns="modele", values="RMSE")
        rows = []
        for model in ("lstm", "gru", "lstm_global", "xgboost", "prophet", "lstm_expost", "gru_expost", "xgboost_expost"):
            if model in m.index:
                rows.append({"Modèle": MODEL[model], "Scénario": SCENARIO[m.loc[model, "scenario"]], "RMSE moyen": n(m.loc[model, "RMSE"], 4),
                             "Écart à la climatologie": f"{n(100 * (m.loc[model, 'RMSE'] / clim - 1), 1)} %",
                             "Villes où il fait mieux": f"{int((w[model] < w['climatologie']).sum())} / {len(w)}"})
        parts.append(f"""## 5.2 Résultats

{table(pd.DataFrame(rows), f"Modèles avancés, moyenne des villes ; climatologie : {n(clim, 4)} kWh/kWc.")}
""")
        if "lstm_global" in m.index and "lstm" in m.index:
            parts.append(f"""**LSTM global.** Un seul réseau est entraîné sur toutes les villes, chacune ramenée à sa propre normale ; un vecteur appris par
ville lui permet de s'adapter au climat local. Son RMSE moyen est de {n(m.loc['lstm_global', 'RMSE'], 4)} contre
{n(m.loc['lstm', 'RMSE'], 4)} pour les réseaux entraînés ville par ville : {"mettre les villes en commun aide" if m.loc['lstm_global', 'RMSE'] < m.loc['lstm', 'RMSE'] else "mettre les villes en commun n'apporte pas de gain"}.
""")
        if "xgboost" in m.index and "prophet" in m.index:
            parts.append(f"""**Modèles additionnels.** XGBoost prévoit chaque horizon par un modèle séparé, à partir de variables ex ante (dernières
productions, météo de la veille, calendrier, normale). Prophet ({n(m.loc['prophet', 'RMSE'], 4)}) n'utilise pas les dernières
observations : c'est une climatologie lissée, et il ne peut pas faire mieux qu'elle à court terme.
""")
    legacy = _read(LEGACY / "py_metriques.csv")
    if legacy is not None:
        # Les deux erreurs sont lues dans le tableau de l'étude historique.
        rmse = legacy.set_index("modèle")["RMSE"]
        hybrid = [k for k in rmse.index if k.startswith("Hybride")]
        arima = [k for k in rmse.index if k.startswith("ARIMA-Fourier manuel")]
        if hybrid and arima:
            parts.append(f"""**Ce qui n'est pas repris.** Le modèle hybride ARIMA + LSTM de la première étude n'a pas été étendu aux nouvelles villes. Il reste
dans le notebook historique, où son RMSE à Tunis était de {n(rmse[hybrid[0]], 4)} contre {n(rmse[arima[0]], 4)} pour l'ARIMA seul : sans
information nouvelle sur la météo à venir, il ne reste presque rien à apprendre des erreurs.
""")
    return "\n".join(parts)


def chapter_technologies(c: Context) -> str:
    if c.reco is None or c.indicators is None:
        return "# 6. Technologies photovoltaïques\n\nRecommandation non calculée : lancer `python -m solarvision.cli recommend`.\n"
    rel = yaml.safe_load((CONFIGS / "reliability.yaml").read_text(encoding="utf-8"))
    weights = pd.DataFrame([{"Critère": v["description"], "Poids": n(v["weight"], 2), "Sens": "plus bas = mieux" if v["better"] == "lower" else "plus haut = mieux"}
                            for v in rel["criteria"].values()])
    counts = c.reco.groupby(["pays", "technologie_recommandee"]).size().unstack(fill_value=0)
    counts_table = counts.reset_index().rename(columns={"pays": "Pays"})
    ties = int(c.reco["ex_aequo"].sum())
    mean = c.indicators.groupby("technologie")[["rendement_annuel_kwh_kwc", "wape_meilleur_ex_ante_pct", "pente_temperature_pct_par_degre",
                                                "ratio_faible_irradiation", "cv_journalier_pct"]].mean()
    ind = pd.DataFrame({"Technologie": mean.index, "Production (kWh/kWc/an)": [n(v, 0) for v in mean["rendement_annuel_kwh_kwc"]],
                        "Erreur de prévision (WAPE, %)": [n(v, 1) for v in mean["wape_meilleur_ex_ante_pct"]],
                        "Température (%/°C)": [n(v, 2) for v in mean["pente_temperature_pct_par_degre"]],
                        "Faible irradiation": [n(v, 3) for v in mean["ratio_faible_irradiation"]],
                        "Variabilité journalière (%)": [n(v, 1) for v in mean["cv_journalier_pct"]]})
    top = mean["rendement_annuel_kwh_kwc"].idxmax()
    clear = c.reco[~c.reco["ex_aequo"]]
    loco = ""
    if c.loco is not None:
        s = c.loco.iloc[0]
        loco = (f"\n\n**Peut-on deviner la technologie à partir du climat ?** Un arbre de décision reçoit les caractéristiques de la ville "
                f"(latitude, altitude, irradiation, températures, nébulosité, variabilité). Jugé ville par ville, chaque ville étant prédite "
                f"par un modèle qui ne l'a pas vue, il retrouve la technologie recommandée dans {n(s['exactitude_arbre_pct'], 0)} % des cas. "
                f"Proposer partout la technologie la plus fréquente en retrouve {n(s['exactitude_majoritaire_pct'], 0)} %. "
                + ("L'arbre n'apporte donc rien de plus que cette règle simple." if s["exactitude_arbre_pct"] <= s["exactitude_majoritaire_pct"]
                   else "L'arbre fait donc mieux que cette règle simple, sur un échantillon qui reste petit."))
    orientation = ""
    orientation_limit = "- L'analyse des orientations n'a pas été faite pour ces villes (`recommend --orientations`).\n"
    if c.orientations is not None and len(c.orientations):
        o = c.orientations
        worst, mildest = o.loc[o["ecart_est_ouest_pct"].idxmin()], o.loc[o["ecart_est_ouest_pct"].idxmax()]
        by_country = o.groupby("pays")[["ecart_est_ouest_pct", "gain_optimal_pct"]].mean().reset_index()
        shown = pd.DataFrame({"Pays": by_country["pays"], "Est-ouest par rapport au sud (%)": [n(v, 1) for v in by_country["ecart_est_ouest_pct"]],
                              "Gain de l'azimut optimisé (%)": [n(v, 2) for v in by_country["gain_optimal_pct"]]})
        orientation = f"""## 6.3 Orientation

Pour la technologie recommandée de chaque ville, PVGIS simule trois orientations : plein sud à la pente optimale (l'installation
de toute l'étude), deux pans est et ouest inclinés à {n(o['pente_est_ouest_deg'].iloc[0], 0)}°, et une orientation dont la pente et
l'azimut sont optimisés ensemble.

{table(shown, "Effet de l'orientation sur la production annuelle, moyenne par pays.")}
Une toiture à deux pans est et ouest produit de {n(-mildest['ecart_est_ouest_pct'], 0)} % ({c.name(mildest['ville'])}) à
{n(-worst['ecart_est_ouest_pct'], 0)} % ({c.name(worst['ville'])}) de moins que le plein sud. Optimiser l'azimut n'apporte presque
rien : l'azimut optimal s'écarte du sud de {n(o['azimut_optimal_deg'].abs().max(), 0)}° au plus, pour un gain maximal de
{n(o['gain_optimal_pct'].max(), 2)} %. Le plein sud à la pente optimale est donc un bon choix partout.

"""
        orientation_limit = ""
    return f"""# 6. Technologies photovoltaïques

## 6.1 Trois technologies, cinq critères

PVGIS simule trois technologies de modules : le silicium cristallin (crystSi) et deux couches minces, CIS et CdTe. Pour chaque
ville et chaque technologie, cinq critères sont **calculés** à partir des données ; aucun n'est une appréciation.

{table(weights, "Critères du score de fiabilité. Chaque critère est ramené entre 0 et 1 parmi les villes d'un même pays.")}
{c.fig("tech", "Production annuelle moyenne par pays et par technologie.", "12cm")}
{table(ind, "Indicateurs moyens par technologie, toutes villes.")}
La technologie qui produit le plus en moyenne est {top} ({n(mean.loc[top, 'rendement_annuel_kwh_kwc'], 0)} kWh/kWc/an). Les écarts
restent de quelques pour cent : les trois technologies voient le même ciel.

## 6.2 Recommandation par ville

{table(counts_table, "Nombre de villes où chaque technologie obtient le meilleur score.")}
{c.fig("decision", "Écart de score entre les deux premières technologies de chaque ville.", "13cm")}
L'incertitude est mesurée en rééchantillonnant des années entières, ce qui garde la saison intacte. Quand l'écart entre les
deux premières technologies tient dans cette marge, le rapport le dit : **{ties} villes sur {len(c.reco)} sont ex æquo**.
{"Dans les " + str(len(clear)) + " autres, la technologie recommandée garde la première place dans " + n(100 * clear["probabilite_meilleure"].mean(), 0) + " % des rééchantillonnages en moyenne." if len(clear) else "Aucune ville ne dégage un gagnant net."}
Le classement dépend aussi des poids : en les faisant varier, la technologie recommandée reste première dans
{n(100 * c.reco['robustesse_poids'].mean(), 0)} % des tirages en moyenne. Le tableau par ville, avec le deuxième choix et la
justification chiffrée, est dans `reports/tech_recommendation.csv` et dans l'application.{loco}

{orientation}## {"6.4" if orientation else "6.3"} Limites

- Les productions sont des **simulations** : les écarts viennent des modèles de rendement de PVGIS, pas de mesures.
- La **dégradation** dans le temps et la **fiabilité mécanique** ne sont pas modélisées par PVGIS.
- Les poids du score sont un choix ; ils sont écrits dans `configs/reliability.yaml` et leur influence est mesurée.
{orientation_limit}"""


def chapter_economics(c: Context) -> str:
    if c.eco is None or c.ranking is None:
        return "# 7. Bénéfices économiques\n\nSimulation non calculée : lancer `python -m solarvision.cli economics`.\n"
    cfg = yaml.safe_load((CONFIGS / "economics.yaml").read_text(encoding="utf-8"))
    hyp = pd.DataFrame([{"Pays": country, "Prix d'achat (€/kWh)": " / ".join(n(v, 2) for v in v_["retail_price_eur_kwh"]),
                         "Rachat du surplus (€/kWh)": " / ".join(n(v, 2) for v in v_["export_price_eur_kwh"]),
                         "Coût (€/kWc)": " / ".join(n(v, 0) for v in v_["capex_eur_per_kwp"]),
                         "CO2 du réseau (g/kWh)": " / ".join(n(v, 0) for v in v_["grid_emission_g_co2_kwh"])}
                        for country, v_ in cfg["countries"].items()])
    ref = c.eco[c.eco["technologie"] == c.reference]
    by_country = ref.groupby("pays").agg(van10=("van_eur_p10", "median"), van50=("van_eur_p50", "median"), van90=("van_eur_p90", "median"),
                                         pay=("temps_retour_ans_p50", "median"), lcoe=("lcoe_eur_kwh_p50", "median"),
                                         co2=("co2_evite_t_p50", "median"), prob=("probabilite_van_positive", "mean")).reset_index()
    res = pd.DataFrame({"Pays": by_country["pays"], "VAN P10 (€)": [n(v, 0) for v in by_country["van10"]],
                        "VAN P50 (€)": [n(v, 0) for v in by_country["van50"]], "VAN P90 (€)": [n(v, 0) for v in by_country["van90"]],
                        "Temps de retour P50 (ans)": [n(v, 1) for v in by_country["pay"]],
                        "Coût de l'énergie P50 (€/kWh)": [n(v, 3) for v in by_country["lcoe"]],
                        "CO2 évité P50 (t)": [n(v, 1) for v in by_country["co2"]],
                        "Probabilité VAN > 0 (%)": [n(100 * v, 0) for v in by_country["prob"]]})
    inconclusive = int(c.ranking["ecart_non_concluant"].sum())
    tornado = ""
    if c.tornado is not None and "tornado" in c.figures:
        t = c.tornado[c.tornado["ville"] == "tunis"].sort_values("amplitude_eur", ascending=False)
        labels = {"retail_price": "le prix d'achat de l'électricité", "capex_per_kwp": "le coût d'investissement", "self_consumption": "la part autoconsommée",
                  "discount_rate": "le taux d'actualisation", "inflation": "la hausse du prix de l'électricité", "export_price": "le prix de rachat",
                  "om_share": "l'entretien", "degradation": "la dégradation", "capex_multiplier": "le surcoût de la technologie"}
        first, second = t.iloc[0], t.iloc[1]
        tornado = (f"""{c.fig("tornado", "Sensibilité de la valeur actuelle nette à chaque hypothèse, Tunis.", "12cm")}
À Tunis, l'hypothèse qui pèse le plus est {labels.get(first['hypothese'], first['hypothese'])} (amplitude de {n(first['amplitude_eur'], 0)} €),
devant {labels.get(second['hypothese'], second['hypothese'])} ({n(second['amplitude_eur'], 0)} €). Ce sont les premières valeurs à vérifier.
""")
    value = ""
    if c.forecast_value is not None:
        v = c.forecast_value
        value = (f"""## 7.3 Valeur de la prévision

Que vaut une meilleure prévision ? Le modèle de coût est explicite : chaque kWh d'écart entre le plan et la production réelle
coûte une pénalité, tirée entre {n(cfg['forecast_value']['imbalance_penalty_eur_kwh'][0], 2)} et {n(cfg['forecast_value']['imbalance_penalty_eur_kwh'][2], 2)} €/kWh.
Remplacer la climatologie par le meilleur modèle ex ante évite en médiane {n(v['erreur_evitee_kwh_an'].median(), 0)} kWh d'erreur par an
pour {n(cfg['system']['peak_power_kwp'], 0)} kWc, soit un gain médian de {n(v['gain_eur_an_p50'].median(), 2)} € par an
(de {n(v['gain_eur_an_p10'].median(), 2)} à {n(v['gain_eur_an_p90'].median(), 2)} €). Pour une installation résidentielle, ce gain est
négligeable : la prévision ex ante ne prend de la valeur qu'à l'échelle d'un parc, ou associée à une prévision météo.
""")
    return f"""# 7. Bénéfices économiques

> **Avertissement.** Aucune des hypothèses de ce chapitre n'est une donnée du projet. Tarifs, coûts et taux sont des ordres de
> grandeur à confirmer auprès des sources indiquées ; chacun est marqué `TODO_VERIFY` dans `configs/economics.yaml`. Les résultats
> sont indicatifs. Ce n'est pas un conseil financier.

## 7.1 Hypothèses

L'installation type fait {n(cfg['system']['peak_power_kwp'], 0)} kWc et dure {cfg['system']['lifetime_years']} ans. Chaque hypothèse est
donnée par trois valeurs (basse / centrale / haute).

{table(hyp, "Hypothèses par pays, à vérifier (basse / centrale / haute).")}
Sources à confirmer : {" ; ".join(f"{k} : {v['source_a_confirmer']}" for k, v in cfg['countries'].items())}.
S'y ajoutent la part autoconsommée ({" / ".join(n(v, 2) for v in cfg['system']['self_consumption_share'])}), le taux d'actualisation
({" / ".join(n(100 * v, 0) for v in cfg['common']['discount_rate'])} %), la hausse annuelle du prix de l'électricité
({" / ".join(n(100 * v, 0) for v in cfg['common']['energy_price_inflation'])} %), l'entretien et, par technologie, un surcoût et une dégradation annuelle.

## 7.2 Résultats

Une simulation de Monte-Carlo ({n(cfg['monte_carlo']['draws'], 0)} tirages) tire chaque hypothèse dans sa plage et le productible
parmi les années observées. Aucun résultat n'est donné sans intervalle.

{table(res, f"Résultats médians par pays, technologie {c.reference}, installation de {n(cfg['system']['peak_power_kwp'], 0)} kWc.")}
{c.fig("npv", "Valeur actuelle nette par ville : médiane et intervalle P10-P90.", "13cm")}
Les intervalles sont larges : l'incertitude sur les prix domine celle sur le soleil. Entre technologies, l'écart de valeur
actuelle nette n'est pas concluant dans {inconclusive} villes sur {len(c.ranking)} (la première technologie gagne dans moins de
90 % des tirages), parce que le surcoût des couches minces est lui-même mal connu.

{tornado}
{value}"""


def chapter_mlops(c: Context) -> str:
    models = registry.list_models()
    active = registry.current()
    reg = pd.DataFrame([{"Modèle": MODEL.get(m["nom"], m["nom"]), "Version": m["version"], "RMSE moyen": n(m["rmse_moyen"], 4),
                         "RMSE climatologie": n(m["rmse_climatologie_moyen"], 4), "Villes gagnées": m["villes_ou_il_bat_la_climatologie"],
                         "Statut": m["statut"]} for m in models]) if models else None
    monitoring = ""
    if c.monitoring:
        d = c.monitoring["derive"]
        monitoring = (f"Entre l'apprentissage et le test, {d.get('stable', 0)} couples ville-variable sont stables, {d.get('à surveiller', 0)} "
                      f"à surveiller et {d.get('alerte', 0)} en alerte (indice de stabilité de population). L'erreur du modèle en production "
                      f"dépasse de plus de {n((c.monitoring['seuils']['error_ratio_alert'] - 1) * 100, 0)} % celle de la climatologie pendant "
                      f"{n(c.monitoring['part_des_jours_en_alerte_erreur_pct'], 1)} % des jours.")
    production = "Aucun modèle n'est en production." if not active else (
        f"Le modèle en production est **{MODEL.get(active['nom'], active['nom'])}**, version {active['version']}.")
    return f"""# 8. Architecture et MLOps

## 8.1 Organisation

Le code est un paquet Python installable (`src/solarvision/`). Chaque étape est une commande de `python -m solarvision.cli` :
`ingest`, `features`, `train`, `deep`, `evaluate`, `recommend`, `economics`, `register`, `monitor`, `serve`, `report`. La commande
`pipeline` les enchaîne ; l'option `--fast` les limite à trois villes pour les essais.

| Je cherche | Emplacement |
|---|---|
| Villes, paramètres, hypothèses | `configs/` |
| Réponses brutes des API | `data/raw/<source>/<ville>/` |
| Tables traitées, panel, découpages | `data/processed/` |
| Origine, licence, empreinte de chaque fichier | `data/manifest.yaml` |
| Prévisions date par date | `reports/forecasts/` |
| Métriques, tests, recommandations | `reports/` |
| Modèles et version en production | `models/registry/` |

Table: Où trouver quoi.

## 8.2 Pratiques appliquées

- **Reproductibilité.** Graine fixée, configuration hors du code, cache brut jamais réécrit, reprise après interruption.
- **Contrats de données.** Un schéma Pandera par table ; une table invalide n'est jamais écrite.
- **Tests.** Données, anti-fuite temporelle, tests statistiques comparés à R, économie, registre, API, non-régression des métriques.
- **Suivi d'expériences.** Chaque version de modèle est journalisée dans MLflow avec ses paramètres, ses métriques, le commit et la graine.
- **Registre et promotion.** Un modèle ne passe en production que s'il bat la climatologie **et** la version en place, sur les mêmes
  dates de test. Le retour arrière tient en une commande. L'empreinte SHA256 est vérifiée à chaque chargement.
- **Service.** Une API versionnée (`/v1`) renvoie les prévisions avec leur intervalle et journalise chaque requête.

## 8.3 Registre

{table(reg, "Versions enregistrées.") if reg is not None else "Registre vide : lancer `python -m solarvision.cli register`."}
{production}

## 8.4 Suivi

{monitoring or "Suivi non calculé : lancer `python -m solarvision.cli monitor`."}
La dérive est mesurée sur l'écart à la moyenne du même mois, pour ne pas confondre la saison avec un changement.

## 8.5 Ce qui n'est pas fait

- **Tout est local.** Ni stockage distant, ni déploiement dans le nuage, ni réentraînement automatique.
- **DVC.** Le pipeline est décrit dans `dvc.yaml`, mais DVC n'est pas installé sur la machine : `dvc repro` n'a pas été exécuté.
- **Docker et intégration continue.** Les fichiers de la v2 sont écrits (`infra/`, `.github/workflows/`) ; l'image n'a pas été construite
  et la chaîne d'intégration n'a pas tourné.
- **Python.** Le projet déclare Python 3.12 ou plus ; les calculs ont été faits avec Python 3.14, seule version installée.
- **Suivi.** Les statistiques de dérive sont calculées avec scipy, Evidently n'étant pas installé ; aucune alerte n'est envoyée.
"""


def chapter_llm(c: Context) -> str:
    def filled(name: str) -> str | None:
        path = LLM_DIR / name
        if not path.exists():
            return None
        text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S).strip()
        return text if text and "À RÉDIGER" not in text and "À COMPLÉTER" not in text else None

    expert = filled("interpretation_experte.md")
    comparison = filled("comparaison_humain_llm.md")
    legacy = (ROOT / "llm" / "interpretation_experte.md").exists()
    body = ["""# 9. IA générative et LLM

## 9.1 Protocole

1. **Les chiffres d'abord.** Les statistiques fournies au LLM sont produites par le code (`reports/exploration_stats.csv`,
   `docs/llm/statistiques_pour_llm.md`) : moyenne, variance, skewness, kurtosis, tests ADF et KPSS, erreurs des modèles.
2. **L'interprétation humaine avant le LLM.** Notre propre lecture est rédigée avant d'envoyer le moindre prompt.
3. **Trois prompts.** Hypothèses de modèles ; explication pour un décideur ; recommandations de gestion, avec les limites que
   le LLM formule lui-même.
4. **La comparaison.** Chaque affirmation du LLM est rangée : convergence, erreur, simplification, causalité inventée, p-value inventée.

## 9.2 Notre interprétation
"""]
    body.append(expert if expert else
                "*Section à rédiger par le groupe, avant de solliciter le LLM (`docs/llm/interpretation_experte.md`). Elle n'est "
                "volontairement pas rédigée par un outil : le barème note la capacité à repérer les erreurs du LLM.*")
    body.append("\n## 9.3 Comparaison avec le LLM\n")
    body.append(comparison if comparison else
                "*Tableau à compléter par le groupe (`docs/llm/comparaison_humain_llm.md`) une fois les trois réponses obtenues.*")
    if legacy:
        body.append("\n**Première étude.** La section équivalente de l'étude sur 9 villes (protocole, trois prompts, réponses intégrales, "
                    "comparaison) figure dans le rapport historique `rapport/` et dans le dossier `llm/`.")
    return "\n".join(body) + "\n"


def chapter_evaluation(c: Context) -> str:
    if c.wide is None:
        return "# 10. Prévision et évaluation\n\nÉvaluation non calculée : lancer `python -m solarvision.cli evaluate`.\n"
    m = c.mean_rmse()
    cov = {} if c.coverage is None else c.coverage.groupby("modele")["couverture_ic95"].mean().to_dict()
    tests = {}
    if c.dm is not None:
        d = c.dm[(c.dm["technologie"] == c.reference) & (c.dm["perte"] == "squared") & c.dm["horizon"].isin([1, 7])]
        tests = d.groupby(["modele", "horizon"])["meilleur_que_reference"].sum().to_dict()
    n_cities = c.wide[c.wide["technologie"] == c.reference]["ville"].nunique()
    unique = pd.DataFrame({
        "Modèle": [MODEL.get(x, x) for x in m["modele"]], "Scénario": [SCENARIO[s] for s in m["scenario"]],
        "MSE": [n(v, 3) for v in m["MSE"]], "RMSE": [n(v, 4) for v in m["RMSE"]], "MAE": [n(v, 4) for v in m["MAE"]],
        "MAPE (%)": [n(v, 1) for v in m["MAPE"]], "WAPE (%)": [n(v, 1) for v in m["WAPE"]],
        "RMSE J+1": [n(v, 3) for v in m["h1"]], "RMSE J+7": [n(v, 3) for v in m["h7"]],
        "IC 95 % (%)": [n(cov.get(x), 1) for x in m["modele"]],
        "Mieux à J+1": ["—" if x == "climatologie" else f"{int(tests.get((x, 1), 0))}/{n_cities}" for x in m["modele"]],
        "Mieux à J+7": ["—" if x == "climatologie" else f"{int(tests.get((x, 7), 0))}/{n_cities}" for x in m["modele"]]})
    r = m.set_index("modele")
    clim, pers = r.loc["climatologie"], r.loc["persistance"]
    ante = m[(m["scenario"] == "ex_ante") & ~m["modele"].isin(["climatologie", "persistance"])]
    best = ante.iloc[0]
    post = m[m["scenario"] == "ex_post"]
    winners = c.summary["meilleur_modele_ex_ante"].value_counts() if c.summary is not None else pd.Series(dtype=int)
    gain = c.summary["gain_vs_climatologie_pct"] if c.summary is not None else pd.Series(dtype=float)
    post_text = "" if post.empty else (
        f"- **Avec la météo observée, l'erreur baisse nettement.** Le meilleur modèle ex post, {MODEL.get(post.iloc[0]['modele'])}, descend à "
        f"{n(post.iloc[0]['RMSE'], 4)}, soit {n(100 * (1 - post.iloc[0]['RMSE'] / clim['RMSE']), 0)} % de moins que la climatologie. C'est une "
        f"borne optimiste : la météo observée remplace une prévision météo, qui serait imparfaite.\n")
    sens = ""
    if c.sensitivity is not None:
        s = c.sensitivity
        sens = (f"\n\n**Sensibilité aux jours imputés.** Les jours imputés sont tous dans l'apprentissage. Trois modèles ont été réestimés sans "
                f"eux dans {s['ville'].nunique()} villes, puis évalués sur le même test : le RMSE change au plus de "
                f"{n(s['ecart_rmse'].abs().max(), 5)} kWh/kWc. Ces jours n'influencent pas les conclusions.")
    gap = ""
    if c.gap is not None:
        g = c.gap.set_index("variante")["rmse_tunis"]
        raw = [k for k in g.index if "lissage 1 j" in k]
        smooth = [k for k in g.index if "lissage 31 j" in k and "apprentissage" in k]
        if raw and smooth:
            gap = (f"\n\n**Un écart expliqué.** Une première version de ce protocole donnait à Tunis une climatologie plus mauvaise que celle de "
                   f"l'étude historique. La cause est la définition de la normale : sans lissage, la moyenne par jour de l'année donne "
                   f"{n(g[raw[0]], 4)} ; lissée sur 31 jours, {n(g[smooth[0]], 4)}, valeur de l'étude historique. Mesurer l'erreur sur les dates de "
                   f"test plutôt que sur les origines ne change presque rien. Le détail est dans `reports/diagnostic_ecart_climatologie_tunis.csv`.")
    cov_text = ""
    if cov:
        cov_text = ("\n\n**Intervalles.** " + " ; ".join(f"{MODEL.get(k, k)} : {n(v, 1)} %" for k, v in sorted(cov.items()))
                    + ". La cible est 95 %. L'intervalle du LSTM global est conforme : sa marge est le quantile des erreurs absolues sur "
                      "l'année de validation, sans hypothèse de loi. Celui de l'AR(1) suppose des erreurs gaussiennes de variance constante, "
                      "ce que le chapitre 4 contredit : sa couverture moyenne peut être correcte tout en étant trop étroite en hiver.")
    return f"""# 10. Prévision et évaluation

## 10.1 Protocole

Depuis chacune des {c.split['n_test'] - int(max(c.params['horizons'])) + 1} origines du test, chaque modèle prévoit les jours J+1 à J+7
avec les seules observations disponibles à l'origine. **Chaque origine est évaluée** ; les paramètres sont réestimés tous les
{c.params['evaluation']['refit_every_days']} jours. Deux références : la persistance (demain comme aujourd'hui) et la climatologie
(normale saisonnière de l'apprentissage, lissée sur {c.params['features']['climatology_window_days']} jours).

## 10.2 Tableau unique

{table(unique, f"Tous les modèles, moyenne de {n_cities} villes, technologie {c.reference} (kWh/kWc). « Mieux » : villes où le test de Diebold-Mariano conclut que le modèle bat la climatologie.")}
{c.fig("models", "Erreur moyenne des modèles.", "12cm")}
- **Ex ante, les modèles se tiennent de près.** Le meilleur, {MODEL.get(best['modele'])}, a un RMSE moyen de {n(best['RMSE'], 4)}
  contre {n(clim['RMSE'], 4)} pour la climatologie, soit {n(100 * (1 - best['RMSE'] / clim['RMSE']), 1)} % de moins. La persistance
  ({n(pers['RMSE'], 4)}) est loin derrière : reconduire la valeur du jour ignore la saison et amplifie le bruit.
- **Le gain est concentré sur le premier jour.** À J+1, {MODEL.get(best['modele'])} gagne {n(100 * (1 - best['h1'] / clim['h1']), 1)} % sur la
  climatologie ; à J+7, {n(100 * (1 - best['h7'] / clim['h7']), 1)} %. C'est la conséquence directe de la faible persistance mesurée au chapitre 3.
{post_text}- **Le MAPE est trompeur ici.** Il est gonflé par les journées très couvertes, où l'observation est proche de zéro ; le WAPE
  est plus représentatif.

{c.fig("horizon", "Gain sur la climatologie selon l'horizon.", "12cm")}

## 10.3 Par ville

{c.fig("gain", "Gain du meilleur modèle ex ante sur la climatologie, par ville.", "12cm")}
Le meilleur modèle ex ante est {", ".join(f"{MODEL.get(k, k)} dans {v} villes" for k, v in winners.items())}. Le gain sur la
climatologie va de {n(gain.min(), 1)} % à {n(gain.max(), 1)} % (médiane {n(gain.median(), 1)} %). Le tableau complet, avec l'erreur par
horizon et par saison, est dans `reports/synthese_ville.csv`.

## 10.4 Tests de Diebold-Mariano

- **Hypothèse nulle :** le modèle et la climatologie ont la même perte moyenne.
- **Sens :** test unilatéral, l'alternative étant que le modèle fait mieux.
- **Perte :** quadratique (résultats ci-dessus) et absolue (dans `reports/dm_tests.csv`).
- **Variance :** de long terme, sur h - 1 retards, puisque les erreurs à l'horizon h se chevauchent ; correction de
  Harvey-Leybourne-Newbold. Un test automatique vérifie que l'implémentation donne les mêmes statistiques que `forecast::dm.test` en R.
- **Tests multiples :** correction de Holm au seuil de {n(100 * c.params['evaluation']['holm_alpha'], 0)} %. La famille est l'ensemble des
  modèles comparés à la climatologie pour une ville, une technologie, un horizon et une perte.

Les deux dernières colonnes du tableau donnent le résultat : à J+1, {MODEL.get(best['modele'])} bat significativement la climatologie dans
{int(tests.get((best['modele'], 1), 0))} villes sur {n_cities} ; à J+7, dans {int(tests.get((best['modele'], 7), 0))}.{cov_text}{sens}{gap}

## 10.5 Quel modèle pour quel usage ?

- **Sans prévision météo, au-delà de deux jours :** la normale saisonnière. Aucun modèle ne la bat durablement.
- **Sans prévision météo, à un ou deux jours :** un modèle ex ante. Le modèle AR(1) à termes de Fourier est interprétable et
  rapide à ajuster ; XGBoost et le LSTM global sont un peu plus précis mais moins lisibles.
- **Avec une prévision météo :** un modèle qui l'utilise. C'est là qu'est le gain, et c'est la qualité de la prévision météo qui le bornera.
"""


def chapter_discussion(c: Context) -> str:
    missing = "" if not c.missing else f"- **Étude incomplète.** {len(c.missing)} villes sur {len(c.cities)} manquent encore ; les moyennes par pays en dépendent.\n"
    return f"""# 11. Discussion critique

## 11.1 Limites des données et des modèles

- **Données simulées.** La production est simulée par PVGIS pour une installation théorique, sans panne, ombrage ni salissure. Les
  conclusions portent sur la météo et sur les modèles de rendement, pas sur le comportement d'installations réelles.
- **Ex post n'est pas une prévision.** Les modèles ex post reçoivent la météo observée. Avec une vraie prévision météo, leur erreur se
  situerait entre celle des modèles ex post et celle des modèles ex ante ; seule une évaluation avec des prévisions archivées le dirait.
- **Hypothèses violées.** Les résidus ne sont ni gaussiens ni de variance constante : les intervalles analytiques sont approximatifs.
  Les intervalles conformes n'ont pas ce défaut, mais leur marge est la même toute l'année.
- **Prévisibilité faible.** La faible autocorrélation de l'écart à la saison borne ce que tout modèle ex ante peut faire. Les écarts
  entre modèles sont petits devant l'incertitude ; le choix se fait donc aussi sur la lisibilité et le coût.
- **Une seule période de test,** d'environ deux ans.
- **Réseaux non réajustés.** Les réseaux récurrents sont entraînés une fois, alors que les modèles classiques sont réestimés tous les
  {c.params['evaluation']['refit_every_days']} jours : la comparaison leur est légèrement défavorable.
{missing}- **Technologies.** Les écarts entre technologies sont faibles et souvent dans la marge d'incertitude ; ni la dégradation ni la
  fiabilité mécanique ne sont modélisées.
- **Économie.** Toutes les hypothèses de prix et de coût restent à vérifier.

## 11.2 IA générative et séries temporelles

**Avantages.**

- **Accélérer les tâches périphériques :** liste d'hypothèses de modèles, reformulation pour un décideur, documentation, squelette de code.
- **Servir de relecteur naïf :** ses contresens montrent où une définition doit être rendue explicite.
- **Interroger des résultats en langage naturel,** à condition d'ancrer les réponses sur les tableaux produits par le code.

**Inconvénients.**

- **Hallucination statistique :** p-values lues à l'envers ou inventées, chiffres plausibles mais faux. Rien, dans le ton, ne distingue
  une affirmation juste d'une affirmation fausse.
- **Causalités inventées :** une corrélation ou un test de Granger devient une cause.
- **Pas de sens des ordres de grandeur :** un écart de quelques millièmes de kWh/kWc est présenté comme une victoire.
- **Reproductibilité :** la réponse dépend du modèle et de sa version.
- **Responsabilité :** un texte recopié sans relecture engage son auteur sur des erreurs qu'il n'a pas vues.

**Règles retenues.** Rédiger sa propre interprétation avant ; fournir les chiffres dans le prompt ; demander au LLM ses propres limites,
puis les compléter ; vérifier chaque nombre cité ; ne jamais laisser un LLM choisir seul le modèle à déployer.

## 11.3 Prolongements

- Évaluer les modèles avec des prévisions météo archivées, pour remplacer la borne ex post par un scénario opérationnel.
- Ajouter les mesures d'installations réelles.
- Vérifier les hypothèses économiques auprès des sources indiquées.
- Faire tourner le pipeline sous DVC et dans la chaîne d'intégration, puis construire l'image Docker.
"""


def annexes(c: Context) -> str:
    parts = ["# Annexe A. Reproductibilité\n",
             "| Étape | Commande |\n|---|---|\n"
             "| Parcours rapide (3 villes) | `python -m solarvision.cli pipeline --fast` |\n"
             "| Étude complète | `python -m solarvision.cli pipeline` |\n"
             "| Reprise des villes en échec | `python -m solarvision.cli ingest --retry-failed` |\n"
             "| Application et API | `python -m solarvision.cli serve` |\n"
             "| Rapport | `python -m solarvision.cli report` |\n"
             "| Tests | `python -m pytest` |\n"
             "| Dossier R autonome | `Rscript run_all.R` dans le dossier R |\n\nTable: Commandes.\n",
             f"\nGraine : {c.params['seed']}. Bibliothèques : " + ", ".join(f"{k} {v}" for k, v in registry._library_versions().items()) + ".\n"]
    if c.summary is not None:
        s = c.summary.sort_values(["pays", "ville"])
        shown = pd.DataFrame({"Ville": [c.name(x) for x in s["ville"]], "Pays": s["pays"],
                              "Meilleur modèle ex ante": [MODEL.get(x, x) for x in s["meilleur_modele_ex_ante"]],
                              "RMSE": [n(v, 4) for v in s["rmse_meilleur"]], "Climatologie": [n(v, 4) for v in s["rmse_climatologie"]],
                              "Gain (%)": [n(v, 1) for v in s["gain_vs_climatologie_pct"]],
                              "J+1": [n(v, 3) for v in s["rmse_h1"]], "J+7": [n(v, 3) for v in s["rmse_h7"]]})
        parts.append("\n# Annexe B. Résultats par ville\n\n" + table(shown, "Meilleur modèle ex ante par ville (kWh/kWc)."))
    if c.reco is not None:
        r = c.reco.sort_values(["pays", "ville"])
        shown = pd.DataFrame({"Ville": [c.name(x) for x in r["ville"]], "Recommandée": r["technologie_recommandee"],
                              "Score": [n(v, 3) for v in r["score"]], "Deuxième": r["deuxieme_choix"],
                              "Écart": [n(v, 3) for v in r["ecart_score"]],
                              "Probabilité (%)": [n(100 * v, 0) for v in r["probabilite_meilleure"]],
                              "Verdict": ["ex æquo" if t else "nette" for t in r["ex_aequo"]]})
        parts.append("\n# Annexe C. Technologie recommandée par ville\n\n" + table(shown, "Recommandation et incertitude par ville."))
    return "".join(parts)


# --------------------------------------------------------------------------------------------- assemblage
def _pandoc() -> str:
    found = shutil.which("pandoc") or str(Path.home() / "AppData/Local/Pandoc/pandoc.exe")
    if not Path(found).exists() and shutil.which(found) is None:
        raise RuntimeError("pandoc introuvable : l'installer, ou convertir reports/rapport/rapport_v2.md à la main")
    return found


def _word_template(pandoc: str, path: Path) -> None:
    """Modèle Word dérivé de celui de pandoc : corps en 10,5 points, marges de 2 cm, tableaux plus petits."""
    default = subprocess.run([pandoc, "--print-default-data-file", "reference.docx"], capture_output=True, check=True).stdout
    raw = path.with_name("_defaut.docx")
    raw.write_bytes(default)
    with zipfile.ZipFile(raw) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/styles.xml":
                x = data.decode("utf-8")
                x = x.replace('<w:sz w:val="24" />', '<w:sz w:val="21" />', 1).replace('<w:szCs w:val="24" />', '<w:szCs w:val="21" />', 1)
                x = re.sub(r'(<w:style [^>]*w:styleId="Compact"[^>]*>.*?</w:pPr>)',
                           r'\1<w:rPr><w:sz w:val="16" /><w:szCs w:val="16" /></w:rPr>', x, count=1, flags=re.S)
                data = x.encode("utf-8")
            elif item.filename == "word/document.xml":
                data = re.sub(r'w:(top|right|bottom|left)="1440"', r'w:\1="1134"', data.decode("utf-8")).encode("utf-8")
            dst.writestr(item, data)
    raw.unlink()


CSS = """@page { size: A4; margin: 18mm 17mm 20mm 17mm; }
html { font-size: 10pt; }
body { font-family: "Segoe UI", system-ui, sans-serif; color: #0b0b0b; line-height: 1.45; max-width: none; margin: 0; padding: 0; background: #fff; }
header#title-block-header { text-align: center; margin: 60mm 0 20mm; break-after: page; }
header#title-block-header .title { font-size: 22pt; line-height: 1.25; margin-bottom: 8mm; }
header#title-block-header .subtitle { font-size: 12pt; color: #52514e; font-weight: 400; }
header#title-block-header .author, header#title-block-header .date { font-size: 11pt; color: #52514e; margin-top: 4mm; }
nav#TOC { font-size: 9pt; }
nav#TOC > ul { list-style: none; padding-left: 0; }
nav#TOC ul ul { list-style: none; padding-left: 14px; }
nav#TOC a { color: #0b0b0b; text-decoration: none; }
h1 { font-size: 15pt; margin: 0 0 6pt; break-before: page; break-after: avoid; }
h2 { font-size: 12pt; margin: 14pt 0 4pt; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
ul, ol { padding-left: 16px; }
li { margin: 2pt 0; }
figure { margin: 8pt 0; text-align: center; break-inside: avoid; }
figure img, p > img { max-width: 100%; height: auto; }
figcaption { font-size: 8.5pt; color: #52514e; margin-top: 2pt; }
table { border-collapse: collapse; width: 100%; font-size: 8pt; margin: 6pt 0 2pt; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border-bottom: 0.5pt solid #c3c2b7; padding: 2.5pt 4pt; vertical-align: top; text-align: left; }
th { background: #f0efec; font-weight: 600; }
caption { caption-side: bottom; font-size: 8.5pt; color: #52514e; text-align: left; padding-top: 3pt; }
code { font-family: Consolas, monospace; font-size: 8.5pt; background: #f0efec; padding: 0 2px; }
blockquote { margin: 6pt 0; padding: 4pt 10pt; border-left: 2pt solid #fab219; background: #fcfcfb; }
"""


def build(fast: bool = False) -> dict[str, Path]:
    """Assemble le rapport, écrit le Markdown, puis le convertit en Word et en PDF."""
    c = Context(fast)
    make_figures(c)
    out = c.reports / "rapport"
    out.mkdir(parents=True, exist_ok=True)
    report = c.params["report"]
    chapters = [chapter_introduction(c), chapter_data(c), chapter_exploration(c), chapter_classical(c), chapter_deep(c),
                chapter_technologies(c), chapter_economics(c), chapter_mlops(c), chapter_llm(c), chapter_evaluation(c),
                chapter_discussion(c), annexes(c)]
    header = (f'---\ntitle: "{report["title"]}"\nsubtitle: "{report["subtitle"]}"\nauthor: "{report["authors"]}"\n'
              f'date: "{report["date"]}"\nlang: fr\n---\n\n')
    body = "\n".join(chapters)
    markdown = out / "rapport_v2.md"
    markdown.write_text(header + body, encoding="utf-8")
    outputs = {"markdown": markdown}
    pandoc = _pandoc()
    common = ["--from", "markdown", "--toc", "--toc-depth=2", "--metadata", "toc-title=Sommaire", "--resource-path", "."]
    # Word : un saut de page avant chaque chapitre, inséré seulement dans la copie destinée à Word.
    word_source = out / "_word.md"
    word_source.write_text(header + re.sub(r"(?m)^# ", lambda _: PAGE_BREAK + "\n# ", body), encoding="utf-8")
    template = out / "_modele.docx"
    _word_template(pandoc, template)
    subprocess.run([pandoc, word_source.name, *common, "-o", f"{NAME}.docx", "--reference-doc", template.name], cwd=out, check=True)
    outputs["docx"] = out / f"{NAME}.docx"
    (out / "impression.css").write_text(CSS, encoding="utf-8")
    subprocess.run([pandoc, markdown.name, *common, "-o", "_rapport.html", "--standalone", "--embed-resources", "--css", "impression.css"],
                   cwd=out, check=True)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto((out / "_rapport.html").as_uri(), wait_until="load")
            page.pdf(path=str(out / f"{NAME}.pdf"), format="A4", print_background=True, display_header_footer=True,
                     header_template="<div></div>",
                     footer_template="<div style='font-size:8px;color:#666;width:100%;text-align:center'>"
                                     "<span class='pageNumber'></span> / <span class='totalPages'></span></div>",
                     margin={"top": "18mm", "bottom": "20mm", "left": "17mm", "right": "17mm"})
            browser.close()
        outputs["pdf"] = out / f"{NAME}.pdf"
    except Exception as err:                               # noqa: BLE001 - sans Chromium, le Word reste disponible
        print(f"PDF non produit ({type(err).__name__}) : ouvrir le fichier Word et l'exporter en PDF.")
    for temp in ("_rapport.html", "_word.md", "_modele.docx"):
        (out / temp).unlink(missing_ok=True)
    return outputs
