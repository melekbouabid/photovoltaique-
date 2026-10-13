"""RAG simple : recherche lexicale BM25 dans un corpus local + réponse rédigée par un LLM (API Groq).

1. Le corpus (rag/corpus.jsonl) est découpé en passages d'environ 120 mots par construire_corpus.py.
2. Recherche : BM25 (rank_bm25) après normalisation du texte (minuscules, accents et mots vides
   retirés, synonymes du domaine : « PV » = photovoltaïque, « éclairement » = irradiance = GHI...).
   BM25 suffit ici : le corpus est petit, technique et en français, et les questions reprennent son
   vocabulaire (noms de villes, de modèles, de tests).
3. Génération : le LLM (hébergé par Groq, API compatible OpenAI) reçoit la question et les meilleurs
   passages numérotés, avec la consigne de ne répondre qu'à partir d'eux et de citer [n]. Sans clé
   GROQ_API_KEY ou sans réseau, la réponse est extractive (phrases des passages les plus proches de
   la question), ce qui garde l'outil utilisable hors ligne.

La clé se lit dans la variable d'environnement GROQ_API_KEY ou dans le fichier .env à la racine du
projet (modèle : .env.example). Seuls la question et les passages retrouvés sont envoyés à Groq.

Usage en ligne de commande : python rag/moteur.py "Quelle ville produit le plus en juillet ?"
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from rank_bm25 import BM25Okapi

ICI = Path(__file__).resolve().parent
CORPUS = ICI / "corpus.jsonl"


def _charger_env(fichier: Path = ICI.parent / ".env") -> None:
    """Lit les lignes CLE=valeur de .env sans écraser l'environnement : la clé ne figure jamais dans le code."""
    if fichier.exists():
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            cle, sep, valeur = ligne.strip().partition("=")
            if sep and cle and not cle.startswith("#"):
                os.environ.setdefault(cle.strip(), valeur.strip().strip("\"'"))


_charger_env()
# Adresse et modèle du LLM, modifiables par l'environnement (docker-compose transmet le fichier .env).
GROQ = (os.environ.get("GROQ_URL") or "https://api.groq.com/openai/v1").rstrip("/") + "/chat/completions"
MODELE_LLM = os.environ.get("GROQ_MODELE") or "openai/gpt-oss-120b"
ATTENTE_MAX_S = 20         # quota par minute atteint (HTTP 429) : une seule nouvelle tentative, après ce délai au plus

MOTS_VIDES = set("""a au aux avec ce ces cette dans de des du elle en est et etre il ils je la le les leur lui
ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses son sur ta te tes toi
ton tu un une vos votre vous y d l s c n j m t qu quel quelle quels quelles est-ce comment combien
pourquoi quoi sont ete fait faire plus moins tres peut peuvent cela ca entre selon apres avant aussi""".split())
# Synonymes du domaine : chaque terme de la question est complété par ses équivalents du corpus.
SYNONYMES = {
    "pv": ["photovoltaique", "production"], "photovoltaique": ["pv", "production"],
    "production": ["productible", "pv"], "productible": ["production"],
    "eclairement": ["irradiation", "irradiance", "ghi", "rayonnement"], "irradiance": ["eclairement", "ghi"],
    "irradiation": ["eclairement", "ghi", "rayonnement"], "ghi": ["irradiation", "eclairement"],
    "rayonnement": ["irradiation", "eclairement"], "soleil": ["solaire", "ensoleillement"],
    "eclairage": ["lux", "lumiere", "eclairement"], "lumiere": ["lux", "eclairage"],
    "nuages": ["nebulosite"], "nuageux": ["nebulosite"], "nebulosite": ["nuages"],
    "pluie": ["precipitation"], "precipitations": ["precipitation", "pluie"],
    "erreur": ["rmse", "mae", "mape"], "precision": ["rmse", "mae", "erreur"],
    "meilleur": ["meilleur", "rmse"], "lstm": ["lstm", "reseau"], "gru": ["gru", "reseau"],
    "tunisie": ["tunis", "sfax", "tozeur", "pays"], "espagne": ["madrid", "seville", "barcelone", "pays"],
    "france": ["paris", "lyon", "marseille", "pays"], "seville": ["seville"], "volatilite": ["garch", "variance"],
    "impute": ["imputation", "remplace", "trou", "corrige", "jour_impute_pvgis"], "imputation": ["impute", "remplace", "trou"],
    "manquant": ["trou", "impute", "interpole"], "trou": ["impute", "manquant", "satellitaire"],
    "kwc": ["kwc", "kwh"], "jeux": ["dataset", "donnees"], "datasets": ["jeux", "donnees"],
    "hiver": ["decembre", "janvier", "fevrier"], "ete": ["juin", "juillet", "aout"],
    "printemps": ["mars", "avril", "mai"], "automne": ["septembre", "octobre", "novembre"],
    "calcule": ["modele", "methode"], "calculer": ["modele", "methode"], "produit": ["production"],
    "produire": ["production"], "ensoleillee": ["irradiation", "classement"], "lumineuse": ["lux", "eclairement"],
}


