import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Info, Scenario } from "./api";
import { Infobulle, MOIS, Message, fmt, marche, useChargement } from "./outils";

const ORIENTATIONS = ["est", "sud-est", "sud", "sud-ouest", "ouest"];

/** Inclinaison et orientation d'une toiture : part du productible optimal (carte de chaleur) et calculateur. */
export function Orientation({ info }: { info: Info }) {
  const [site, setSite] = useState("tunis");
  const [choix, setChoix] = useState<{ inclinaison: number; orientation: string } | null>(null);
  const [kwc, setKwc] = useState("3");
  const { donnees, erreur, enCours } = useChargement(() => api.orientations(site), [site]);

  const lignes = useMemo(() => {
    if (!donnees) return [];
    const inc = [...new Set(donnees.scenarios.map((s) => s.inclinaison))].sort((a, b) => a - b);
    return inc.map((i) => ({
      inclinaison: i,
      cellules: ORIENTATIONS.map((o) => donnees.scenarios.find((s) => s.inclinaison === i && (s.orientation === o || i === 0)) ?? null),
    }));
  }, [donnees]);
  const parts = donnees?.scenarios.map((s) => s.part_optimal_pct) ?? [];
  const mini = Math.min(...parts), maxi = Math.max(...parts);
  const opt = donnees?.scenarios.find((s) => s.est_optimal);
  const facade = donnees?.scenarios.find((s) => s.inclinaison === 90 && s.orientation === "sud");
  const est30 = donnees?.scenarios.find((s) => s.inclinaison === 30 && s.orientation === "est");
  const actif: Scenario | undefined = donnees?.scenarios.find((s) =>
    choix ? s.inclinaison === choix.inclinaison && (s.orientation === choix.orientation || s.inclinaison === 0) : s.est_optimal);
  const puissance = Math.max(Number(kwc.replace(",", ".")) || 1, 0.1);
  const mensuel = (actif?.mensuel_kwh_kwc ?? []).map((v, i) => ({ mois: MOIS[i], valeur: v * puissance }));

  return (
    <section className="carte" id="orientation" aria-labelledby="titre-orientation">
      <div className="carte-entete">
        <div>
          <h2 id="titre-orientation">Inclinaison et orientation de la toiture</h2>
          <p className="sous-titre">
            Le lien avec SolarVision : une fois la surface de toiture détectée, quelle production selon sa pente et son
            orientation ? Scénarios PVGIS (moyennes 2005-2023), de la toiture plate (0°) à la façade verticale (90°).
          </p>
        </div>
        <label className="champ-compact">
          <span>Ville</span>
          <select value={site} onChange={(e) => { setSite(e.target.value); setChoix(null); }}>
            {info.sites.map((s) => <option key={s.site} value={s.site}>{s.ville} ({s.pays})</option>)}
          </select>
        </label>
      </div>
      <Message erreur={erreur} enCours={enCours} vide={!donnees} />
      {donnees && (
        <div className={`deux-colonnes ${enCours ? "attente" : ""}`}>
          <div>
            <h3>Part de la production à la pente optimale plein sud ({fmt(donnees.pente_optimale)}°)</h3>
            <div className="chaleur chaleur-orientation" role="table" aria-label="Part du productible optimal selon l'inclinaison et l'orientation">
              <div role="row" className="chaleur-ligne">
                <span role="columnheader" className="chaleur-entete" />
                {ORIENTATIONS.map((o) => <span role="columnheader" key={o} className="chaleur-entete">{o}</span>)}
              </div>
              {lignes.map((l) => (
                <div role="row" className="chaleur-ligne" key={l.inclinaison}>
                  <span role="rowheader" className="chaleur-entete">{fmt(l.inclinaison)}°{l.inclinaison === 0 ? " (à plat)" : ""}</span>
                  {l.cellules.map((c, j) => c === null ? <span key={j} role="cell" /> : (
                    <button key={j} role="cell" type="button"
                            className={`chaleur-cellule c${marche(c.part_optimal_pct, mini, maxi)} ${c === actif ? "choisie" : ""} ${c.est_optimal ? "optimale" : ""}`}
                            title={`${fmt(l.inclinaison)}°, ${c.orientation} : ${fmt(c.e_an_kwh_kwc)} kWh/kWc/an`}
                            onClick={() => setChoix({ inclinaison: l.inclinaison, orientation: ORIENTATIONS[j] })}>
                      {fmt(c.part_optimal_pct)} %
                    </button>
                  ))}
                </div>
              ))}
            </div>
            <div className="echelle" aria-hidden="true">
              <span>{fmt(mini)} %</span>
              <span className="echelle-barre" />
              <span>{fmt(maxi)} %</span>
            </div>
            <p className="note">
              Cliquer sur une case pour la choisir ; cadre épais : pente optimale plein sud.
              {facade && est30 && ` À ${donnees.ville}, une façade verticale orientée sud garde ${fmt(facade.part_optimal_pct)} % de
              l'optimum, une toiture inclinée à 30° vers l'est ${fmt(est30.part_optimal_pct)} %.`}
            </p>
          </div>
          <div>
            <h3>Votre toiture</h3>
            <div className="calculateur">
              <label>Puissance (kWc)
                <input type="text" inputMode="decimal" value={kwc} placeholder="ex. 3" onChange={(e) => setKwc(e.target.value)} />
              </label>
              {actif && (
                <div className="calcul-resultat">
                  <span className="tuile-libelle">{fmt(actif.inclinaison)}°, {actif.orientation}</span>
                  <span className="tuile-valeur">{fmt(actif.e_an_kwh_kwc * puissance)} kWh/an</span>
                  <span className="tuile-note">
                    {fmt(actif.part_optimal_pct)} % de l'optimum{opt && !actif.est_optimal ? ` (${fmt(opt.e_an_kwh_kwc * puissance)} kWh/an)` : ""}
                  </span>
                </div>
              )}
            </div>
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={mensuel} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--grille)" vertical={false} />
                <XAxis dataKey="mois" tickLine={false} stroke="var(--axe)" tick={{ fill: "var(--encre-attenuee)", fontSize: 11 }} />
                <YAxis width={44} tickLine={false} axisLine={false} tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} />
                <Tooltip cursor={{ fill: "var(--grille)", opacity: 0.5 }} content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <Infobulle titre={String(label)} lignes={[{ nom: "production du mois", couleur: "var(--serie-1)",
                      valeur: `${fmt(Number(payload[0].value))} kWh` }]} />
                  ) : null} />
                <Bar dataKey="valeur" fill="var(--serie-1)" radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
            <p className="note">Production mensuelle moyenne (kWh) pour {fmt(puissance, 1)} kWc, pertes système de 14 %.</p>
          </div>
        </div>
      )}
    </section>
  );
}
