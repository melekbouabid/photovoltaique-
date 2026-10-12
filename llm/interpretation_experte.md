# Interprétation experte, rédigée avant de solliciter le LLM

Ce texte fixe notre propre lecture des résultats **avant** l'envoi des prompts au LLM (section 5 de
l'énoncé), pour pouvoir comparer ensuite les deux interprétations sans être influencés par la réponse
de la machine. Les chiffres viennent du notebook Python (`resultats/py_metriques.csv` et suivants).

## 1. Hypothèses de modèles à partir des statistiques descriptives (pendant du prompt 1)

- La série est dominée par un **cycle annuel déterministe** : ACF de 0,33 au retard 365 et de -0,31 au
  retard 182, production moyenne de 3,06 kWh/kWc par jour en décembre contre 5,43 en juillet. Ce cycle
  se modélise par des termes de Fourier (ou des normales journalières) et non par une différence
  saisonnière de retard 365, impraticable (état de plus de 365 dimensions, 17 cycles seulement).
- Les tests ADF et KPSS concluent tous deux à la stationnarité en niveau : **d = 0**. Différencier
  créerait une autocorrélation négative artificielle (ACF de -0,37 au retard 1 après différence).
- Une fois le cycle retiré, il reste un **AR(1) faible** (ACF de 0,26 au retard 1, PACF coupée ensuite) :
  la prévisibilité au-delà de deux jours sera très faible sans information météo.
- La variance est **plus forte en hiver qu'en été** (écart-type de 1,53 en mars contre 0,41 en juillet)
  et la distribution est asymétrique à gauche : un logarithme serait contre-indiqué ; il faut un modèle
  de variance saisonnière ou conditionnelle (GARCH), et des intervalles non gaussiens.
- Modèles à tester : ARIMA(1,0,0) à termes de Fourier ; SARIMAX avec nébulosité, pluie et aérosols ;
  VAR (production, nébulosité, température) ; GARCH sur les erreurs, avec une variance saisonnière ;
  réseaux récurrents en écart à la normale ; deux références, persistance et climatologie.
- Pièges : prendre l'irradiation PVGIS comme variable explicative (tautologique, la production en est
  calculée), lire le MAPE alors que certains jours valent moins de 0,5 kWh/kWc, appliquer la
  cointégration à des séries stationnaires, oublier que les données sont simulées par satellite.

## 2. Explication pour un décideur (pendant du prompt 2)

Sans prévision météo, on ne sait pas faire beaucoup mieux que « la normale de la saison » : le meilleur
modèle (un réseau de neurones entraîné sur 9 villes) se trompe en moyenne de 0,83 kWh/kWc par jour,
contre 0,86 pour la simple normale, et ce petit gain ne vaut que pour le lendemain et le surlendemain.
La météo d'un jour à Tunis renseigne peu sur celle de la semaine suivante. Avec une prévision météo
(nébulosité, pluie, poussières), l'erreur baisse d'un tiers (0,55 kWh/kWc pour le modèle statistique,
0,50 pour le réseau de neurones). Nous recommandons le modèle statistique avec météo (SARIMAX) : presque
aussi précis que le réseau, il explique ses prévisions (une poussière saharienne d'épaisseur optique 1
coûte environ 1 kWh/kWc, soit 20 % d'une journée) et donne une fourchette fiable. L'incertitude est
plus forte de novembre à avril : les fourchettes doivent être plus larges l'hiver.

## 3. Recommandations et limites (pendant du prompt 3)

1. **Planifier la maintenance et le nettoyage les jours prévus les moins productifs** (perte évitée
   maximale), en priorité au printemps, quand les poussières et les pluies alternent. Limite : la
   prévision au-delà de deux jours ne vaut pas mieux que la normale ; il faut une prévision météo.
2. **Piloter la batterie avec la prévision à un jour** : charger moins sur le réseau la veille d'une
   journée prévue claire. Limite : erreur de 1 kWh/kWc environ un jour sur trois en hiver ; garder une
   marge de sécurité saisonnière (fourchettes du modèle GARCH saisonnier).
3. **Ne pas s'engager auprès du réseau au-delà de J+2 sur une prévision statistique seule.** Limite :
   les intervalles constants sont trop étroits l'hiver (93 % de couverture au lieu de 95 %).
4. **Dimensionner avec PVGIS et non avec l'hypothèse du rapport SolarVision** (1 585 kWh/kWc/an à Tunis,
   soit 142 m² au lieu de 156 m² pour 45 MWh/an). Limite : rayonnement satellitaire, installation
   théorique sans pannes ni ombrages locaux.

Ce que les résultats **ne permettent pas** de conclure : la performance d'une installation réelle
(données simulées), l'apport d'une vraie prévision météo (le modèle ex post utilise la météo observée),
une tendance de long terme de la production (+0,2 % par an, non distinguable d'une dérive satellitaire),
ni un lien de cause à effet entre villes (la causalité de Granger mesure la prévisibilité).
