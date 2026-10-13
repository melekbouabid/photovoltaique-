# Du rapport SolarVision-MLOps au projet de séries temporelles

## Le rapport SolarVision-MLOps

Le rapport « SolarVision-MLOps » propose un système de vision par ordinateur qui segmente les toitures sur des images aériennes ou satellite (modèle principal YOLO11-seg, comparaison avec SegFormer et U-Net), calcule la surface utile en m² puis estime la production solaire annuelle d'un bâtiment. La chaîne MLOps prévue comprend FastAPI, React, DVC, MLflow, ONNX, Docker Compose et GitHub Actions. Les jeux de données envisagés sont Inria Aerial Image Labeling, le jeu de panneaux photovoltaïques de Bradbury et al. (2016), WHU Building et SpaceNet.

## La formule énergétique du rapport

La production annuelle y est estimée par E = S x G x eta x PR : S est la surface utile (m²), G l'irradiation annuelle (kWh/m²/an), eta le rendement des modules (20 %) et PR le ratio de performance (0,8). Exemple du rapport pour une toiture à Tunis, avec G = 1 800 kWh/m²/an : 100 m² utiles produisent 100 x 1 800 x 0,20 x 0,80 = 28 800 kWh/an, et il faut environ 156 m² pour couvrir 45 000 kWh/an. Le rapport précise que G = 1 800 n'est qu'un ordre de grandeur, « à remplacer par la valeur PVGIS pour Tunis ».

## Ce que le projet de séries temporelles apporte

Le projet de séries temporelles part du lien PVGIS du rapport et remplace l'hypothèse annuelle par des données journalières de 2005 à 2023, pour 9 villes : Paris, Lyon, Marseille (France), Tunis, Sfax, Tozeur (Tunisie), Madrid, Séville, Barcelone (Espagne). Il répond à trois questions que le rapport laissait ouvertes :

1. Quelle est la vraie valeur de l'irradiation et du productible à Tunis ? (voir les fiches par ville et la table `data/reference/pvgis_synthese_9_villes.csv`)
2. Comment la production varie-t-elle d'un jour à l'autre et d'une saison à l'autre ?
3. Peut-on prévoir la production des prochains jours, et avec quelle erreur ?

Dans la formule du rapport, le produit G x eta x PR correspond à la production d'1 kWc multipliée par 0,2 kWc/m² (un module de rendement 20 % fournit 0,2 kWc par m²). Le projet fournit directement cette production d'1 kWc, jour par jour.

## Les autres liens du rapport

Le rapport contient 21 liens différents : 11 articles sur arXiv (U-Net, ResNet, YOLO, Faster R-CNN, Mask R-CNN, revue YOLO, Segment Anything, Vision Transformer, Swin Transformer, SegFormer, MLOps), 3 articles d'éditeurs (jeu de données PV de Bradbury, inventaire mondial du PV de Kruitwagen et al. dans Nature, dette technique des systèmes d'apprentissage de Sculley et al.), la documentation d'Ultralytics YOLO11, 5 pages de jeux d'images aériennes (Inria, son miroir Hugging Face, figshare de Bradbury, WHU, SpaceNet) et l'outil PVGIS. Seul PVGIS fournit des séries temporelles. Les résumés des articles ont été récupérés pour le corpus de l'assistant ; les jeux d'images ne sont pas téléchargés, car ils ne contiennent pas de séries temporelles.
