import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Info } from "./api";
import { Infobulle, MOIS, Message, fmt, useChargement } from "./outils";

const MOIS_COMPLET = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
  "novembre", "décembre"];

/** Journée type d'un mois (2023, heure solaire) : éclairement lumineux et puissance PV, deux graphiques superposés. */
export function LumiereDuJour({ info }: { info: Info }) {
  const [site, setSite] = useState("tunis");
  const [mois, setMois] = useState(12);
  const { donnees, erreur, enCours } = useChargement(() => api.profilHoraire(site, mois), [site, mois]);
  const r = donnees?.resume;

  const graphique = (cle: "eclairement_klux" | "p_w_kwc", unite: string, couleur: string, seuil?: number) => (
    <ResponsiveContainer width="100%" height={170}>
      <AreaChart data={donnees?.heures ?? []} syncId="journee" margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grille)" vertical={false} />
        <XAxis dataKey="heure" tickLine={false} stroke="var(--axe)" interval={2} tickFormatter={(h) => `${h} h`}
               tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} />
        <YAxis width={44} tickLine={false} axisLine={false} tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} />
        <Tooltip cursor={{ stroke: "var(--axe)" }} content={({ active, payload, label }) => {
          if (!active || !payload?.length) return null;
          const x = payload[0].payload;
          return <Infobulle titre={`${label} h (heure solaire)`} lignes={[
            { nom: "éclairement lumineux", valeur: `${fmt(x.eclairement_klux, 1)} klux`, couleur: "var(--serie-2)" },
            { nom: "puissance d'1 kWc", valeur: `${fmt(x.p_w_kwc)} W`, couleur: "var(--serie-1)" },
            { nom: "jours au-dessus de 10 klux", valeur: `${fmt(100 * x.part_lumiere_suffisante)} %` },
            { nom: "nébulosité", valeur: x.nebulosite_pct === null ? "-" : `${fmt(x.nebulosite_pct)} %` },
          ]} />;
        }} />
        {seuil !== undefined && (
          <ReferenceLine y={seuil} stroke="var(--encre-secondaire)" strokeDasharray="4 3"
                         label={{ value: "10 klux : éclairage naturel suffisant", position: "insideTopLeft", fill: "var(--encre-secondaire)", fontSize: 11 }} />
        )}
        <Area dataKey={cle} type="monotone" stroke={couleur} strokeWidth={2} fill={couleur} fillOpacity={0.12}
              isAnimationActive={false} unit={unite} />
      </AreaChart>
    </ResponsiveContainer>
  );

  return (
    <section className="carte" id="lumiere" aria-labelledby="titre-lumiere">
      <div className="carte-entete">
        <div>
          <h2 id="titre-lumiere">Lumière du jour et éclairage naturel</h2>
          <p className="sous-titre">
            Journée moyenne d'un mois de 2023, heure par heure (heure solaire : midi quand le soleil est au plus haut).
            Au-dessus de 10 000 lux à l'extérieur, la lumière du jour suffit à éclairer un local courant.
          </p>
        </div>
        <label className="champ-compact">
          <span>Ville</span>
          <select value={site} onChange={(e) => setSite(e.target.value)}>
            {info.sites.map((s) => <option key={s.site} value={s.site}>{s.ville} ({s.pays})</option>)}
          </select>
        </label>
      </div>
      <div className="segments segments-mois" role="group" aria-label="Mois">
        {MOIS.map((m, i) => (
          <button key={m} className={mois === i + 1 ? "actif" : ""} aria-pressed={mois === i + 1} onClick={() => setMois(i + 1)}
                  title={MOIS_COMPLET[i]}>{m}</button>
        ))}
      </div>
      <Message erreur={erreur} enCours={enCours} vide={!donnees} />
      {donnees && r && (
        <div className={enCours ? "attente" : ""}>
          <div className="tuiles">
            <div className="tuile">
              <span className="tuile-libelle">Lumière naturelle suffisante</span>
              <span className="tuile-valeur">{fmt(r.heures_lumiere_10klux, 1)} h<span className="tuile-unite"> par jour</span></span>
              <span className="tuile-note">au-dessus de 10 klux, en {MOIS_COMPLET[mois - 1]}</span>
            </div>
            <div className="tuile">
              <span className="tuile-libelle">Jour solaire</span>
              <span className="tuile-valeur">
                {r.premiere_heure_jour === null ? "-" : `${r.premiere_heure_jour} h - ${(r.derniere_heure_jour ?? 0) + 1} h`}
              </span>
              <span className="tuile-note">heures avec du rayonnement (heure solaire)</span>
            </div>
            <div className="tuile">
              <span className="tuile-libelle">Éclairement maximal moyen</span>
              <span className="tuile-valeur">{fmt(r.eclairement_max_klux)}<span className="tuile-unite"> klux</span></span>
              <span className="tuile-note">vers midi solaire</span>
            </div>
            <div className="tuile">
              <span className="tuile-libelle">Production d'1 kWc</span>
              <span className="tuile-valeur">{fmt(r.production_jour_kwh_kwc, 2)}<span className="tuile-unite"> kWh par jour</span></span>
              <span className="tuile-note">somme des puissances horaires moyennes</span>
            </div>
          </div>
          <div className="deux-colonnes">
            <div>
              <h3>Éclairement lumineux horizontal (klux)</h3>
              {graphique("eclairement_klux", " klux", "var(--serie-2)", 10)}
            </div>
            <div>
              <h3>Puissance d'une installation de 1 kWc (W)</h3>
              {graphique("p_w_kwc", " W", "var(--serie-1)")}
            </div>
          </div>
          <p className="note">Source : jeu horaire 2023 (PVGIS et météo ERA5), éclairement lumineux calculé à partir des composantes
            directe et diffuse (100 et 125 lm/W).</p>
        </div>
      )}
    </section>
  );
}
