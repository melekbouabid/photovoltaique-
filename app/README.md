# Application web : prévision photovoltaïque et assistant RAG

Complément de démonstration du mini-projet (non demandé par l'énoncé). Backend FastAPI, frontend React.

## Page d'accueil

1. **Prévoir** : un formulaire dont tous les champs sont pré-remplis et modifiables.
   - pays et ville (9 villes), grandeur (production photovoltaïque ou éclairement), modèle ;
   - dernier jour connu et horizon (1 à 10 jours) ;
   - puissance installée (kWc) et consommation journalière (facultative) ;
   - **les 14 derniers jours observés** : valeurs PVGIS en grisé ; on peut les remplacer par les relevés de sa
     propre installation, y compris au-delà de la fin des données (31/12/2023), où les valeurs proposées sont des
     normales saisonnières.

   La réponse donne un texte rédigé, la production totale et sa fourchette, l'écart à la normale, l'erreur moyenne
   du modèle sur la période de test, un graphique (historique, prévision, intervalle à 95 %, normale) et le
   tableau détaillé.
2. **Assistant (RAG)** : questions libres sur les données, la méthode et les résultats ; réponse rédigée par un
   LLM (API Groq) à partir des passages retrouvés, avec les sources. Une question de prévision (« combien produira
   3 kWc à Séville les 5 prochains jours ? ») déclenche le LSTM.
3. **Lumière** : journée moyenne d'un mois (puissance, éclairement énergétique et lumineux, heure par heure).
4. **Toiture** : production annuelle selon l'inclinaison et l'orientation des modules (scénarios PVGIS), calculateur.
5. **Pays**, **Modèles**, **Données** : comparaison des 9 villes, résultats de l'étude et précision des modèles
   servis, catalogue des 14 jeux de données (conformité, variables, téléchargement) et liens du rapport SolarVision.

## Modèles servis

Entraînés par `python/entrainer_modeles_app.py` sur les 9 villes, même découpage que le notebook :

| Modèle | Principe | Intervalle |
|---|---|---|
| LSTM global | 28 jours passés (écart à la normale) et position dans l'année, prévision directe à 10 jours | quantiles des erreurs de validation |
| ARIMA-Fourier | ordre et harmoniques retenus par l'étude, paramètres figés par ville | intervalle du filtre de Kalman |
| Climatologie | normale saisonnière du jour (2005-2020) | ± 1,96 écart-type saisonnier |
| Persistance | dernière valeur répétée | aucun |

Le LSTM est volontairement univarié : l'utilisateur peut saisir ses relevés de production, pas la météo.

## Lancer

Prérequis : `data/datasets/` (collecte), `app/backend/modeles/` (entraînement) et `rag/corpus.jsonl`
(`python rag/construire_corpus.py`). Pour les réponses rédigées : une clé `GROQ_API_KEY` dans le fichier `.env` à la
racine du projet (modèle : `.env.example` ; sans elle, l'assistant répond par extraits).

Avec Docker, depuis la racine du projet : `docker compose up --build`, puis http://localhost:8000.

Sans Docker :

```
cd app/frontend && npm install && npm run build      (une fois : le backend sert ensuite le site)
cd app/backend && uvicorn main:app --port 8000
```

Ouvrir http://localhost:8000. En développement : `npm run dev` dans `app/frontend` (port 5173, appels /api relayés).

## API

| Route | Rôle |
|---|---|
| `GET /api/health` | État du service, modèle du LLM et présence de la clé |
| `GET /api/info` | Sites, période, bornes de la date d'origine, modèles |
| `GET /api/catalogue` | Jeux de données et liens du rapport SolarVision |
| `GET /api/series?site=&variable=&debut=&fin=&pas=` | Série d'une ville |
| `GET /api/profils?variable=` | Profils mensuels des 9 villes |
| `GET /api/valeurs_recentes?site=&variable=&origine=&n=` | Valeurs de départ du formulaire |
| `POST /api/prevision` | Prévision (corps : site, variable, modele, origine, horizon, puissance_kwc, conso_kwh_jour, valeurs_recentes) |
| `GET /api/modeles` | Métriques de l'étude et validation des modèles servis |
| `GET /api/profil_horaire?site=&mois=` | Journée moyenne d'un mois (2023), heure par heure |
| `GET /api/orientations?site=` | Production selon l'inclinaison et l'orientation |
| `POST /api/assistant` | Question au RAG (corps : question, contexte facultatif, llm) |
| `GET /donnees/<fichier>` | Téléchargement d'un jeu de données |

## Tests

Depuis `app/backend` : `python -m pytest -q` (19 tests). Dans le conteneur : `docker compose exec app python -m pytest -q -p no:cacheprovider`.

## À savoir

- Les données s'arrêtent le 31/12/2023 (base satellitaire PVGIS-SARAH3). Au-delà, sans saisie, la prévision part
  de la normale saisonnière.
- Une origine antérieure au 6 février 2022 est dans l'échantillon d'apprentissage : l'erreur affichée est optimiste.
- L'assistant envoie à Groq la question et les passages retrouvés, rien d'autre.
- Application de démonstration, sans authentification, à utiliser en local.
