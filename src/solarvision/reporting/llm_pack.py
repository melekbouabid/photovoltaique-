"""Dossier de travail de la section « IA générative » : statistiques, prompts et gabarits.

Ce module prépare ce qui peut l'être par le code :
- les statistiques à fournir au LLM (tout vient des tableaux de reports/) ;
- les trois prompts, qui citent ces statistiques pour que chaque affirmation du LLM soit vérifiable ;
- des gabarits vides pour ce qui revient à l'étudiant.
Il n'écrit JAMAIS l'interprétation experte ni la comparaison : c'est le travail noté de l'étudiant.
Un fichier déjà rempli par l'étudiant n'est jamais écrasé.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from solarvision.config import ROOT, load_cities, load_params
from solarvision.reporting.report import MODEL, MONTH_NAMES, SCENARIO, n, table

LLM_DIR = ROOT / "docs" / "llm"
MARKER_WRITE = "À RÉDIGER"
MARKER_FILL = "À COMPLÉTER"


def statistics_markdown(exploration: pd.DataFrame, wide: pd.DataFrame, city: str = "tunis") -> str:
    """Fiche de statistiques d'une ville, prête à être collée dans un prompt."""
    params = load_params()
    reference = params["pv"]["reference_technology"]
    e = exploration[exploration["ville"] == city].iloc[0]
    desc = pd.DataFrame([{"Statistique": k, "Valeur": v} for k, v in [
        ("Nombre de jours (apprentissage)", n(e["jours_apprentissage"], 0)),
        ("Moyenne (kWh/kWc par jour)", n(e["moyenne"], 3)), ("Variance", n(e["variance"], 3)),
        ("Écart-type", n(e["ecart_type"], 3)), ("Minimum", n(e["minimum"], 3)), ("Maximum", n(e["maximum"], 3)),
        ("Skewness", n(e["skewness"], 3)), ("Kurtosis (excès)", n(e["kurtosis_exces"], 3)),
        (f"Mois le plus bas ({MONTH_NAMES[int(e['mois_le_plus_bas']) - 1]})", n(e["moyenne_mois_bas"], 2)),
        (f"Mois le plus haut ({MONTH_NAMES[int(e['mois_le_plus_haut']) - 1]})", n(e["moyenne_mois_haut"], 2)),
        ("Part de la variance portée par la normale saisonnière (%)", n(100 * e["part_variance_saisonniere"], 1)),
        ("Autocorrélation à 1 jour de l'écart à la normale", n(e["acf1_ecart_normale"], 3)),
        ("Autocorrélation à 2 jours", n(e["acf2_ecart_normale"], 3)),
        ("Autocorrélation à 7 jours", n(e["acf7_ecart_normale"], 3))]])
    tests = pd.DataFrame([
        {"Série": "production brute", "ADF (stat)": n(e["adf_stat_brute"], 2), "ADF (p)": n(e["adf_p_brute"], 4),
         "KPSS (stat)": n(e["kpss_stat_brute"], 3), "KPSS (p)": n(e["kpss_p_brute"], 3)},
        {"Série": "écart à la normale saisonnière", "ADF (stat)": n(e["adf_stat_ecart_normale"], 2), "ADF (p)": n(e["adf_p_ecart_normale"], 4),
         "KPSS (stat)": n(e["kpss_stat_ecart_normale"], 3), "KPSS (p)": n(e["kpss_p_ecart_normale"], 3)}])
    m = wide[(wide["ville"] == city) & (wide["technologie"] == reference)]
    total = m[m["horizon"] == "tous"].set_index("modele")
    by_h = m[m["horizon"].isin(["1", "7"])].pivot_table(index="modele", columns="horizon", values="RMSE")
    errors = pd.DataFrame([{"Modèle": MODEL.get(k, k), "Scénario": SCENARIO[r["scenario"]], "RMSE": n(r["RMSE"], 4), "MAE": n(r["MAE"], 4),
                            "WAPE (%)": n(r["WAPE"], 1), "RMSE à J+1": n(by_h.loc[k, "1"], 3), "RMSE à J+7": n(by_h.loc[k, "7"], 3)}
                           for k, r in total.sort_values(["scenario", "RMSE"]).iterrows()])
    name = load_cities()[city].nom
    return f"""# Statistiques à fournir au LLM — {name}

Fichier généré par `python -m solarvision.cli llm-pack`. Ne pas le modifier à la main : il est recalculé à partir de
`reports/exploration_stats.csv` et de `reports/metrics_wide.csv`.

Série : production journalière d'une installation photovoltaïque de 1 kWc à {name} (silicium cristallin, plein sud, pente
optimale), simulée par PVGIS, de {params['period']['start_year']} à {params['period']['end_year']}. Les statistiques sont
calculées sur l'échantillon d'apprentissage.

## Statistiques descriptives

{table(desc)}
## Tests de stationnarité

ADF : hypothèse nulle = racine unitaire. KPSS : hypothèse nulle = stationnarité. La p-value du KPSS est bornée entre 0,01 et 0,10.

{table(tests)}
## Erreurs de prévision sur l'échantillon de test (J+1 à J+7, kWh/kWc)

« Ex ante » : le modèle ne connaît rien du futur. « Ex post » : il reçoit la météo observée des jours visés.

{table(errors)}"""


