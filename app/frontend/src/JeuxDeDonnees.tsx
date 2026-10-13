import { useState } from "react";
import { api, JeuDeDonnees } from "./api";
import { Message, fmt, useChargement } from "./outils";

const CATEGORIES = ["série temporelle", "article", "jeu d'images", "documentation"];
const PLURIELS: Record<string, string> = {
  "série temporelle": "séries temporelles", article: "articles", "jeu d'images": "jeux d'images", documentation: "documentations",
};

/** Les 14 jeux de données construits, leur conformité (plus de 1 000 lignes, au moins 20 variables) et leurs variables. */
export function JeuxDeDonnees() {
  const { donnees, erreur, enCours } = useChargement(api.catalogue, []);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const liens = donnees?.liens ?? [];
  const jeux = donnees?.jeux ?? [];
  const conformes = jeux.filter((j) => j.conforme).length;
  const totalLignes = jeux.reduce((s, j) => s + j.lignes, 0);

  return (
    <section className="carte" id="donnees" aria-labelledby="titre-donnees">
      <div className="carte-entete">
        <div>
          <h2 id="titre-donnees">Jeux de données</h2>
          <p className="sous-titre">
            Construits par <code>python/collecte_donnees.py</code> à partir du lien PVGIS du rapport SolarVision, complété par
            Open-Meteo (ERA5), NASA POWER, RTE et REE. Chaque jeu compte plus de 1 000 lignes et au moins 20 variables
            explicatives. Fiches complètes : <code>data/LISEZMOI_donnees.md</code>.
          </p>
        </div>
      </div>
      <Message erreur={erreur} enCours={enCours} vide={!donnees} />
      {donnees && (
        <>
          <div className="tuiles">
            <div className="tuile">
              <span className="tuile-libelle">Jeux de données conformes</span>
              <span className="tuile-valeur">{conformes} / {jeux.length}</span>
              <span className="tuile-note">plus de 1 000 lignes et au moins 20 variables chacun</span>
            </div>
            <div className="tuile">
              <span className="tuile-libelle">Lignes au total</span>
              <span className="tuile-valeur">{fmt(totalLignes)}</span>
              <span className="tuile-note">journalier, horaire, mensuel, scénarios</span>
            </div>
            <div className="tuile">
              <span className="tuile-libelle">Variables du panel</span>
              <span className="tuile-valeur">{jeux.find((j) => j.fichier.includes("panel"))?.variables_explicatives ?? "—"}</span>
              <span className="tuile-note">PVGIS, météo, aérosols, éclairage naturel, astronomie, retards</span>
            </div>
            <div className="tuile">
              <span className="tuile-libelle">Liens du rapport visités</span>
              <span className="tuile-valeur">{liens.length}</span>
              <span className="tuile-note">
                {CATEGORIES.map((c) => {
                  const n = liens.filter((l) => l.categorie === c).length;
                  return `${n} ${n > 1 ? PLURIELS[c] : c}`;
                }).join(" · ")}
              </span>
            </div>
          </div>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Fichier</th><th>Thème</th><th>Pays</th><th className="num">Lignes</th>
                  <th className="num">Variables</th><th>Période</th><th>Conformité</th><th />
                </tr>
              </thead>
              <tbody>
                {jeux.map((j) => <LigneJeu key={j.fichier} j={j} ouvert={ouvert === j.fichier}
                                           basculer={() => setOuvert(ouvert === j.fichier ? null : j.fichier)} />)}
              </tbody>
            </table>
          </div>
          <details className="tableau-details">
            <summary>Les {liens.length} liens du rapport SolarVision et leur usage</summary>
            <ul className="liste-liens">
              {liens.map((l) => (
                <li key={l.url}>
                  <span className="etiquette">{l.categorie}</span>
                  <a href={l.url} target="_blank" rel="noreferrer">{l.titre || l.url}</a>
                  <span className="source-chemin">{l.usage || l.statut}</span>
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
    </section>
  );
}

function LigneJeu({ j, ouvert, basculer }: { j: JeuDeDonnees; ouvert: boolean; basculer: () => void }) {
  const nom = j.fichier.split("/").pop()!;
  return (
    <>
      <tr title={j.description}>
        <td><code>{nom}</code></td>
        <td>{j.theme}</td>
        <td>{j.pays}</td>
        <td className="num">{fmt(j.lignes)}</td>
        <td className="num">{j.variables_explicatives}</td>
        <td>{j.periode ? `${j.periode[0].slice(0, 7)} → ${j.periode[1].slice(0, 7)}` : "—"}</td>
        <td>
          <span className={`badge ${j.conforme ? "badge-ok" : "badge-non"}`}>
            <span aria-hidden="true">{j.conforme ? "✓" : "✗"}</span> {j.conforme ? "conforme" : "non conforme"}
          </span>
        </td>
        <td className="actions">
          <button type="button" className="lien-bouton" aria-expanded={ouvert} onClick={basculer}>
            {ouvert ? "Masquer" : "Variables"}
          </button>
          <a href={`/donnees/${nom}`} download className="lien-telechargement">CSV</a>
        </td>
      </tr>
      {ouvert && (
        <tr className="ligne-detail">
          <td colSpan={8}>
            <p className="note">{j.description}. Taille : {fmt(j.taille_ko / 1024, 1)} Mo ; valeurs manquantes : {fmt(j.valeurs_manquantes_pct, 2)} %.</p>
            <div className="variables-grille">
              {j.variables.map((v) => (
                <div key={v.nom} className="variable">
                  <code>{v.nom}</code>
                  <span className="variable-unite">{v.unite !== "-" ? v.unite : ""}</span>
                  <span className="variable-desc">{v.description}</span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
