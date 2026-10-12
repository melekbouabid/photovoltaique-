"""Construit le corpus du RAG (rag/corpus.jsonl) à partir des données et des résultats du projet.

Sources, toutes locales :
- rag/docs/*.md : méthode PVGIS, glossaire des séries temporelles, lien avec le rapport SolarVision ;
- data/LISEZMOI_donnees.md : fiches des 14 jeux de données ;
- fiches statistiques par ville, rédigées ici à partir de data/datasets/ (chiffres calculés, non saisis) ;
- résultats de l'étude (resultats/*.csv), mis en phrases ;
- rapport/rapport_corps.md (interprétations), s'il existe ;
- résumés des articles cités par le rapport SolarVision (sources/liens_rapport_solarvision.json).

Usage : python rag/construire_corpus.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
JEUX, RES = RACINE / "data" / "datasets", RACINE / "resultats"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
TAILLE = 120          # mots par passage : assez pour une idée complète, assez court pour une recherche précise


def f(v, d=2):
    """Nombre au format français."""
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def decouper(titre: str, texte: str, source: str) -> list[dict]:
    """Découpe un texte en passages d'environ TAILLE mots, en respectant les fins de phrase."""
    phrases = re.split(r"(?<=[.!?])\s+|\n(?=[-#|])", texte.strip())
    out, courant = [], []
    for ph in phrases:
        courant.append(ph.strip())
        if sum(len(p.split()) for p in courant) >= TAILLE:
            out.append(" ".join(courant))
            courant = []
    if courant:
        out.append(" ".join(courant))
    return [{"titre": titre, "texte": re.sub(r"\s+", " ", t), "source": source} for t in out if len(t.split()) > 5]


