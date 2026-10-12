"""Assemble le rapport (corps + tableaux tirés des résultats + annexes LLM) puis le convertit avec pandoc.

Les tableaux chiffrés ne sont pas recopiés à la main : ils sont produits ici à partir des fichiers de
resultats/ écrits par les notebooks, ce qui garantit que le rapport et le code disent la même chose.

Usage : python rapport/construire_rapport.py [chemin_vers_pandoc]
Sorties : Rapport_solarvision_series_temporelles.docx et .pdf (PDF via xelatex, s'il est installé).
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

import pandas as pd

ICI = pathlib.Path(__file__).resolve().parent
RACINE = ICI.parent
RES, LLM = RACINE / "resultats", RACINE / "llm"
NOM = "Rapport_solarvision_series_temporelles"

pandoc = sys.argv[1] if len(sys.argv) > 1 else (shutil.which("pandoc")
                                                or str(pathlib.Path.home() / "AppData/Local/Pandoc/pandoc.exe"))
if not pathlib.Path(pandoc).exists() and shutil.which(pandoc) is None:
    sys.exit("pandoc introuvable : indiquer son chemin en argument")


def f(v, d=3):
    """Nombre au format français (virgule décimale, espace pour les milliers)."""
    if pd.isna(v):
        return "-"
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def p_val(p):
    return "< 0,001" if p < 0.001 else f(p, 3)


def tableau(lignes, entete, legende):
    md = ["| " + " | ".join(entete) + " |", "|" + "---|" * len(entete)]
    md += ["| " + " | ".join(str(c) for c in l) + " |" for l in lignes]
    return "\n".join(md) + f"\n\nTable: {legende}\n"


def t_jeux():
    cat = json.loads((RACINE / "data" / "catalogue_datasets.json").read_text(encoding="utf-8"))
    lignes = [(f"`{c['fichier'].split('/')[-1]}`", c["theme"], c["pays"], f(c["lignes"], 0), c["colonnes"],
               f"{c['periode'][0][:7]} à {c['periode'][1][:7]}" if c["periode"] else "-") for c in cat]
    return tableau(lignes, ["Fichier", "Thème", "Pays", "Lignes", "Colonnes", "Période"],
                   "Les 14 jeux de données construits (data/datasets/).")


def t_stationnarite():
    t = pd.read_csv(RES / "py_stationnarite.csv")
    lignes = [(r["série"], f(r["ADF stat"], 2), p_val(r["ADF p"]), f(r["KPSS stat"], 3),
               ("> 0,10" if r["KPSS p"] >= 0.1 else ("< 0,01" if r["KPSS p"] <= 0.01 else f(r["KPSS p"], 3))),
               r["conclusion à 5 %"]) for _, r in t.iterrows()]
    return tableau(lignes, ["Série (apprentissage)", "ADF", "p ADF", "KPSS", "p KPSS", "Conclusion à 5 %"],
                   "Tests de stationnarité (ADF : H0 = racine unitaire ; KPSS : H0 = stationnarité).")


def t_importance():
    a = pd.read_csv(RES / "py_importance_variables_ex_ante.csv", index_col=0).head(8)
    p = pd.read_csv(RES / "py_importance_variables_ex_post.csv", index_col=0).head(8)
    lignes = [(i + 1, f"`{a.index[i]}`", f(a.iloc[i]["permutation (hausse du MSE)"], 3),
               f"`{p.index[i]}`", f(p.iloc[i]["permutation (hausse du MSE)"], 3)) for i in range(8)]
    return tableau(lignes, ["Rang", "Ex ante (lendemain)", "Permutation", "Ex post (jour même)", "Permutation"],
                   "Huit premières variables selon le rang moyen (Spearman, information mutuelle, permutation).")


def t_diagnostics():
    t = pd.read_csv(RES / "py_diagnostics_arima.csv", index_col=0)
    lignes = [(m, f(r["LB(10) p"], 3), f(r["LB(30) p"], 3), f(r["max |ACF| (1-30)"], 3), p_val(r["JB p"]),
               f(r["skewness"], 2), f(r["kurtosis"], 2), f(r["ARCH-LM(7) stat"], 1)) for m, r in t.iterrows()]
    return tableau(lignes, ["Modèle", "p LB(10)", "p LB(30)", "max abs(ACF)", "p JB", "Asymétrie", "Kurtosis", "ARCH-LM(7)"],
                   "Diagnostic des résidus (p de l'ARCH-LM inférieure à 0,001 pour les trois modèles).")


def t_granger():
    t = pd.read_csv(RES / "py_granger.csv")
    noms = {"pv_kwh_kwc": "production", "nebulosite_pct": "nébulosité", "t2m_moy_c": "température"}
    lignes = [(noms[r["cause"]], noms[r["effet"]], f(r["F"], 1), p_val(r["p"])) for _, r in t.iterrows()]
    return tableau(lignes, ["Cause", "Effet", "F", "p"], "Causalité de Granger dans le VAR(3) de Tunis.")


def t_garch():
    t = pd.read_csv(RES / "py_garch_comparaison.csv", index_col=0)
    lignes = [(m, f(r["AIC"], 0), f(r["BIC"], 0), int(r["nb paramètres"]), f(r["LB(10) sur z² p"], 3),
               f(r["ARCH-LM(7) sur z p"], 3), f(r["kurtosis de z"], 1)) for m, r in t.iterrows()]
    return tableau(lignes, ["Modèle", "AIC", "BIC", "Paramètres", "p LB(10) sur z²", "p ARCH-LM(7) sur z", "Kurtosis de z"],
                   "Modèles de volatilité des erreurs à un jour de l'ARIMA-Fourier (z : résidus standardisés).")


def t_cv():
    t = pd.read_csv(RES / "py_validation_croisee_rnn.csv")
    lignes = [(r["cellule"], int(r["fenêtre L"]), int(r["état caché"]), f(r["RMSE pli 1"]), f(r["RMSE pli 2"]),
               f(r["RMSE pli 3"]), f(r["RMSE moyen"])) for _, r in t.iterrows()]
    return tableau(lignes, ["Cellule", "Fenêtre", "État caché", "Pli 1", "Pli 2", "Pli 3", "Moyenne"],
                   "Validation croisée temporelle des réseaux (RMSE en kWh/kWc ; climatologie : 1,129 / 1,087 / 1,130).")


def t_metriques():
    t = pd.read_csv(RES / "py_metriques.csv", index_col=0)
    lignes = []
    for m, r in t.iterrows():
        nom = m.replace(" (ex ante)", "").replace(" (ex post)", "")
        lignes.append((nom, r["information"], f(r["MSE"]), f(r["RMSE"]), f(r["MAE"]), f(r["MAPE (%)"], 1) + " %",
                       f(r["WAPE (%)"], 1) + " %", f(r["RMSE h=1"]), f(r["RMSE h=7"]),
                       "-" if pd.isna(r["couverture IC 95 % (%)"]) else f(r["couverture IC 95 % (%)"], 1) + " %"))
    return tableau(lignes, ["Modèle", "Information", "MSE", "RMSE", "MAE", "MAPE", "WAPE", "RMSE h=1", "RMSE h=7", "Couv. IC 95 %"],
                   "Métriques sur 688 prévisions glissantes à 7 jours (kWh/kWc), tous horizons confondus.")


def t_complexite():
    t = pd.read_csv(RES / "py_metriques.csv", index_col=0)
    lignes = [(m.replace(" (ex ante)", "").replace(" (ex post)", ""), r["famille"], f(r["nb paramètres"], 0),
               f(r["durée d'ajustement (s)"], 1) + " s", r["interprétabilité"]) for m, r in t.iterrows()]
    return tableau(lignes, ["Modèle", "Famille", "Paramètres", "Durée d'ajustement", "Interprétabilité"],
                   "Complexité, coût de calcul et interprétabilité.")


def t_dm():
    t = pd.read_csv(RES / "py_diebold_mariano.csv")
    garde = t[t["référence"].isin(["Climatologie"]) | (t["référence"].str.startswith("LSTM global") & ~t["modèle"].str.contains("ex post"))]
    lignes = [(r["référence"].replace(" (ex ante)", ""), r["modèle"].replace(" (ex ante)", ""), f(r["DM h=1"], 2), p_val(r["p h=1"]),
               f(r["DM h=7"], 2), p_val(r["p h=7"]), p_val(r["p abs h=7"])) for _, r in garde.iterrows()]
    return tableau(lignes, ["Référence", "Modèle", "DM h=1", "p h=1", "DM h=7", "p h=7", "p h=7 (perte absolue)"],
                   "Tests de Diebold-Mariano (perte quadratique sauf dernière colonne ; DM > 0 : le modèle bat la référence).")


def t_r_python():
    t = pd.read_csv(RES / "comparaison_R_python.csv", index_col=0)
    lignes = [(m, f(r["RMSE Python"], 4), f(r["RMSE R"], 4), f(r["écart RMSE (%)"], 3) + " %") for m, r in t.iterrows()]
    return tableau(lignes, ["Modèle", "RMSE Python", "RMSE R", "Écart"], "Même protocole, même échantillon : Python et R.")


def t_rag():
    t = pd.read_csv(RES / "rag_evaluation.csv")
    lignes = [(r["question"], int(r["rang trouvé"]) if not pd.isna(r["rang trouvé"]) else "absent") for _, r in t.iterrows()]
    return tableau(lignes, ["Question de test", "Rang du bon passage"],
                   f"Évaluation de la recherche du RAG : bon passage en tête {t['hit@1'].mean():.0%} des cas, "
                   f"parmi les 4 transmis au LLM {t['hit@4'].mean():.0%}.".replace("%", " %"))


TABLEAUX = {"TABLEAU_JEUX": t_jeux, "TABLEAU_STATIONNARITE": t_stationnarite, "TABLEAU_IMPORTANCE": t_importance,
            "TABLEAU_DIAGNOSTICS": t_diagnostics, "TABLEAU_GRANGER": t_granger, "TABLEAU_GARCH": t_garch,
            "TABLEAU_CV": t_cv, "TABLEAU_METRIQUES": t_metriques, "TABLEAU_COMPLEXITE": t_complexite,
            "TABLEAU_DM": t_dm, "TABLEAU_R_PYTHON": t_r_python, "TABLEAU_RAG": t_rag}


def modele_word(chemin):
    """Dérive du modèle par défaut de pandoc un modèle plus dense (10,5 pt, marges de 2 cm)."""
    defaut = subprocess.run([pandoc, "--print-default-data-file", "reference.docx"], capture_output=True, check=True).stdout
    brut = ICI / "_defaut.docx"
    brut.write_bytes(defaut)
    with zipfile.ZipFile(brut) as src, zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/styles.xml":
                x = data.decode("utf-8")
                x = x.replace('<w:sz w:val="24" />', '<w:sz w:val="21" />', 1).replace('<w:szCs w:val="24" />', '<w:szCs w:val="21" />', 1)
                x = re.sub(r'(<w:style [^>]*w:styleId="Compact"[^>]*>.*?</w:pPr>)',
                           r'\1<w:rPr><w:sz w:val="17" /><w:szCs w:val="17" /></w:rPr>', x, count=1, flags=re.S)
                data = x.encode("utf-8")
            elif item.filename == "word/document.xml":
                data = re.sub(r'w:(top|right|bottom|left)="1440"', r'w:\1="1134"', data.decode("utf-8")).encode("utf-8")
            dst.writestr(item, data)
    brut.unlink()


texte = (ICI / "rapport_corps.md").read_text(encoding="utf-8")
for cle, fonction in TABLEAUX.items():
    texte = texte.replace("{{%s}}" % cle, fonction())
for k in (1, 2, 3):
    prompt = (LLM / f"prompt_{k}.txt").read_text(encoding="utf-8").strip()
    reponse = re.sub(r"<!--.*?-->", "", (LLM / f"reponse_{k}.md").read_text(encoding="utf-8"), flags=re.S).strip()
    reponse = "\n".join("> " + l if l.strip() else ">" for l in reponse.splitlines())   # citée telle quelle
    texte = texte.replace("{{PROMPT_%d}}" % k, prompt).replace("{{REPONSE_%d}}" % k, reponse)
experte = (LLM / "interpretation_experte.md").read_text(encoding="utf-8").split("\n", 1)[1]
texte = texte.replace("{{INTERPRETATION_EXPERTE}}", re.sub(r"^## ", "### ", experte.strip(), flags=re.M))
reste = re.findall(r"\{\{[A-Z_0-9]+\}\}", texte)
if reste:
    sys.exit(f"Champs non remplis : {reste}")
(ICI / "rapport.md").write_text(texte, encoding="utf-8")

modele_word(ICI / "_modele.docx")
commun = ["rapport.md", "--from", "markdown", "--toc", "--toc-depth=2", "--metadata", "toc-title=Sommaire",
          "--resource-path", ".", "--number-sections=false"]
subprocess.run([pandoc, *commun, "-o", f"{NOM}.docx", "--reference-doc", "_modele.docx"], cwd=ICI, check=True)
print("Rapport Word :", ICI / f"{NOM}.docx")
(ICI / "_modele.docx").unlink()

# PDF : HTML autonome (figures incluses) imprimé par Chromium. Plus robuste qu'une chaîne LaTeX pour les
# caractères Unicode et ne demande aucun paquet supplémentaire.
subprocess.run([pandoc, *commun, "-o", "_rapport.html", "--standalone", "--embed-resources", "--css", "impression.css"],
               cwd=ICI, check=True)
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.goto((ICI / "_rapport.html").as_uri(), wait_until="load")
        page.pdf(path=str(ICI / f"{NOM}.pdf"), format="A4", print_background=True, display_header_footer=True,
                 header_template="<div></div>",
                 footer_template="<div style='font-size:8px;color:#666;width:100%;text-align:center'>"
                                 "<span class='pageNumber'></span> / <span class='totalPages'></span></div>",
                 margin={"top": "18mm", "bottom": "20mm", "left": "17mm", "right": "17mm"})
        navigateur.close()
    print("Rapport PDF :", ICI / f"{NOM}.pdf")
except ImportError:
    print("Playwright absent : PDF non produit (ouvrir le .docx et l'exporter en PDF).")
(ICI / "_rapport.html").unlink()
(ICI / "rapport.md").unlink()
