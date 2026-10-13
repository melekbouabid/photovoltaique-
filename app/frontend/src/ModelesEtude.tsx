import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Variable } from "./api";
import { Infobulle, Message, fmt, useChargement } from "./outils";

// Quatre modèles au plus sur le graphique, couleur attachée au modèle (jamais à son rang).
const COURBES = [
  { modele: "Persistance (J)", nom: "Persistance", couleur: "var(--serie-2)" },
  { modele: "Climatologie", nom: "Climatologie", couleur: "var(--encre-attenuee)" },
  { modele: "ARIMA-Fourier manuel", nom: "ARIMA-Fourier", couleur: "var(--serie-1)" },
  { modele: "SARIMAX météo (ex post)", nom: "SARIMAX météo (ex post)", couleur: "var(--serie-3)" },
];
const NOMS_APP: Record<string, string> = { lstm: "LSTM global", arima: "ARIMA-Fourier", climatologie: "Climatologie", persistance: "Persistance" };

/** Résultats de l'étude (Tunis) et précision des modèles servis par l'application (9 villes). */
export function ModelesEtude() {
  const { donnees, erreur, enCours } = useChargement(api.modeles, []);
  const [variable, setVariable] = useState<Variable>("pv_kwh_kwc");
  const etude = donnees?.etude ?? [];
  const parNom = new Map(etude.map((m) => [m.modele, m]));
  const courbes = COURBES.filter((c) => parNom.has(c.modele));
  const horizons = Array.from({ length: 7 }, (_, h) => {
    const ligne: Record<string, number> = { horizon: h + 1 };
    for (const c of courbes) ligne[c.modele] = parNom.get(c.modele)!.rmse_par_horizon[h];
    return ligne;
  });
  const maxi = Math.max(1e-9, ...etude.map((m) => m.rmse));
  const appli = donnees?.application.rmse_test[variable] ?? {};

  return (
    <section className="carte" id="modeles" aria-labelledby="titre-modeles">
      <div className="carte-entete">
        <div>
          <h2 id="titre-modeles">Modèles de l'étude</h2>
          <p className="sous-titre">
            Production d'1 kWc à Tunis : prévisions glissantes à 7 jours sur la période de test (février 2022 à
            décembre 2023), erreurs en kWh/kWc par jour. Détail dans le notebook et le rapport.
          </p>
        </div>
      </div>
      <Message erreur={erreur} enCours={enCours} vide={!donnees} />
      {etude.length > 0 && (
        <>
          <h3>Erreur selon l'horizon (RMSE)</h3>
          <ul className="legende" aria-label="Légende">
            {courbes.map((c) => <li key={c.modele}><span className="cle-ligne" style={{ background: c.couleur }} />{c.nom}</li>)}
          </ul>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={horizons} margin={{ top: 8, right: 16, bottom: 18, left: 0 }}>
              <CartesianGrid stroke="var(--grille)" vertical={false} />
              <XAxis dataKey="horizon" tickLine={false} stroke="var(--axe)" tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }}
                     label={{ value: "horizon (jours)", position: "insideBottom", offset: -12, fill: "var(--encre-attenuee)", fontSize: 12 }} />
              <YAxis width={40} tickLine={false} axisLine={false} domain={[0, "auto"]}
                     tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} tickFormatter={(v) => fmt(v, 1)} />
              <Tooltip cursor={{ stroke: "var(--axe)" }} content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <Infobulle titre={`Horizon : ${label} jour${Number(label) > 1 ? "s" : ""}`} lignes={courbes.map((c) => ({
                    nom: c.nom, couleur: c.couleur,
                    valeur: fmt(Number(payload.find((x) => x.dataKey === c.modele)?.value ?? 0), 3),
                  }))} />
                ) : null} />
              {courbes.map((c) => (
                <Line key={c.modele} dataKey={c.modele} stroke={c.couleur} strokeWidth={2} isAnimationActive={false}
                      dot={{ r: 4, fill: c.couleur, stroke: "var(--surface)", strokeWidth: 2 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>

          <div className="tableau-defilant">
            <table>
              <caption>Tous les modèles, toutes origines et tous horizons confondus</caption>
              <thead>
                <tr>
                  <th>Modèle</th><th>Information</th><th>RMSE</th><th className="num">MAE</th>
                  <th className="num">MAPE</th><th className="num">Couverture IC 95 %</th><th className="num">Paramètres</th>
                </tr>
              </thead>
              <tbody>
                {etude.map((m) => (
                  <tr key={m.modele}>
                    <td>{m.modele.replace(/ \(ex (ante|post)\)/, "")}</td>
                    <td>{m.information}</td>
                    <td>
                      <div className="barre-ligne">
                        <span className="barre" style={{ width: `${(100 * m.rmse) / maxi}%` }} />
                        <span className="num">{fmt(m.rmse, 3)}</span>
                      </div>
                    </td>
                    <td className="num">{fmt(m.mae, 3)}</td>
                    <td className="num">{fmt(m.mape_pct, 1)} %</td>
                    <td className="num">{m.couverture_ic95_pct === null ? "—" : `${fmt(m.couverture_ic95_pct, 1)} %`}</td>
                    <td className="num">{fmt(m.nb_parametres)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {donnees && (
        <>
          <div className="carte-entete sous-section">
            <h3>Modèles servis par l'application : RMSE à 1-7 jours sur la période de test, par ville</h3>
            <div className="segments" role="group" aria-label="Grandeur">
              <button className={variable === "pv_kwh_kwc" ? "actif" : ""} aria-pressed={variable === "pv_kwh_kwc"}
                      onClick={() => setVariable("pv_kwh_kwc")}>Photovoltaïque</button>
              <button className={variable === "ghi_kwh_m2" ? "actif" : ""} aria-pressed={variable === "ghi_kwh_m2"}
                      onClick={() => setVariable("ghi_kwh_m2")}>Éclairement</button>
            </div>
          </div>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr><th>Ville</th>{Object.values(NOMS_APP).map((n) => <th key={n} className="num">{n}</th>)}</tr>
              </thead>
              <tbody>
                {Object.entries(appli).map(([site, r]) => {
                  const meilleur = Math.min(...Object.values(r));
                  return (
                    <tr key={site}>
                      <td>{site.charAt(0).toUpperCase() + site.slice(1)}</td>
                      {Object.keys(NOMS_APP).map((k) => (
                        <td key={k} className={`num ${r[k as keyof typeof r] === meilleur ? "meilleur" : ""}`}>
                          {fmt(r[k as keyof typeof r], 3)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="note">En gras : la plus petite erreur de la ligne. Sans information sur la météo à venir, aucun modèle ne
            fait beaucoup mieux que la normale saisonnière au-delà de deux jours : la météo d'un jour renseigne peu sur celle de la semaine suivante.</p>
        </>
      )}
    </section>
  );
}
