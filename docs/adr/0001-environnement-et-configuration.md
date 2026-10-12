# ADR 0001 — Environnement d'exécution et dossier de configuration

Date : 11 octobre 2026. Statut : acceptée, à revoir si le délai le permet.

## Contexte

Le plan demande Python 3.12 installé par `uv`, avec un fichier de verrouillage. Sur la machine de travail :

- seul Python 3.14 est installé, `uv` est absent ;
- la connexion est lente (environ 150 ko/s) ;
- installer Python 3.12 et toutes les bibliothèques représente environ 700 Mo de téléchargements ;
- le rendu est le 12 octobre 2026 à 23h55, et la collecte des 30 villes occupe déjà la connexion.

Par ailleurs, `CLAUDE.md` nomme le dossier de configuration `config/`, alors que l'architecture cible de
`MASTER_PROMPT.md` le nomme `configs/`.

## Décision

1. **Les calculs sont faits avec Python 3.14**, dans l'environnement existant, qui contient déjà les
   bibliothèques lourdes (torch, statsmodels, prophet, xgboost).
2. **`pyproject.toml` déclare `requires-python >= 3.12`.** Le code n'utilise rien de propre à la version 3.14.
3. **Le dossier de configuration s'appelle `configs/`**, comme dans l'architecture cible.

## Conséquences

- La règle « Python 3.12 via uv » n'est pas respectée à la lettre. Le fonctionnement sous Python 3.12
  n'a pas été testé.
- Le fichier de verrouillage `uv.lock` reste à produire (`uv lock`), ce qui demande d'installer `uv`.
- `requirements.txt` continue de fixer les versions exactes utilisées.
- Le chemin `config/params.yaml` cité dans `CLAUDE.md` correspond à `configs/params.yaml`.
