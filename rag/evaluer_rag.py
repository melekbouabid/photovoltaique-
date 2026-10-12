"""Évaluation du RAG : la recherche trouve-t-elle le bon passage, et la réponse contient-elle le bon chiffre ?

Pour chaque question, on connaît le titre (ou un fragment) du passage qui contient la réponse et un mot-clé
attendu dans la réponse. Mesures : présence du bon passage en première position (hit@1) et parmi les quatre
premiers (hit@4, ceux que reçoit le LLM) ; avec --llm, présence du mot-clé dans la réponse rédigée.

Usage : python rag/evaluer_rag.py [--llm]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
from rag.moteur import MoteurRAG, _sans_accents  # noqa: E402

# (question, fragment du titre du passage attendu, mot-clé attendu dans la réponse)
QUESTIONS = [
    ("Quelle ville produit le plus d'électricité solaire par kWc ?", "comparaison des 9 villes", "Tozeur"),
    ("Quelle est la production photovoltaïque moyenne en décembre à Paris ?", "Fiche Paris : production par mois", "décembre"),
    ("Combien produit 1 kWc à Tunis par an ?", "Fiche Tunis : production annuelle", "kWh/kWc"),
    ("Quelle est la pente optimale des modules à Séville ?", "Fiche Séville : production annuelle", "35"),
    ("Combien d'heures de lumière naturelle par jour en hiver à Tozeur ?", "Fiche Tozeur : éclairement", "heures"),
    ("Quel est le meilleur modèle de prévision sans météo ?", "meilleur modèle", "RMSE"),
    ("Comment PVGIS calcule-t-il la production photovoltaïque ?", "Modèle de production photovoltaïque", "température"),
    ("D'où viennent les données de rayonnement de PVGIS ?", "Bases de données utilisées", "SARAH3"),
    ("Qu'est-ce que le test KPSS ?", "Test KPSS", "stationnaire"),
    ("Que signifie la causalité de Granger ?", "Causalité de Granger", "prévi"),
    ("Qu'est-ce qu'un modèle GARCH ?", "ARCH et GARCH", "variance"),
    ("Quelle production moyenne en juillet en Espagne ?", "Comparaison par pays", "juillet"),
    ("Que contient le jeu de données tn_eclairement_journalier.csv ?", "tn_eclairement_journalier.csv", "Tunisie"),
    ("Que mesure la variable besoin_eclairage_h ?", "Dictionnaire des variables", "lux"),
    ("Quelle irradiation le rapport SolarVision supposait-il à Tunis ?", "formule énergétique du rapport", "1 800"),
    ("Pourquoi certains jours PVGIS ont-ils été imputés ?", "Transformations et précautions", "SARAH3"),
]


PAUSE_QUOTA_S = 60


def evaluer(llm: bool = False) -> pd.DataFrame:
    moteur = MoteurRAG()
    lignes = []
    for q, attendu, mot in QUESTIONS:
        t0 = time.time()
        rep = moteur.repondre(q, k=4, llm=llm)
        if llm and rep["mode"] == "extractif":
            # Quota de jetons par minute de l'API Groq atteint : attendre la fenêtre suivante plutôt que de
            # compter une réponse extractive comme une réponse du LLM.
            time.sleep(PAUSE_QUOTA_S)
            rep = moteur.repondre(q, k=4, llm=llm)
        titres = [s["titre"] for s in rep["sources"]]
        rang = next((i + 1 for i, t in enumerate(titres) if _sans_accents(attendu) in _sans_accents(t)), None)
        ligne = {"question": q, "passage attendu": attendu, "rang trouvé": rang, "hit@1": rang == 1,
                 "hit@4": rang is not None, "mode": rep["mode"], "durée (s)": round(time.time() - t0, 1)}
        if llm:
            ligne["mot-clé dans la réponse"] = _sans_accents(mot) in _sans_accents(rep["reponse"])
            ligne["réponse"] = rep["reponse"]
        lignes.append(ligne)
    return pd.DataFrame(lignes)


if __name__ == "__main__":
    avec_llm = "--llm" in sys.argv
    tab = evaluer(avec_llm)
    sortie = ICI.parent / "resultats" / ("rag_evaluation_llm.csv" if avec_llm else "rag_evaluation.csv")
    tab.to_csv(sortie, index=False)
    pd.set_option("display.width", 200)
    print(tab.drop(columns=[c for c in ("réponse",) if c in tab]).to_string(index=False))
    print(f"\nhit@1 = {tab['hit@1'].mean():.0%} ; hit@4 = {tab['hit@4'].mean():.0%}"
          + (f" ; mot-clé présent dans la réponse = {tab['mot-clé dans la réponse'].mean():.0%}" if avec_llm else ""))
    print("Résultats écrits dans", sortie)