def _sans_accents(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _racine(m: str) -> str:
    """Racinisation très légère : pluriels en -s/-x (villes -> ville, heures -> heure)."""
    return m[:-1] if len(m) > 4 and m[-1] in "sx" and not m[-2].isdigit() else m


def normaliser(texte: str) -> list[str]:
    t = _sans_accents(texte)
    return [_racine(m) for m in re.findall(r"[a-z0-9_]+(?:[.,][0-9]+)?", t) if m not in MOTS_VIDES and len(m) > 1]


# Les jetons de la question sont racinisés : les clés doivent l'être aussi (« nuages » -> « nuage »).
_SYNONYMES_RACINES = {_racine(k): v for k, v in SYNONYMES.items()}


def etendre(jetons: list[str], question: str = "") -> list[str]:
    """Termes ajoutés à la question : synonymes du domaine et, pour une question de classement, les mots
    « classement » et « record ». Ils sont pondérés moins que les mots de la question (voir rechercher)."""
    out = []
    for j in jetons:
        out += [_racine(x) for x in _SYNONYMES_RACINES.get(j, [])]
    q = _sans_accents(question)
    # « la ville qui produit le plus », « record », « meilleure » : chercher les classements.
    if re.search(r"\b(le|la|les) plus\b|meilleur|maximum|record|classement|moins", q):
        out += ["classement", "record"]
    return out


POIDS_EXTENSION = 0.4      # un synonyme compte moins qu'un mot de la question


class MoteurRAG:
    """Index BM25 du corpus, recherche des passages et rédaction de la réponse."""

    def __init__(self, corpus: Path = CORPUS):
        if not corpus.exists():
            raise FileNotFoundError(f"{corpus} introuvable : lancer d'abord python rag/construire_corpus.py")
        self.passages = [json.loads(l) for l in corpus.read_text(encoding="utf-8").splitlines() if l.strip()]
        # Le titre est compté deux fois : il résume le passage (ville, thème, méthode).
        self.index = BM25Okapi([normaliser(f"{p['titre']} {p['titre']} {p['texte']}") for p in self.passages])

    def rechercher(self, question: str, k: int = 4) -> list[dict]:
        jetons = normaliser(question)
        scores = self.index.get_scores(jetons) + POIDS_EXTENSION * self.index.get_scores(etendre(jetons, question))
        ordre = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [{**self.passages[i], "score": round(float(scores[i]), 3)} for i in ordre if scores[i] > 0]

    @staticmethod
    def _messages(question: str, passages: list[dict], contexte: str | None) -> list[dict]:
        blocs = []
        if contexte:
            blocs.append(f"[0] (prévision calculée par l'application) {contexte}")
        blocs += [f"[{i}] ({p['titre']}) {p['texte']}" for i, p in enumerate(passages, start=1)]
        consigne = ("Tu es l'assistant du projet SolarVision - Séries temporelles (production photovoltaïque et "
                    "éclairement solaire en France, Tunisie et Espagne). Réponds à la question en t'appuyant "
                    "UNIQUEMENT sur les extraits numérotés fournis. Cite tes sources entre crochets droits, sous la "
                    "forme [1], [2]. "
                    "Recopie les chiffres tels qu'ils figurent dans les extraits, sans les recalculer. Si les "
                    "extraits ne permettent pas de répondre, dis-le clairement. Réponds en français, en texte "
                    "simple (ni tableau ni titre), en 120 mots au maximum.")
        return [{"role": "system", "content": consigne},
                {"role": "user", "content": "Extraits :\n" + "\n".join(blocs) + f"\n\nQuestion : {question}"}]

    @staticmethod
    def _groq(messages: list[dict], modele: str, timeout: int) -> str | None:
        """Appel de l'API Groq ; None si la clé manque, si le réseau échoue ou si la réponse est vide."""
        cle = os.environ.get("GROQ_API_KEY", "").strip()
        if not cle:
            return None
        corps = {"model": modele, "messages": messages, "temperature": 0, "seed": 42, "max_completion_tokens": 900}
        if "gpt-oss" in modele:
            # Modèle à raisonnement : effort minimal (la réponse est dans les extraits) et raisonnement non renvoyé.
            corps |= {"reasoning_effort": "low", "include_reasoning": False}
        try:
            for essai in range(2):
                r = requests.post(GROQ, timeout=timeout, json=corps, headers={"Authorization": f"Bearer {cle}"})
                if r.status_code == 429 and essai == 0:
                    try:
                        attente = float(r.headers.get("retry-after", 5))
                    except ValueError:
                        attente = 5.0
                    if attente > ATTENTE_MAX_S:
                        return None
                    time.sleep(attente + 0.5)
                    continue
                r.raise_for_status()
                texte = (r.json()["choices"][0]["message"].get("content") or "").strip()
                # Certains modèles citent sous la forme 【1】 : ramenée à [1], seule forme reconnue par l'interface.
                return re.sub(r"【\s*(\d+)[^】]*】", r"[\1]", texte) or None
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return None
        return None

    @staticmethod
    def _extractif(question: str, passages: list[dict], contexte: str | None) -> str:
        """Repli sans LLM : les phrases qui partagent le plus de mots avec la question."""
        q = set(normaliser(question)) | set(etendre(normaliser(question), question))
        phrases = []
        sources = ([(0, contexte)] if contexte else []) + [(i, p["texte"]) for i, p in enumerate(passages, start=1)]
        for i, texte in sources:
            for ph in re.split(r"(?<=[.!?])\s+", texte):
                recouvrement = len(q & set(normaliser(ph)))
                # Les lignes de tableau (« | ») ne sont pas des phrases : illisibles hors de leur tableau.
                if recouvrement and " | " not in ph and len(ph) <= 400:
                    phrases.append((recouvrement, i, ph.strip()))
        phrases.sort(key=lambda x: (-x[0], x[1]))
        if not phrases:
            return "Je ne trouve pas de passage du corpus qui réponde à cette question."
        return " ".join(f"{ph} [{i}]" for _, i, ph in phrases[:3])

    def repondre(self, question: str, k: int = 4, contexte: str | None = None, llm: bool = True,
                 modele: str = MODELE_LLM, timeout: int = 60) -> dict:
        passages = self.rechercher(question, k)
        mode, texte = "extractif", None
        if llm:
            texte = self._groq(self._messages(question, passages, contexte), modele, timeout)
            if texte is not None:
                mode = f"llm ({modele}, Groq)"
        if texte is None:
            texte = self._extractif(question, passages, contexte)
        return {"question": question, "reponse": texte, "mode": mode,
                "sources": [{"rang": i, "titre": p["titre"], "source": p["source"], "score": p["score"],
                             "extrait": p["texte"][:400]} for i, p in enumerate(passages, start=1)]}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Quelle ville produit le plus d'électricité solaire par kWc ?"
    rep = MoteurRAG().repondre(q)
    print(f"Question : {q}\nMode : {rep['mode']}\n\n{rep['reponse']}\n\nSources :")
    for s in rep["sources"]:
        print(f"  [{s['rang']}] {s['titre']} ({s['source']}, score {s['score']})")
