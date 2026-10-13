import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, Profil, Variable } from "./api";
import { COULEUR_PAYS, Infobulle, MOIS, Message, fmt, marche, useChargement } from "./outils";

const PAYS = ["France", "Tunisie", "Espagne"];

/** Comparaison France / Tunisie / Espagne : profil saisonnier par pays et total annuel par ville. */
export function ComparaisonPays() {
  const [variable, setVariable] = useState<Variable>("pv_kwh_kwc");
  const { donnees, erreur, enCours } = useChargement(() => api.profils(variable), [variable]);
  const estPV = variable === "pv_kwh_kwc";
  const unite = estPV ? "kWh/kWc" : "kWh/m²";

  // Profil d'un pays = moyenne de ses trois villes, mois par mois (3 séries : une par pays).
  const parPays = (p: string) => (donnees ?? []).filter((d) => d.pays === p);
  const mensuel = MOIS.map((m, i) => {
    const ligne: Record<string, number | string> = { mois: m };
    for (const p of PAYS) {
      const v = parPays(p);
      if (v.length) ligne[p] = v.reduce((s, d) => s + d.mensuel[i], 0) / v.length;
    }
    return ligne;
  });
  const annuel = [...(donnees ?? [])].sort((a, b) => b.annuel - a.annuel);
  const tousMois = (donnees ?? []).flatMap((d) => d.mensuel);
  const miniM = Math.min(...tousMois), maxiM = Math.max(...tousMois);

  return (
    <section className="carte" id="pays" aria-labelledby="titre-pays">
      <div className="carte-entete">
        <div>
          <h2 id="titre-pays">France, Tunisie, Espagne</h2>
          <p className="sous-titre">Moyennes 2005-2023 des 9 villes, données PVGIS (1 kWc à la pente optimale, plein sud).</p>
        </div>
        <div className="segments" role="group" aria-label="Grandeur comparée">
          <button className={estPV ? "actif" : ""} aria-pressed={estPV} onClick={() => setVariable("pv_kwh_kwc")}>Photovoltaïque</button>
          <button className={!estPV ? "actif" : ""} aria-pressed={!estPV} onClick={() => setVariable("ghi_kwh_m2")}>Éclairement</button>
        </div>
      </div>
      <Message erreur={erreur} enCours={enCours} vide={!donnees} />
      {donnees && (
        <div className={`deux-colonnes ${enCours ? "attente" : ""}`}>
          <div>
            <h3>Profil saisonnier ({unite} par jour, moyenne des 3 villes)</h3>
            <ul className="legende" aria-label="Légende">
              {PAYS.map((p) => <li key={p}><span className="cle-ligne" style={{ background: COULEUR_PAYS[p] }} />{p}</li>)}
            </ul>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={mensuel} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--grille)" vertical={false} />
                <XAxis dataKey="mois" tickLine={false} stroke="var(--axe)" tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} />
                <YAxis width={36} tickLine={false} axisLine={false} domain={[0, "auto"]}
                       tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} />
                <Tooltip cursor={{ stroke: "var(--axe)" }} content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <Infobulle titre={String(label)} lignes={PAYS.map((p) => ({
                      nom: p, couleur: COULEUR_PAYS[p],
                      valeur: `${fmt(Number(payload.find((x) => x.dataKey === p)?.value ?? 0), 2)} ${unite}`,
                    }))} />
                  ) : null} />
                {PAYS.map((p) => (
                  <Line key={p} dataKey={p} stroke={COULEUR_PAYS[p]} strokeWidth={2} isAnimationActive={false}
                        dot={{ r: 4, fill: COULEUR_PAYS[p], stroke: "var(--surface)", strokeWidth: 2 }} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h3>Total annuel par ville ({estPV ? "kWh/kWc" : "kWh/m²"} par an)</h3>
            <ul className="legende" aria-label="Légende">
              {PAYS.map((p) => <li key={p}><span className="cle-bloc" style={{ background: COULEUR_PAYS[p] }} />{p}</li>)}
            </ul>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={annuel} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 8 }} barCategoryGap={6}>
                <CartesianGrid stroke="var(--grille)" horizontal={false} />
                <XAxis type="number" hide domain={[0, "dataMax"]} />
                <YAxis type="category" dataKey="ville" width={78} tickLine={false} axisLine={false}
                       tick={{ fill: "var(--encre-secondaire)", fontSize: 12 }} />
                <Tooltip cursor={{ fill: "var(--grille)", opacity: 0.4 }} content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as Profil;
                  return <Infobulle titre={`${d.ville} (${d.pays})`} lignes={[{ nom: "par an", couleur: COULEUR_PAYS[d.pays], valeur: `${fmt(d.annuel)} ${estPV ? "kWh/kWc" : "kWh/m²"}` }]} />;
                }} />
                <Bar dataKey="annuel" maxBarSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
                  {annuel.map((d) => <Cell key={d.site} fill={COULEUR_PAYS[d.pays]} />)}
                  <LabelList dataKey="annuel" position="right" formatter={(v: number) => fmt(v)}
                             style={{ fill: "var(--encre-secondaire)", fontSize: 12 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {estPV && (
              <p className="note">
                Somme annuelle moyenne des séries journalières 2005-2023 ; elle est inférieure de moins de 1,5 % au productible
                PVGIS de long terme affiché sur les cartes des villes.
              </p>
            )}
          </div>
        </div>
      )}
      {donnees && (
        <>
          <h3>Carte de chaleur : moyenne journalière par mois et par ville ({unite})</h3>
          <div className="chaleur chaleur-mois" role="table" aria-label={`Moyenne journalière par mois et par ville, ${unite}`}>
            <div role="row" className="chaleur-ligne">
              <span role="columnheader" className="chaleur-entete" />
              {MOIS.map((m) => <span role="columnheader" key={m} className="chaleur-entete">{m}</span>)}
            </div>
            {[...donnees].sort((a, b) => b.annuel - a.annuel).map((d) => (
              <div role="row" className="chaleur-ligne" key={d.site}>
                <span role="rowheader" className="chaleur-entete chaleur-ville">
                  <span className="cle-ligne" style={{ background: COULEUR_PAYS[d.pays] }} />{d.ville}
                </span>
                {d.mensuel.map((v, i) => (
                  <span role="cell" key={i} className={`chaleur-cellule c${marche(v, miniM, maxiM)}`}
                        title={`${d.ville}, ${MOIS[i]} : ${fmt(v, 2)} ${unite} par jour`}>{fmt(v, 1)}</span>
                ))}
              </div>
            ))}
          </div>
          <div className="echelle" aria-hidden="true">
            <span>{fmt(miniM, 1)}</span><span className="echelle-barre" /><span>{fmt(maxiM, 1)} {unite}</span>
          </div>
        </>
      )}
      {donnees && (
        <details className="tableau-details">
          <summary>Tableau des valeurs mensuelles par ville ({unite} par jour)</summary>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr><th>Ville</th><th>Pays</th>{MOIS.map((m) => <th key={m} className="num">{m}</th>)}<th className="num">Année</th></tr>
              </thead>
              <tbody>
                {donnees.map((d) => (
                  <tr key={d.site}>
                    <td>{d.ville}</td><td>{d.pays}</td>
                    {d.mensuel.map((v, i) => <td key={i} className="num">{fmt(v, 2)}</td>)}
                    <td className="num">{fmt(d.annuel)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}
