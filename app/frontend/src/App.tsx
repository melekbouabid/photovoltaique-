import { useEffect, useState } from "react";
import { api } from "./api";
import { Assistant } from "./Assistant";
import { ComparaisonPays } from "./ComparaisonPays";
import { JeuxDeDonnees } from "./JeuxDeDonnees";
import { LumiereDuJour } from "./LumiereDuJour";
import { ModelesEtude } from "./ModelesEtude";
import { Orientation } from "./Orientation";
import { Prevoir } from "./Prevoir";
import { BoutonTheme, COULEUR_PAYS, Message, Soleil, fmt, useChargement } from "./outils";

const SECTIONS = [
  { id: "prevoir", libelle: "Prévoir" }, { id: "assistant", libelle: "Assistant" },
  { id: "lumiere", libelle: "Lumière" }, { id: "orientation", libelle: "Toiture" },
  { id: "pays", libelle: "Pays" }, { id: "modeles", libelle: "Modèles" }, { id: "donnees", libelle: "Données" },
];

/** Section visible à l'écran, pour signaler le lien actif du bandeau. */
function useSectionActive(ids: string[]) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    const obs = new IntersectionObserver((entrees) => {
      const visibles = entrees.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visibles.length) setActive(visibles[0].target.id);
    }, { rootMargin: "-80px 0px -55% 0px" });
    const minuterie = window.setTimeout(() => ids.forEach((id) => { const el = document.getElementById(id); if (el) obs.observe(el); }), 500);
    return () => { window.clearTimeout(minuterie); obs.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return active;
}

export default function App() {
  const info = useChargement(api.info, []);
  const catalogue = useChargement(api.catalogue, []);
  const modeles = useChargement(api.modeles, []);
  const [demande, setDemande] = useState<{ contexte: string; cle: number } | null>(null);
  const active = useSectionActive(SECTIONS.map((s) => s.id));

  // « Poser une question sur cette prévision » : la réponse affichée devient le contexte de l'assistant.
  const versAssistant = (contexte: string) => {
    setDemande({ contexte, cle: Date.now() });
    document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const productible = (pays: string) => {
    const s = (info.donnees?.sites ?? []).filter((x) => x.pays === pays);
    return s.length ? s.reduce((a, x) => a + x.productible_kwh_kwc_an, 0) / s.length : 0;
  };
  const jeux = catalogue.donnees?.jeux ?? [];
  const chiffres = [
    { valeur: jeux.length || null, libelle: "jeux de données" },
    { valeur: jeux.reduce((s, j) => s + j.lignes, 0) || null, libelle: "lignes" },
    { valeur: jeux.find((j) => j.fichier.includes("panel"))?.variables_explicatives ?? null, libelle: "variables par jour et par ville" },
    { valeur: info.donnees?.sites.length ?? null, libelle: "villes, 3 pays" },
    { valeur: modeles.donnees?.etude.length ?? null, libelle: "modèles comparés" },
  ];

  return (
    <>
      <header className="bandeau">
        <div className="bandeau-contenu">
          <a className="marque" href="#prevoir"><Soleil /><span>SolarVision <em>Séries temporelles</em></span></a>
          <nav aria-label="Sections de la page">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`} className={active === s.id ? "actif" : ""}
                 aria-current={active === s.id ? "true" : undefined}>{s.libelle}</a>
            ))}
          </nav>
          <BoutonTheme />
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-texte">
            <h1>Prévoir le soleil des prochains jours, ville par ville</h1>
            <p>
              Production photovoltaïque et éclairement solaire en France, en Tunisie et en Espagne : 19 années de données
              PVGIS (le lien « séries temporelles » du rapport SolarVision), des modèles ARIMA, VAR, GARCH et LSTM, et un
              assistant qui répond à vos questions en citant ses sources.
            </p>
            <ul className="chiffres-cles" aria-label="Le projet en chiffres">
              {chiffres.map((c) => (
                <li key={c.libelle}><strong>{c.valeur === null ? "…" : fmt(c.valeur)}</strong> {c.libelle}</li>
              ))}
            </ul>
            <div className="hero-actions">
              <a className="bouton-principal" href="#prevoir">Lancer une prévision</a>
              <a className="bouton-secondaire" href="#assistant">Poser une question</a>
            </div>
          </div>
          {info.donnees && (
            <div className="chiffres-hero" aria-label="Productible moyen par pays">
              {["France", "Tunisie", "Espagne"].map((p) => (
                <div className="chiffre" key={p}>
                  <span className="chiffre-pays"><span className="cle-ligne" style={{ background: COULEUR_PAYS[p] }} />{p}</span>
                  <span className="chiffre-valeur">{fmt(productible(p))} <small>kWh/kWc/an</small></span>
                  <span className="chiffre-note">
                    {info.donnees!.sites.filter((s) => s.pays === p).map((s) => s.ville).join(", ")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        <Message erreur={info.erreur && `API injoignable : ${info.erreur}. Le backend est-il lancé sur le port 8000 ?`}
                 enCours={info.enCours} vide={!info.donnees} />
        {info.donnees && <Prevoir info={info.donnees} onQuestion={versAssistant} />}
        <Assistant demande={demande} />
        {info.donnees && <LumiereDuJour info={info.donnees} />}
        {info.donnees && <Orientation info={info.donnees} />}
        <ComparaisonPays />
        <ModelesEtude />
        <JeuxDeDonnees />
      </main>

      <footer>
        <p>
          Données : PVGIS © Union européenne (JRC, rayonnement SARAH3, météo ERA5) ; Open-Meteo (ERA5, CC BY 4.0) ;
          NASA POWER (LaRC) ; RTE éCO2mix via ODRÉ (Licence Ouverte v2.0) ; Red Eléctrica (REData). Mini-projet
          Séries temporelles pour la data science. API : <a href="/docs">documentation Swagger</a>.
        </p>
      </footer>
    </>
  );
}