PROMPTS = {
    1: ("hypotheses", "Hypothèses de modèles",
        "Tu es statisticien, spécialiste des séries temporelles. Voici les statistiques d'une série journalière.\n"
        "1. Propose trois modèles de prévision adaptés à cette série, du plus simple au plus élaboré.\n"
        "2. Pour chacun, cite la statistique ci-dessous qui justifie ton choix.\n"
        "3. Dis quel ordre de différenciation tu retiens et pourquoi.\n"
        "4. Dis ce que tu attends de chaque modèle à l'horizon de 1 jour puis de 7 jours.\n"
        "N'invente aucun chiffre : n'utilise que ceux qui te sont donnés."),
    2: ("vulgarisation", "Explication pour un décideur",
        "Tu t'adresses au responsable d'un parc de toitures solaires, qui n'est pas statisticien.\n"
        "En 200 mots au plus, explique-lui ce que disent les résultats ci-dessous : peut-il se fier à une prévision à 7 jours,\n"
        "et que gagnerait-il à disposer d'une prévision météo ?\n"
        "N'invente aucun chiffre : n'utilise que ceux qui te sont donnés."),
    3: ("recommandations", "Recommandations de gestion et limites",
        "À partir des résultats ci-dessous, donne trois recommandations de gestion à l'exploitant d'un parc de toitures solaires.\n"
        "Puis écris toi-même la liste des limites de ton analyse : ce que ces chiffres ne permettent pas de conclure,\n"
        "les hypothèses que tu as faites, et ce qu'il faudrait vérifier avant d'agir.\n"
        "N'invente aucun chiffre : n'utilise que ceux qui te sont donnés."),
}

TEMPLATES = {
    "interpretation_experte.md": f"""# Notre interprétation — à rédiger AVANT de solliciter le LLM

<!-- {MARKER_WRITE} par le groupe. Ce fichier n'est volontairement pas rédigé par un outil :
     le barème note votre capacité à repérer les erreurs du LLM, ce qui suppose d'avoir d'abord votre propre lecture.
     Supprimez ce commentaire et la ligne « {MARKER_WRITE} » quand le texte est écrit. -->

{MARKER_WRITE}

Points à traiter, à partir de `statistiques_pour_llm.md` et du rapport :

1. Que disent la moyenne, la variance, le skewness et le kurtosis de la série ?
2. Que concluent l'ADF et le KPSS, et quel ordre de différenciation en découle ?
3. Que dit l'autocorrélation de l'écart à la normale sur ce qu'un modèle peut prévoir ?
4. Quels modèles retenez-vous, et qu'attendez-vous d'eux à 1 jour puis à 7 jours ?
5. Que montrent les erreurs mesurées, ex ante puis ex post ?
6. Quelles recommandations pour un exploitant, et avec quelles limites ?
""",
    "comparaison_humain_llm.md": f"""<!-- {MARKER_FILL} par le groupe, une fois les trois réponses obtenues. Supprimez ce commentaire et la ligne « {MARKER_FILL} ». -->

{MARKER_FILL}

| Affirmation du LLM | Prompt | Catégorie | Vérification (chiffre, fichier ou test) |
|---|---|---|---|
| | | convergence | |
| | | erreur | |
| | | simplification | |
| | | causalité inventée | |
| | | p-value inventée | |

Catégories : **convergence** (le LLM dit comme nous), **erreur** (affirmation fausse), **simplification** (vraie mais incomplète),
**causalité inventée** (un lien devenu une cause), **p-value inventée** (un chiffre ou un test qui n'était pas dans le prompt).
""",
}


def build(exploration: pd.DataFrame, wide: pd.DataFrame, city: str = "tunis", folder: Path = LLM_DIR) -> list[str]:
    """Écrit les statistiques et les prompts ; crée les gabarits seulement s'ils n'existent pas."""
    folder.mkdir(parents=True, exist_ok=True)
    stats = statistics_markdown(exploration, wide, city)
    (folder / "statistiques_pour_llm.md").write_text(stats, encoding="utf-8")
    log = ["statistiques_pour_llm.md (généré)"]
    data_block = stats.split("\n", 1)[1].split("Série :", 1)[1]
    for number, (slug, title, instruction) in PROMPTS.items():
        (folder / f"prompt_{number}_{slug}.md").write_text(
            f"# Prompt {number} — {title}\n\n{instruction}\n\nSérie :{data_block}", encoding="utf-8")
        log.append(f"prompt_{number}_{slug}.md (généré)")
        answer = folder / f"reponse_{number}.md"
        if not answer.exists():
            answer.write_text(f"<!-- {MARKER_FILL} : coller ici la réponse intégrale du LLM au prompt {number}, sans la modifier.\n"
                              f"     Indiquer le modèle, sa version, la date et les réglages (température, graine). -->\n\n{MARKER_FILL}\n",
                              encoding="utf-8")
            log.append(f"reponse_{number}.md (gabarit vide)")
    for name, content in TEMPLATES.items():
        path = folder / name
        if path.exists():
            log.append(f"{name} (conservé : jamais écrasé)")
        else:
            path.write_text(content, encoding="utf-8")
            log.append(f"{name} (gabarit vide, à remplir par le groupe)")
    return log