def sections_markdown(chemin: Path, prefixe: str) -> list[dict]:
    """Un document Markdown découpé par titres, puis en passages."""
    texte = chemin.read_text(encoding="utf-8")
    texte = re.sub(r"\{\{[A-Z_0-9]+\}\}", "", texte)                # champs du rapport remplis à la construction
    texte = re.sub(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?", "", texte)   # images
    texte = re.sub(r"^---\n.*?\n---\n", "", texte, flags=re.S)      # en-tête YAML
    morceaux = re.split(r"\n(?=#{1,3} )", texte)
    out = []
    for m in morceaux:
        lignes = m.strip().splitlines()
        if not lignes:
            continue
        titre = lignes[0].lstrip("#").strip()
        corps = "\n".join(lignes[1:]).replace("**", "").replace("`", "")
        out += decouper(f"{prefixe} - {titre}", corps, str(chemin.relative_to(RACINE)).replace("\\", "/"))
    return out


def fiches_jeux() -> list[dict]:
    """Un passage par jeu de données (sans répéter le dictionnaire), puis le dictionnaire des variables une
    seule fois : sinon les longues listes de variables, identiques d'un jeu à l'autre, envahissent la recherche."""
    f_cat = RACINE / "data" / "catalogue_datasets.json"
    if not f_cat.exists():
        return []
    cat = json.loads(f_cat.read_text(encoding="utf-8"))
    out = []
    vus = {}
    for c in cat:
        nom = c["fichier"].split("/")[-1]
        per = f", du {c['periode'][0]} au {c['periode'][1]}" if c.get("periode") else ""
        texte = (f"Jeu de données {nom} ({c['theme']}, {c['pays']}) : {c['description']}. {c['lignes']:,} lignes, "
                 f"{c['colonnes']} colonnes{per}, {c['valeurs_manquantes_pct']} % de valeurs manquantes. "
                 f"Sources : {' ; '.join(s.split(' - ')[0] for s in c['sources'])}. Variables : "
                 + ", ".join(v["nom"] for v in c["variables"]) + ".").replace(",", ",")
        out += decouper(f"Jeu de données {nom}", texte, c["fichier"])
        for v in c["variables"]:
            vus.setdefault(v["nom"], v)
    lignes = [f"{v['nom']} ({v['unite']}) : {v['description']} [source : {v['source']}]." for v in vus.values()]
    for i in range(0, len(lignes), 8):
        bloc = lignes[i:i + 8]
        out.append({"titre": "Dictionnaire des variables : " + ", ".join(l.split(" (")[0] for l in bloc),
                    "texte": " ".join(bloc), "source": "data/catalogue_datasets.json"})
    lis = RACINE / "data" / "LISEZMOI_donnees.md"
    if lis.exists():                     # parties générales des fiches : origine, sites, précautions
        for p in sections_markdown(lis, "Jeux de données"):
            if not any(k in p["titre"] for k in (".csv", "Liste des jeux")):
                out.append(p)
    return out


def fiches_villes() -> list[dict]:
    panel = pd.read_csv(JEUX / "panel_9_villes_journalier.csv", parse_dates=["date"])
    synth = pd.read_csv(RACINE / "data" / "reference" / "pvgis_synthese_9_villes.csv", index_col="site")
    out, classement = [], []
    for site, d in panel.groupby("site", sort=False):
        d = d.set_index("date")
        ville, pays = d["ville"].iloc[0], d["pays"].iloc[0]
        an = d.groupby(d.index.year)["pv_kwh_kwc"].sum()
        mois = d.groupby(d.index.month)["pv_kwh_kwc"].mean()
        ghi_m = d.groupby(d.index.month)["ghi_kwh_m2"].mean()
        lux_m = d.groupby(d.index.month)["heures_lumiere_10klux"].mean()
        ghi_an = d.groupby(d.index.year)["ghi_kwh_m2"].sum().mean()
        s = synth.loc[site]
        jmax, jmin = d["pv_kwh_kwc"].idxmax(), d["pv_kwh_kwc"].idxmin()
        classement.append((ville, pays, an.mean(), ghi_an))
        texte = (
            f"{ville} ({pays}), latitude {d['latitude'].iloc[0]}°, longitude {d['longitude'].iloc[0]}°. "
            f"Production photovoltaïque simulée par PVGIS pour 1 kWc orienté plein sud et incliné à "
            f"{s['pente_optimale_deg']:.0f}° (pente optimale) : {f(an.mean(), 0)} kWh/kWc par an en moyenne "
            f"sur 2005-2023, avec un écart-type d'une année à l'autre de {f(an.std(), 0)} kWh/kWc. "
            f"Meilleure année : {an.idxmax()} ({f(an.max(), 0)} kWh/kWc) ; plus faible : {an.idxmin()} "
            f"({f(an.min(), 0)} kWh/kWc). Productible annuel selon l'outil PVcalc de PVGIS : "
            f"{f(s['productible_kwh_kwc_an'], 0)} kWh/kWc, pour une irradiation de {f(s['irradiation_plan_kwh_m2_an'], 0)} "
            f"kWh/m²/an sur le plan des modules. Irradiation globale horizontale moyenne : {f(ghi_an, 0)} kWh/m²/an.")
        out += decouper(f"Fiche {ville} : production annuelle", texte, "data/datasets/panel_9_villes_journalier.csv")
        texte = (f"Production photovoltaïque moyenne par mois à {ville} ({pays}), en kWh/kWc par jour : "
                 + " ; ".join(f"{MOIS[m - 1]} {f(v)}" for m, v in mois.items())
                 + f". Mois le plus productif : {MOIS[int(mois.idxmax()) - 1]} ; le moins productif : "
                 f"{MOIS[int(mois.idxmin()) - 1]}. Rapport entre les deux : {f(mois.max() / mois.min(), 1)}. "
                 f"Record journalier : {f(d['pv_kwh_kwc'].max())} kWh/kWc le {jmax:%d/%m/%Y} ; journée la plus "
                 f"faible : {f(d['pv_kwh_kwc'].min())} kWh/kWc le {jmin:%d/%m/%Y}.")
        out += decouper(f"Fiche {ville} : production par mois", texte, "data/datasets/panel_9_villes_journalier.csv")
        texte = (f"Éclairement à {ville} ({pays}). Irradiation globale horizontale moyenne par mois, en kWh/m² "
                 f"par jour : " + " ; ".join(f"{MOIS[m - 1]} {f(v)}" for m, v in ghi_m.items())
                 + f". Heures par jour où l'éclairement lumineux extérieur dépasse 10 000 lux (éclairage naturel "
                 f"suffisant) : {f(lux_m.min(), 1)} h en {MOIS[int(lux_m.idxmin()) - 1]} et {f(lux_m.max(), 1)} h en "
                 f"{MOIS[int(lux_m.idxmax()) - 1]}. Éclairement lumineux maximal moyen en juin : "
                 f"{f(d.loc[d.index.month == 6, 'eclairement_max_klux'].mean(), 0)} klux. Nébulosité moyenne : "
                 f"{f(d['nebulosite_pct'].mean(), 0)} % ; température moyenne : {f(d['t2m_moy_c'].mean(), 1)} °C ; "
                 f"épaisseur optique moyenne des aérosols : {f(d['aerosols_aod'].mean(), 2)}.")
        out += decouper(f"Fiche {ville} : éclairement et éclairage naturel", texte,
                        "data/datasets/panel_9_villes_journalier.csv")
    classement.sort(key=lambda x: -x[2])
    texte = ("Classement des 9 villes par production photovoltaïque annuelle d'1 kWc (moyenne 2005-2023, PVGIS) : "
             + " ; ".join(f"{i}. {v} ({p}) {f(e, 0)} kWh/kWc" for i, (v, p, e, _) in enumerate(classement, start=1))
             + ". Classement par irradiation globale horizontale annuelle : "
             + " ; ".join(f"{v} {f(g, 0)} kWh/m²" for v, _, _, g in sorted(classement, key=lambda x: -x[3])) + ".")
    out += decouper("Classement et comparaison des 9 villes (France, Tunisie, Espagne)", texte, "data/reference/pvgis_synthese_9_villes.csv")
    pays = panel.groupby("pays")["pv_kwh_kwc"].mean() * 365.25
    texte = ("Production annuelle moyenne d'1 kWc par pays (moyenne des 3 villes) : "
             + " ; ".join(f"{p} {f(v, 0)} kWh/kWc" for p, v in pays.sort_values(ascending=False).items())
             + ". En juillet, la production moyenne journalière vaut "
             + " ; ".join(f"{p} {f(v)} kWh/kWc" for p, v in panel[panel['date'].dt.month == 7].groupby('pays')['pv_kwh_kwc'].mean().items())
             + " ; en décembre, " + " ; ".join(f"{p} {f(v)} kWh/kWc" for p, v in
                                               panel[panel['date'].dt.month == 12].groupby('pays')['pv_kwh_kwc'].mean().items()) + ".")
    out += decouper("Comparaison par pays : France, Tunisie, Espagne", texte, "data/datasets/panel_9_villes_journalier.csv")
    return out


def fiches_resultats() -> list[dict]:
    out = []
    f_m = RES / "py_metriques.csv"
    if f_m.exists():
        t = pd.read_csv(f_m, index_col=0)
        ante = t[t["information"] == "ex ante"].sort_values("RMSE")
        post = t[t["information"] == "ex post"].sort_values("RMSE")
        texte = ("Comparaison des modèles de prévision de la production photovoltaïque journalière à Tunis, à 7 jours "
                 "(prévisions glissantes sur la période de test 2022-2023, erreurs en kWh/kWc par jour). "
                 "Modèles ex ante (sans météo future), du meilleur au moins bon : "
                 + " ; ".join(f"{m} RMSE {f(r['RMSE'], 3)}, MAE {f(r['MAE'], 3)}, MAPE {f(r['MAPE (%)'], 1)} %"
                              for m, r in ante.iterrows()) + ".")
        out += decouper("Résultats : comparaison des modèles ex ante", texte, "resultats/py_metriques.csv")
        texte = ("Modèles ex post (météo observée des 7 jours fournie, borne optimiste) : "
                 + " ; ".join(f"{m} RMSE {f(r['RMSE'], 3)}, MAE {f(r['MAE'], 3)}, MAPE {f(r['MAPE (%)'], 1)} %"
                              for m, r in post.iterrows())
                 + f". Meilleur modèle ex ante : {ante.index[0]} ; meilleur modèle ex post : {post.index[0]}. "
                 f"Erreur à 1 jour du meilleur ex ante : RMSE {f(ante['RMSE h=1'].iloc[0], 3)} ; à 7 jours : "
                 f"{f(ante['RMSE h=7'].iloc[0], 3)} kWh/kWc.")
        out += decouper("Résultats : modèles ex post et meilleur modèle", texte, "resultats/py_metriques.csv")
    for nom, fichier, titre in (
            ("stationnarité", "py_stationnarite.csv", "Résultats : tests de stationnarité ADF et KPSS (Tunis)"),
            ("Granger", "py_granger.csv", "Résultats : causalité de Granger (VAR de Tunis)"),
            ("Granger multi-sites", "py_granger_multi_sites.csv", "Résultats : Granger entre Tunis et les autres villes"),
            ("GARCH", "py_garch_comparaison.csv", "Résultats : modèles de volatilité ARCH/GARCH"),
            ("validation croisée", "py_validation_croisee_rnn.csv", "Résultats : validation croisée des LSTM et GRU"),
            ("LSTM global", "py_lstm_global_par_ville.csv", "Résultats : LSTM global entraîné sur les 9 villes"),
            ("importance ex ante", "py_importance_variables_ex_ante.csv", "Résultats : variables les plus utiles (ex ante)"),
            ("importance ex post", "py_importance_variables_ex_post.csv", "Résultats : variables les plus utiles (ex post)"),
            ("Johansen national", "py_johansen_national.csv", "Résultats : cointégration France-Espagne (production nationale)"),
            ("validation externe", "py_validation_externe.csv", "Résultats : PVGIS comparé aux productions mesurées RTE et REE"),
            ("SARIMA mensuel", "py_metriques_mensuel.csv", "Résultats : SARIMA mensuel (horizon 6 mois)"),
            ("Diebold-Mariano", "py_diebold_mariano.csv", "Résultats : tests de Diebold-Mariano")):
        fc = RES / fichier
        if not fc.exists():
            continue
        t = pd.read_csv(fc)
        if len(t) > 14:
            t = t.head(14)
        lignes = []
        for _, r in t.iterrows():
            lignes.append(", ".join(f"{c} = {f(v, 3) if isinstance(v, (float, np.floating)) else v}"
                                    for c, v in r.items() if not (isinstance(v, float) and np.isnan(v))))
        out += decouper(titre, f"Tableau {nom} : " + " | ".join(lignes) + ".", f"resultats/{fichier}")
    f_app = RACINE / "app" / "backend" / "modeles" / "validation_app.json"
    if f_app.exists():
        v = json.loads(f_app.read_text(encoding="utf-8"))
        for var, par_site in v.get("rmse_test", {}).items():
            texte = (f"Modèles servis par l'application pour la variable {var} : erreur RMSE sur la période de test "
                     "(2022-2023), par ville et par modèle, en unités de la variable : "
                     + " ; ".join(f"{s} : " + ", ".join(f"{m} {f(x, 3)}" for m, x in d.items()) for s, d in par_site.items()) + ".")
            out += decouper(f"Application : précision des modèles ({var})", texte, "app/backend/modeles/validation_app.json")
    return out


def resumes_articles() -> list[dict]:
    f_l = RACINE / "sources" / "liens_rapport_solarvision.json"
    if not f_l.exists():
        return []
    out = []
    for l in json.loads(f_l.read_text(encoding="utf-8")):
        if l.get("resume") and l["categorie"] == "article":
            entete = f"Article cité par le rapport SolarVision : {l.get('titre', '')}"
            if l.get("auteurs"):
                entete += f" ({l['auteurs'][:120]}, {l.get('date', '')[:4]})"
            out += decouper(entete[:200], l["resume"], l["url"])
    return out


def construire() -> int:
    passages = []
    for doc in sorted((ICI / "docs").glob("*.md")):
        passages += sections_markdown(doc, doc.stem.replace("_", " ").capitalize())
    passages += fiches_jeux()
    passages += fiches_villes()
    passages += fiches_resultats()
    if (RACINE / "rapport" / "rapport_corps.md").exists():
        passages += sections_markdown(RACINE / "rapport" / "rapport_corps.md", "Rapport")
    passages += resumes_articles()
    with (ICI / "corpus.jsonl").open("w", encoding="utf-8") as fo:
        for i, p in enumerate(passages):
            fo.write(json.dumps({"id": i, **p}, ensure_ascii=False) + "\n")
    print(f"{len(passages)} passages écrits dans {ICI / 'corpus.jsonl'}")
    return len(passages)


if __name__ == "__main__":
    construire()
