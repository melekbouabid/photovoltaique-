"""Construit notebooks/solarvision_v2.ipynb : le parcours de la v2, étape par étape, en mode rapide.

Le notebook appelle le paquet `solarvision` : il ne recopie pas le code, il le fait tourner et montre
ce qu'il produit. En mode rapide (3 villes), il s'exécute en quelques minutes ; les téléchargements
déjà en cache ne sont pas refaits.

Usage : python scripts/build_notebook.py
        python -m nbconvert --to notebook --execute --inplace notebooks/solarvision_v2.ipynb
"""
from __future__ import annotations

import nbformat as nbf

from solarvision.config import ROOT

CELLS: list[tuple[str, str]] = [
    ("md", """# SolarVision v2 — parcours de bout en bout

Prévision de la production photovoltaïque journalière (1 kWc) de J+1 à J+7, comparaison de trois technologies
de modules, bénéfices économiques.

Ce notebook déroule toutes les étapes sur **trois villes** (Paris, Tunis, Madrid) : c'est le mode rapide du pipeline.
L'étude complète se lance par `python -m solarvision.cli pipeline`. L'étude statistique détaillée de Tunis
(ACF et PACF, STL, ARIMA et SARIMA, VAR, Granger, Johansen, GARCH) est dans `mini_projet_python.ipynb` et dans le notebook R.

Mettre `FAST = False` pour travailler sur toutes les villes déjà traitées."""),
    ("code", """# Versions et graine : le notebook doit donner les mêmes résultats d'une exécution à l'autre.
import platform, random, warnings
from importlib import metadata

import numpy as np
import pandas as pd

from solarvision.config import DATA, REPORTS, load_cities, load_params, select_cities

warnings.filterwarnings("ignore")
FAST = True
params = load_params()
random.seed(params["seed"]); np.random.seed(params["seed"])
print("Python", platform.python_version(), "| graine", params["seed"])
for lib in ("numpy", "pandas", "statsmodels", "xgboost", "prophet", "torch", "scikit-learn", "pandera"):
    print(f"  {lib:14s} {metadata.version(lib)}")
pd.set_option("display.width", 160); pd.set_option("display.max_columns", 20)"""),
    ("md", """## 1. Données

Trois sources : PVGIS (production simulée de trois technologies), Open-Meteo (météo ERA5) et NASA POWER
(rayonnement de contrôle). Les réponses sont mises en cache ; rien n'est retéléchargé s'il est déjà présent."""),
    ("code", """# Téléchargement de ce qui manque, puis construction des tables journalières (imputation et contrôles compris).
from solarvision.data import ingest, process

cities = select_cities(fast=FAST)
root = DATA / "fast" if FAST else DATA
ingest.run_downloads(cities)
quality = process.process_all(cities, root)
quality[["ville", "lignes", "jours_imputes", "manquants_pct", "statut"]]"""),
    ("code", """# Table traitée de Tunis : les trois séries de production et le drapeau d'imputation.
tunis = pd.read_csv(root / "processed" / "tunis.csv", parse_dates=["date"]).set_index("date")
print(tunis.describe().loc[["mean", "std", "min", "max"]].round(3))
print("\\nJours dont le rayonnement PVGIS manquait (corrigés avec NASA POWER) :")
print([str(d.date()) for d in tunis.index[tunis["jour_impute_pvgis"] == 1]])"""),
    ("md", """## 2. Panel et découpage

Une ligne par ville et par jour. Chaque colonne a un rôle : cible, variable **ex ante** (connue avant le jour visé)
ou variable **ex post** (météo observée le jour même). Le découpage est chronologique : 90 % des jours les plus
anciens pour l'apprentissage."""),
    ("code", """from solarvision.features import panel as pm

panel = pm.build_panel(root, allow_partial=True, cities=cities)
splits, roles = pm.load_splits(root), pm.load_roles(root)
print(f"Panel : {len(panel)} lignes, {panel.shape[1]} colonnes, {panel['ville'].nunique()} villes")
print("Découpage de Tunis :", splits["tunis"])
print({k: len(v) for k, v in roles.items()})"""),
    ("md", """## 3. Exploration

Statistiques sur l'apprentissage seulement. L'ADF a pour hypothèse nulle une racine unitaire ; le KPSS a pour
hypothèse nulle la stationnarité."""),
    ("code", """from solarvision.reporting import exploration

reports = REPORTS / "fast" if FAST else REPORTS
stats = exploration.run(panel, splits, reports)
stats[["ville", "moyenne", "variance", "skewness", "kurtosis_exces", "rapport_saisonnier", "acf1_ecart_normale",
       "adf_p_ecart_normale", "kpss_p_ecart_normale", "stationnaire_ecart_normale"]].round(3)"""),
    ("code", """# La série de Tunis et sa normale saisonnière (calculée sur l'apprentissage, lissée sur 31 jours).
import matplotlib.pyplot as plt
from solarvision.reporting import figures  # applique le style commun des figures

t = panel[panel["ville"] == "tunis"].set_index("date")
fig, ax = plt.subplots(figsize=(10, 3.2))
ax.plot(t.index, t["pv_crystSi_kwh_kwc"], color=figures.MUTED, linewidth=0.4, label="Production journalière")
ax.plot(t.index, t["normale_crystSi"], color=figures.SERIES[0], linewidth=2, label="Normale saisonnière")
ax.axvline(pd.Timestamp(splits["tunis"]["test_debut"]), color=figures.AXIS, linestyle="--")
ax.set_ylabel("kWh/kWc par jour"); ax.set_title("Tunis : production et normale saisonnière"); ax.legend(loc="lower left", ncol=2)
plt.show()"""),
    ("md", """## 4. Modèles classiques

Deux références (persistance, climatologie), une régression harmonique à erreurs AR(1), XGBoost en prévision directe
et Prophet. Depuis **chaque** jour du test, chaque modèle prévoit J+1 à J+7 ; les paramètres sont réestimés tous les 30 jours."""),
    ("code", """# Le modèle statistique à la main, sur Tunis : estimation, puis prévision depuis chaque origine.
from solarvision.evaluation.metrics import compute_metrics
from solarvision.models import baselines, statistical
from solarvision.models.protocol import origins, target_matrix
from solarvision.models.train import FOURIER, load_city

series = load_city("tunis", root)
y, exog = series.frame["pv_crystSi_kwh_kwc"].to_numpy(), series.frame[FOURIER].to_numpy()
pos = origins(series.n, series.n_train)
fit = statistical.fit_ar1_regression(y[: series.n_train], exog[: series.n_train])
print(f"AR(1) : phi = {fit['phi']:.3f}, écart-type des innovations = {fit['sigma2'] ** 0.5:.3f} kWh/kWc, BIC = {fit['bic']:.0f}")
observed = target_matrix(y, pos)
candidates = {"persistance": baselines.persistence(y, pos),
              "climatologie": baselines.climatology(series.frame["normale_crystSi"].to_numpy(), pos),
              "arima_fourier": statistical.forecast_ar1_regression(y, exog, pos)["predicted"]}
pd.DataFrame({k: compute_metrics(observed, v) for k, v in candidates.items()}).T.round(4)"""),
    ("code", """# Tous les modèles classiques, sur toutes les villes du mode choisi (reprise : une ville déjà traitée n'est pas refaite).
from solarvision.models import train as tr

results = tr.train_all(sorted(splits), fast=FAST, workers=3)
pd.DataFrame(results)[["ville", "statut"]]"""),
    ("md", """## 5. Réseaux récurrents

LSTM et GRU par ville, en scénario ex ante puis ex post, et un LSTM global entraîné sur toutes les villes.
La cible est l'écart à la normale saisonnière. En mode rapide, l'entraînement est limité à trois époques :
il vérifie la chaîne, pas la performance."""),
    ("code", """from solarvision.models import deep as dp

for city in sorted(splits):
    print(dp.run_city(city, fast=FAST))
print(dp.run_global(sorted(splits), fast=FAST))
curves = pd.read_csv(dp.collect_curves(FAST))
curves[curves["ville"] == "tunis"].pivot_table(index="epoque", columns="modele", values="perte_validation").round(4)"""),
    ("md", """## 6. Évaluation

Mêmes origines, mêmes horizons, mêmes métriques pour tous les modèles. Les modèles **ex post** connaissent la météo
observée des jours visés : c'est une borne optimiste, jamais une performance opérationnelle."""),
    ("code", """from solarvision.evaluation import evaluate as ev

tables = ev.run(reports)
wide = tables["metrics_wide"]
view = wide[(wide["horizon"] == "tous") & (wide["technologie"] == "crystSi")]
view.pivot_table(index=["scenario", "modele"], columns="ville", values="RMSE").round(4)"""),
    ("code", """# Diebold-Mariano contre la climatologie (correction HLN, variance sur h - 1 retards, correction de Holm par famille).
dm = tables["dm_tests"]
dm[(dm["ville"] == "tunis") & (dm["technologie"] == "crystSi") & (dm["perte"] == "squared") & dm["horizon"].isin([1, 7])][
    ["modele", "scenario", "horizon", "dm_stat", "p_unilaterale", "p_holm_unilaterale", "taille_famille", "meilleur_que_reference"]].round(4)"""),
    ("code", """tables["synthese_ville"][["ville", "meilleur_modele_ex_ante", "rmse_meilleur", "rmse_climatologie",
                           "gain_vs_climatologie_pct", "gain_h1_pct", "gain_h7_pct"]].round(3)"""),
    ("md", """## 7. Technologies et économie

Le score de fiabilité est calculé à partir de cinq critères ; quand l'écart entre deux technologies tient dans la marge
d'incertitude, elles sont déclarées ex æquo. Les hypothèses économiques sont **à vérifier** (`TODO_VERIFY`)."""),
    ("code", """from solarvision.recommender import reliability

reco = reliability.compute(panel, wide, ev.load_forecasts(reports), reports)
reco["recommendation"][["ville", "technologie_recommandee", "score", "deuxieme_choix", "ecart_score",
                        "probabilite_meilleure", "ex_aequo"]].round(3)"""),
    ("code", """from solarvision.economics import simulate

eco = simulate.run(panel, reports, wide)
eco["ranking"][["ville", "meilleure_technologie_van", "van_p10", "van_p50", "van_p90", "temps_retour_p50",
                "ecart_non_concluant"]].round(1)"""),
    ("md", """## 8. Registre et suivi

Un modèle n'est promu que s'il bat la climatologie **et** la version en place, sur les mêmes dates de test.
En mode rapide, le registre est séparé (`models/registry_fast`) : il ne remplace jamais le modèle de l'étude complète."""),
    ("code", """from solarvision.config import MODELS
from solarvision.mlops import candidates, registry
from solarvision.monitoring import drift

if FAST:
    registry.use(MODELS / "registry_fast")
for r in candidates.register_and_promote(FAST):
    print(r["nom"], r.get("version"), "->", r["statut"])
active = registry.current()
summary = drift.run(panel, splits, ev.load_forecasts(reports), active["nom"] if active else "arima_fourier", reports)
print("\\nDérive :", summary["derive"], "| jours en alerte d'erreur :", round(summary["part_des_jours_en_alerte_erreur_pct"], 1), "%")"""),
    ("md", """## 9. Pour aller plus loin

- Application et API : `python -m solarvision.cli serve --fast`, puis http://127.0.0.1:8001
- Rapport : `python -m solarvision.cli report --fast`
- Section IA générative : `python -m solarvision.cli llm-pack --fast`, puis les gabarits de `docs/llm/`
- Étude complète : `python -m solarvision.cli pipeline`"""),
]


def main() -> None:
    notebook = nbf.v4.new_notebook()
    notebook["cells"] = [nbf.v4.new_markdown_cell(text) if kind == "md" else nbf.v4.new_code_cell(text) for kind, text in CELLS]
    notebook["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                            "language_info": {"name": "python"}}
    path = ROOT / "notebooks" / "solarvision_v2.ipynb"
    nbf.write(notebook, path)
    print(path)


if __name__ == "__main__":
    main()
