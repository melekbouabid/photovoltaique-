<!-- modèle : qwen3-vl:8b-instruct (Ollama, local) | options : {'temperature': 0, 'seed': 42, 'num_ctx': 8192} | date : 2026-10-10 -->

**Recommandation 1 : Planifier le nettoyage des modules en fonction des prévisions ex post (météo observée).**  
→ Utiliser le modèle LSTM ex post (MAE 0.50 kWh/kWc/jour) pour anticiper les périodes de faible production (ex : janvier, novembre).  
*Limites :* Ce modèle repose sur des données simulées (PVGIS), non mesurées sur site, donc moins fiables en cas de pollution ou de dégradation locale.  
*Risque :* Surévaluation de la production en période sèche, conduisant à un nettoyage inutile ou trop tardif.

**Recommandation 2 : Piloter la batterie en fonction des prévisions ex ante (LSTM global) pour optimiser le stockage.**  
→ Le modèle ex ante (MAE 0.83) permet une planification à court terme (jusqu’à 7 jours) pour charger la batterie en période de forte production (juillet).  
*Limites :* L’erreur (MAPE 29.4 %) reste élevée, surtout en hiver.  
*Risque :* Surcharge ou sous-utilisation de la batterie en période de forte incertitude (novembre-mars).

**Recommandation 3 : Engager la production vers le réseau en fonction des prévisions ex post, avec un seuil de confiance.**  
→ En période de forte production (juillet), utiliser le modèle ex post pour engager la production avec un seuil de confiance (ex : 90 % de la production prévue).  
*Limites :* Le modèle ex post est plus précis mais dépend de la météo observée, donc moins adapté aux périodes de forte incertitude.  
*Risque :* Engager trop tôt en cas de mauvais temps, ou trop tard en cas de forte production.

**Recommandation 4 : Informer les usagers via un tableau de bord basé sur les prévisions ex post.**  
→ Afficher les prévisions journalières (MAE 0.50) pour les usagers, avec une marge d’erreur (ex : ±15 %).  
*Limites :* Les données sont simulées, donc les usagers pourraient être trompés en cas de déviation importante.  
*Risque :* Perte de confiance si les prévisions ne correspondent pas à la réalité.

**Ce que ces résultats ne permettent PAS de conclure :**  
→ Ils ne permettent pas de valider la performance d’un modèle sur une installation réelle (données simulées).  
→ Ils ne permettent pas de conclure sur la fiabilité des prévisions en cas de conditions météorologiques extrêmes (ex : orages, neige).  
→ Ils ne permettent pas de conclure sur l’impact des dégradations physiques des modules (poussière, salissures, fissures).  
→ Ils ne permettent pas de conclure sur la rentabilité économique ou la rentabilité énergétique à long terme.
