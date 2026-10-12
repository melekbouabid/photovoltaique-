"""Section 5 : envoie les prompts construits par le notebook à un LLM local et archive les réponses.

Le LLM utilisé est un modèle généraliste servi par Ollama (https://ollama.com), exécuté en local.
Les prompts (prompt_1.txt à prompt_3.txt) sont écrits par le notebook Python à partir de ses propres
résultats. Chaque réponse est enregistrée intégralement, avec le nom du modèle et les réglages, dans
reponse_k.md. Notre propre interprétation (interpretation_experte.md) est rédigée AVANT cet appel.

Usage : python llm/interroger_llm.py [nom_du_modele]
"""
import datetime
import pathlib
import sys

import requests

MODELE = sys.argv[1] if len(sys.argv) > 1 else "qwen3-vl:8b-instruct"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192}   # température 0 : réponse reproductible
ICI = pathlib.Path(__file__).resolve().parent

if not (ICI / "interpretation_experte.md").exists():
    sys.exit("Rédiger d'abord llm/interpretation_experte.md : l'interprétation humaine doit précéder celle du LLM.")

for k in (1, 2, 3):
    prompt = (ICI / f"prompt_{k}.txt").read_text(encoding="utf-8")
    r = requests.post("http://localhost:11434/api/generate", timeout=1800,
                      json={"model": MODELE, "prompt": prompt, "stream": False, "options": OPTIONS})
    r.raise_for_status()
    reponse = r.json()["response"].strip()
    entete = (f"<!-- modèle : {MODELE} (Ollama, local) | options : {OPTIONS} | "
              f"date : {datetime.date.today().isoformat()} -->\n\n")
    (ICI / f"reponse_{k}.md").write_text(entete + reponse + "\n", encoding="utf-8")
    print(f"prompt {k} : {len(prompt)} caractères envoyés, {len(reponse)} reçus")
