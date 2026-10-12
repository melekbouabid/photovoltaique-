// Client de l'API FastAPI. Les types reprennent les schémas Pydantic du backend (app/backend/main.py).

export type Variable = "pv_kwh_kwc" | "ghi_kwh_m2";
export type Modele = "lstm" | "arima" | "climatologie" | "persistance";

export interface Site {
  site: string;
  ville: string;
  pays: string;
  code_pays: string;
  latitude: number;
  longitude: number;
  pente_optimale_deg: number;
  productible_kwh_kwc_an: number;
  irradiation_plan_kwh_m2_an: number;
}

export interface Info {
  debut: string;
  fin: string;
  fin_apprentissage: string;
  origine_min: string;
  origine_max: string;
  horizon_max: number;
  sites: Site[];
  variables: Record<Variable, { libelle: string; unite: string; court: string }>;
  modeles: Record<Modele, string>;
}

export interface ValeurRecente {
  date: string;
  valeur: number;
  source: string;
}

export interface PointPrevision {
  date: string;
  horizon: number;
  prevision: number;
  bas: number | null;
  haut: number | null;
  normale: number;
  observe: number | null;
}

export interface Prevision {
  site: string;
  ville: string;
  pays: string;
  variable: Variable;
  unite: string;
  modele: Modele;
  nom_modele: string;
  origine: string;
  horizon: number;
  puissance_kwc: number;
  conso_kwh_jour: number | null;
  valeurs_saisies: number;
  hors_donnees: boolean;
  dans_apprentissage: boolean;
  mae_prevision: number | null;
  total: number;
  total_bas: number | null;
  total_haut: number | null;
  total_normale: number;
  ecart_normale_pct: number;
  mae_test_modele: number | null;
  reponse: string;
  historique: { date: string; valeur: number; source: string }[];
  previsions: PointPrevision[];
}

export interface DemandePrevision {
  site: string;
  variable: Variable;
  modele: Modele;
  origine: string;
  horizon: number;
  puissance_kwc: number;
  conso_kwh_jour: number | null;
  valeurs_recentes: number[] | null;
}

export interface SourceRAG {
  rang: number;
  titre: string;
  source: string;
  score: number;
  extrait: string;
}

export interface ReponseAssistant {
  question: string;
  reponse: string;
  mode: string;
  sources: SourceRAG[];
  prevision: Prevision | null;
}

export interface Profil extends Site {
  mensuel: number[];
  annuel: number;
}

export interface JeuDeDonnees {
  fichier: string;
  description: string;
  theme: string;
  pays: string;
  lignes: number;
  colonnes: number;
  variables_explicatives: number;
  conforme: boolean;
  periode: [string, string] | null;
  taille_ko: number;
  valeurs_manquantes_pct: number;
  variables: { nom: string; unite: string; description: string }[];
}

export interface HeureProfil {
  heure: number;
  p_w_kwc: number;
  ghi_w_m2: number;
  eclairement_klux: number;
  part_lumiere_suffisante: number;
  nebulosite_pct: number | null;
  t_module_c: number;
  t2m_c: number;
}

export interface ProfilHoraire {
  site: string;
  ville: string;
  mois: number;
  heures: HeureProfil[];
  resume: {
    heures_lumiere_10klux: number;
    premiere_heure_jour: number | null;
    derniere_heure_jour: number | null;
    eclairement_max_klux: number;
    production_jour_kwh_kwc: number;
  };
}

export interface Scenario {
  inclinaison: number;
  azimut: number;
  orientation: string;
  est_optimal: boolean;
  e_an_kwh_kwc: number;
  part_optimal_pct: number;
  mensuel_kwh_kwc: number[];
}

export interface Orientations {
  site: string;
  ville: string;
  pente_optimale: number;
  productible_optimal_kwh_kwc: number;
  scenarios: Scenario[];
}

export interface LienRapport {
  url: string;
  categorie: string;
  statut: string;
  titre: string;
  usage: string;
}

export interface MetriquesModele {
  modele: string;
  information: string;
  famille: string;
  rmse: number;
  mae: number;
  mape_pct: number;
  couverture_ic95_pct: number | null;
  nb_parametres: number;
  rmse_par_horizon: number[];
}

export interface Modeles {
  etude: MetriquesModele[];
  application: {
    ordre_arima: number[];
    K_fourier: number;
    fin_apprentissage: string;
    rmse_test: Record<Variable, Record<string, Record<Modele, number>>>;
    mae_test: Record<Variable, Record<string, Record<Modele, number>>>;
  };
}

async function traiter<T>(reponse: Response): Promise<T> {
  if (!reponse.ok) {
    // FastAPI renvoie {detail: "..."} ou, pour une erreur de validation, {detail: [{msg: "..."}]}.
    const corps = await reponse.json().catch(() => null);
    const detail = corps?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.[0]?.msg ?? `Erreur ${reponse.status}`);
  }
  return reponse.json();
}

async function lire<T>(chemin: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const q = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(params)) if (valeur !== undefined) q.set(cle, String(valeur));
  return traiter<T>(await fetch(`/api/${chemin}${q.size ? `?${q}` : ""}`));
}

async function envoyer<T>(chemin: string, corps: unknown): Promise<T> {
  return traiter<T>(await fetch(`/api/${chemin}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps),
  }));
}

export const api = {
  info: () => lire<Info>("info"),
  valeursRecentes: (site: string, variable: Variable, origine: string, n = 14) =>
    lire<ValeurRecente[]>("valeurs_recentes", { site, variable, origine, n }),
  prevision: (d: DemandePrevision) => envoyer<Prevision>("prevision", d),
  assistant: (question: string, contexte: string | null, llm = true) =>
    envoyer<ReponseAssistant>("assistant", { question, contexte, llm }),
  profils: (variable: Variable) => lire<Profil[]>("profils", { variable }),
  catalogue: () => lire<{ jeux: JeuDeDonnees[]; liens: LienRapport[] }>("catalogue"),
  modeles: () => lire<Modeles>("modeles"),
  profilHoraire: (site: string, mois: number) => lire<ProfilHoraire>("profil_horaire", { site, mois }),
  orientations: (site: string) => lire<Orientations>("orientations", { site }),
};
