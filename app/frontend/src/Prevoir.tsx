import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, DemandePrevision, Info, Modele, Prevision, ValeurRecente, Variable } from "./api";
import { COULEUR_PAYS, Infobulle, Sparkline, dateChiffres, dateCourte, dateLongue, fmt, useChargement } from "./outils";

const N_RECENTS = 14;
const ORIGINE_DEFAUT = "2023-10-01";       // dans la période de test : les valeurs réelles sont connues
// Couleur attachée au modèle (jamais à son rang) : la comparaison garde les mêmes teintes.
const COULEUR_MODELE: Record<Modele, string> = {
  lstm: "var(--serie-1)", arima: "var(--serie-2)", persistance: "var(--serie-3)", climatologie: "var(--encre-attenuee)",
};
const ORDRE_MODELES: Modele[] = ["lstm", "arima", "climatologie", "persistance"];

interface Point {
  date: string;
  observe?: number;
  prevision?: number;
  normale?: number;
  bande?: [number, number];
  [cle: string]: number | string | [number, number] | undefined;
}

const nombre = (s: string) => Number(s.trim().replace(",", "."));

/** Formulaire de prévision (champs pré-remplis et modifiables) et réponse : graphique, chiffres clés, texte. */
export function Prevoir({ info, onQuestion }: { info: Info; onQuestion: (contexte: string) => void }) {
  const paysListe = [...new Set(info.sites.map((s) => s.pays))];
  const [pays, setPays] = useState("Tunisie");
  const [site, setSite] = useState("tunis");
  const [variable, setVariable] = useState<Variable>("pv_kwh_kwc");
  const [modele, setModele] = useState<Modele>("lstm");
  const [origine, setOrigine] = useState(ORIGINE_DEFAUT);
  const [horizon, setHorizon] = useState("7");
  const [kwc, setKwc] = useState("3");
  const [conso, setConso] = useState("");
  const [refs, setRefs] = useState<ValeurRecente[]>([]);
  const [saisies, setSaisies] = useState<string[]>(Array(N_RECENTS).fill(""));
  const [resultat, setResultat] = useState<Prevision | null>(null);
  const [comparer, setComparer] = useState(false);
  const [autres, setAutres] = useState<Partial<Record<Modele, Prevision>>>({});
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const premierCalcul = useRef(true);
  const derniere = useRef<DemandePrevision | null>(null);
  const profils = useChargement(() => api.profils(variable), [variable]);

  const estPV = variable === "pv_kwh_kwc";
  const puissance = estPV ? Math.max(nombre(kwc) || 1, 0.1) : 1;
  const uniteSaisie = estPV ? "kWh" : "kWh/m²";
  const sitesPays = info.sites.filter((s) => s.pays === pays);
  const horsDonnees = refs.some((r) => r.source !== "données PVGIS");
  const maxProfil = Math.max(1e-9, ...(profils.donnees ?? []).flatMap((p) => p.mensuel));

  // Valeurs récentes pré-remplies (données PVGIS, ou normale au-delà de 2023) à chaque changement de lieu,
  // de grandeur ou de date ; les saisies précédentes sont effacées car elles ne correspondent plus.
  useEffect(() => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(origine)) return;
    let actif = true;
    api.valeursRecentes(site, variable, origine, N_RECENTS)
      .then((v) => { if (actif) { setRefs(v); setSaisies(Array(N_RECENTS).fill("")); setErreur(null); } })
      .catch((e: Error) => actif && setErreur(e.message));
    return () => { actif = false; };
  }, [site, variable, origine]);

  // Comparaison : les trois autres modèles, avec exactement la même demande que la prévision affichée.
  async function chargerAutres(d: DemandePrevision) {
    const liste = ORDRE_MODELES.filter((m) => m !== d.modele);
    const res = await Promise.all(liste.map((m) => api.prevision({ ...d, modele: m }).catch(() => null)));
    setAutres(Object.fromEntries(liste.map((m, i) => [m, res[i]]).filter(([, p]) => p)) as Partial<Record<Modele, Prevision>>);
  }

  async function prevoir(e?: FormEvent) {
    e?.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      const modifie = saisies.some((s) => s.trim() !== "");
      const valeurs = modifie
        ? refs.map((r, i) => (saisies[i].trim() === "" ? r.valeur : nombre(saisies[i]) / puissance))
        : null;
      if (valeurs?.some((v) => !Number.isFinite(v) || v < 0)) {
        throw new Error("Les valeurs saisies doivent être des nombres positifs (virgule ou point décimal).");
      }
      const h = Math.min(Math.max(parseInt(horizon, 10) || 7, 1), info.horizon_max);
      setHorizon(String(h));
      const c = estPV && conso.trim() ? nombre(conso) : null;
      const d: DemandePrevision = {
        site, variable, modele, origine, horizon: h, puissance_kwc: puissance,
        conso_kwh_jour: c !== null && Number.isFinite(c) && c >= 0 ? c : null, valeurs_recentes: valeurs,
      };
      derniere.current = d;
      setResultat(await api.prevision(d));
      if (comparer) await chargerAutres(d);
      else setAutres({});
    } catch (err) {
      setErreur((err as Error).message);
    } finally {
      setEnCours(false);
    }
  }

  async function basculerComparaison() {
    const nouveau = !comparer;
    setComparer(nouveau);
    if (nouveau && derniere.current) await chargerAutres(derniere.current);
    if (!nouveau) setAutres({});
  }

  // Une première prévision est calculée dès que les valeurs de départ sont chargées.
  useEffect(() => {
    if (premierCalcul.current && refs.length) {
      premierCalcul.current = false;
      prevoir();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refs]);

  return (
    <section className="carte carte-prevoir" id="prevoir" aria-labelledby="titre-prevoir">
      <div className="carte-entete">
        <div>
          <h2 id="titre-prevoir">Prévoir la production ou l'éclairement</h2>
          <p className="sous-titre">
            Choisissez une ville, remplissez ou modifiez les champs, puis lancez la prévision. Les modèles sont entraînés sur
            2005-2022 (PVGIS) ; vous pouvez remplacer les derniers jours par les relevés de votre installation.
          </p>
        </div>
      </div>

      <div className="choix-villes" role="radiogroup" aria-label="Ville">
        {info.sites.map((s) => {
          const prof = profils.donnees?.find((p) => p.site === s.site);
          const choisi = s.site === site;
          return (
            <button type="button" key={s.site} role="radio" aria-checked={choisi}
                    className={`carte-ville ${choisi ? "choisie" : ""}`}
                    onClick={() => { setPays(s.pays); setSite(s.site); }}>
              <span className="carte-ville-pays"><span className="cle-ligne" style={{ background: COULEUR_PAYS[s.pays] }} />{s.pays}</span>
              <span className="carte-ville-nom">{s.ville}</span>
              {prof && <Sparkline valeurs={prof.mensuel} couleur={COULEUR_PAYS[s.pays]} max={maxProfil} />}
              <span className="carte-ville-chiffre">
                {/* Photovoltaïque : productible PVGIS (PVcalc), le chiffre du rapport et de l'en-tête de page. */}
                {estPV || !prof ? `${fmt(s.productible_kwh_kwc_an)} kWh/kWc/an` : `${fmt(prof.annuel)} kWh/m²/an`}
              </span>
            </button>
          );
        })}
      </div>

      <div className="prevoir-grille">
        <form className="formulaire" onSubmit={prevoir}>
          <fieldset>
            <legend>Lieu</legend>
            <div className="segments" role="group" aria-label="Pays">
              {paysListe.map((p) => (
                <button type="button" key={p} className={p === pays ? "actif" : ""} aria-pressed={p === pays}
                        onClick={() => { setPays(p); setSite(info.sites.find((s) => s.pays === p)!.site); }}>
                  {p}
                </button>
              ))}
            </div>
            <label htmlFor="ville">Ville</label>
            <select id="ville" value={site} onChange={(e) => setSite(e.target.value)}>
              {sitesPays.map((s) => (
                <option key={s.site} value={s.site}>{s.ville}</option>
              ))}
            </select>
          </fieldset>

          <fieldset>
            <legend>Grandeur et modèle</legend>
            <div className="segments" role="group" aria-label="Grandeur à prévoir">
              <button type="button" className={estPV ? "actif" : ""} aria-pressed={estPV}
                      onClick={() => setVariable("pv_kwh_kwc")}>Photovoltaïque</button>
              <button type="button" className={!estPV ? "actif" : ""} aria-pressed={!estPV}
                      onClick={() => setVariable("ghi_kwh_m2")}>Éclairement</button>
            </div>
            <label htmlFor="modele">Modèle</label>
            <select id="modele" value={modele} onChange={(e) => setModele(e.target.value as Modele)}>
              {(Object.entries(info.modeles) as [Modele, string][]).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </fieldset>

          <fieldset>
            <legend>Période</legend>
            <div className="champs-ligne">
              <div>
                <label htmlFor="origine">Dernier jour connu</label>
                <input id="origine" type="date" value={origine} min={info.origine_min} max={info.origine_max}
                       placeholder="aaaa-mm-jj" required onChange={(e) => setOrigine(e.target.value)} />
              </div>
              <div>
                <label htmlFor="horizon">Horizon (jours)</label>
                <input id="horizon" type="number" inputMode="numeric" min={1} max={info.horizon_max} value={horizon}
                       placeholder="7" onChange={(e) => setHorizon(e.target.value)} />
              </div>
            </div>
          </fieldset>

          {estPV && (
            <fieldset>
              <legend>Votre installation</legend>
              <div className="champs-ligne">
                <div>
                  <label htmlFor="kwc">Puissance (kWc)</label>
                  <input id="kwc" type="text" inputMode="decimal" value={kwc} placeholder="ex. 3"
                         onChange={(e) => setKwc(e.target.value)} />
                </div>
                <div>
                  <label htmlFor="conso">Consommation (kWh/jour)</label>
                  <input id="conso" type="text" inputMode="decimal" value={conso} placeholder="facultatif, ex. 12"
                         onChange={(e) => setConso(e.target.value)} />
                </div>
              </div>
              <p className="aide">Puissance ≈ surface utile de toiture (m²) × 0,2 (modules de rendement 20 %).</p>
            </fieldset>
          )}

          <fieldset>
            <legend>Derniers jours observés ({uniteSaisie}{estPV ? ` pour ${fmt(puissance, 1)} kWc` : "/jour"})</legend>
            <p className="aide">
              {horsDonnees
                ? "Au-delà du 31/12/2023, les valeurs proposées sont des normales saisonnières : saisissez vos relevés."
                : "Valeurs PVGIS en grisé : laissez vide pour les garder, ou saisissez votre propre relevé."}
            </p>
            <div className="grille-saisie">
              {refs.map((r, i) => (
                <label key={r.date} className="saisie">
                  <span>{dateChiffres(r.date)}</span>
                  <input type="text" inputMode="decimal" value={saisies[i]}
                         placeholder={fmt(r.valeur * puissance, estPV && puissance >= 10 ? 0 : 1)}
                         aria-label={`Valeur du ${dateLongue(r.date)}, ${uniteSaisie}`}
                         onChange={(e) => setSaisies((s) => s.map((x, j) => (j === i ? e.target.value : x)))} />
                </label>
              ))}
            </div>
            {saisies.some((s) => s.trim()) && (
              <button type="button" className="lien-bouton" onClick={() => setSaisies(Array(N_RECENTS).fill(""))}>
                Effacer mes saisies
              </button>
            )}
          </fieldset>

          <button type="submit" className="bouton-principal" disabled={enCours || !refs.length}>
            {enCours ? "Calcul en cours…" : "Prévoir"}
          </button>
          {erreur && <p className="message erreur" role="alert">{erreur}</p>}
        </form>

        <div className={`resultat ${enCours && resultat ? "attente" : ""}`} aria-live="polite">
          {resultat
            ? <Resultat p={resultat} autres={autres} comparer={comparer} onComparer={basculerComparaison}
                        nomsModeles={info.modeles} onQuestion={onQuestion} />
            : <p className="message">Préparation de la prévision…</p>}
        </div>
      </div>
    </section>
  );
}

function Resultat({ p, autres, comparer, onComparer, nomsModeles, onQuestion }: {
  p: Prevision; autres: Partial<Record<Modele, Prevision>>; comparer: boolean; onComparer: () => void;
  nomsModeles: Record<Modele, string>; onQuestion: (contexte: string) => void;
}) {
  const estPV = p.variable === "pv_kwh_kwc";
  const k = estPV ? p.puissance_kwc : 1;
  const unite = estPV ? "kWh" : "kWh/m²";
  const series = comparer ? ORDRE_MODELES.filter((m) => m === p.modele || autres[m]) : [p.modele];
  const prevOf = (m: Modele) => (m === p.modele ? p : autres[m]);
  const points: Point[] = [
    ...p.historique.map((h) => ({ date: h.date, observe: h.valeur * k })),
    ...p.previsions.map((x, i) => {
      const pt: Point = {
        date: x.date, prevision: x.prevision * k, normale: x.normale * k,
        observe: x.observe === null ? undefined : x.observe * k,
        bande: x.bas === null || x.haut === null ? undefined : ([x.bas * k, x.haut * k] as [number, number]),
      };
      for (const m of series) {
        const q = prevOf(m);
        if (q) pt[`m_${m}`] = q.previsions[i].prevision * k;
      }
      return pt;
    }),
  ];
  const ecart = p.ecart_normale_pct;
  const decimales = estPV && k >= 10 ? 0 : 1;

  return (
    <>
      <div className="reponse">
        <h3>Réponse</h3>
        <p>{p.reponse}</p>
        <button type="button" className="lien-bouton" onClick={() => onQuestion(p.reponse)}>
          Poser une question à l'assistant sur cette prévision
        </button>
      </div>

      <div className="tuiles">
        <div className="tuile">
          <span className="tuile-libelle">{estPV ? `Production prévue sur ${p.horizon} j` : "Irradiation moyenne prévue"}</span>
          <span className="tuile-valeur">
            {estPV ? `${fmt(p.total, decimales)} kWh` : `${fmt(p.total / p.horizon, 2)} kWh/m²`}
          </span>
          <span className="tuile-note">
            {estPV && p.total_bas !== null && p.total_haut !== null
              ? `fourchette ${fmt(p.total_bas, decimales)} à ${fmt(p.total_haut, decimales)} kWh`
              : estPV ? `${fmt(p.total / p.horizon, 1)} kWh par jour en moyenne` : "par jour"}
          </span>
        </div>
        <div className="tuile">
          <span className="tuile-libelle">Écart à la normale saisonnière</span>
          {Math.abs(ecart) < 1 ? (
            <span className="tuile-valeur">≈ 0 %</span>
          ) : (
            <span className={`tuile-valeur ${ecart > 0 ? "hausse" : "baisse"}`}>
              <span aria-hidden="true">{ecart > 0 ? "▲ " : "▼ "}</span>{ecart > 0 ? "+" : "−"}{fmt(Math.abs(ecart), 0)} %
            </span>
          )}
          <span className="tuile-note">normale 2005-2020 : {fmt(p.total_normale, estPV ? decimales : 1)} {unite}</span>
        </div>
        <div className="tuile">
          <span className="tuile-libelle">Erreur moyenne du modèle</span>
          <span className="tuile-valeur">
            {p.mae_test_modele === null ? "—" : `${fmt(p.mae_test_modele, 2)}`}
            <span className="tuile-unite"> {estPV ? "kWh/kWc/j" : "kWh/m²/j"}</span>
          </span>
          <span className="tuile-note">sur la période de test 2022-2023, à {p.ville}</span>
        </div>
        {p.mae_prevision !== null && (
          <div className="tuile">
            <span className="tuile-libelle">Erreur de cette prévision</span>
            <span className="tuile-valeur">{fmt(p.mae_prevision, 2)}<span className="tuile-unite"> {estPV ? "kWh/kWc/j" : "kWh/m²/j"}</span></span>
            <span className="tuile-note">
              {p.dans_apprentissage ? "jours vus à l'entraînement : erreur optimiste" : "comparée aux valeurs réelles PVGIS"}
            </span>
          </div>
        )}
      </div>

      <div className="barre-graphique">
        <ul className="legende" aria-label="Légende">
          <li><span className="cle-ligne" style={{ background: "var(--encre)" }} />Observé</li>
          {series.map((m) => (
            <li key={m}><span className="cle-ligne" style={{ background: COULEUR_MODELE[m] }} />{nomsModeles[m]}</li>
          ))}
          <li><span className="cle-bloc" style={{ background: "var(--serie-1-voile)" }} />Intervalle à 95 % ({nomsModeles[p.modele]})</li>
          {!comparer && <li><span className="cle-ligne" style={{ background: "var(--encre-attenuee)" }} />Normale saisonnière</li>}
        </ul>
        <label className="interrupteur">
          <input type="checkbox" checked={comparer} onChange={onComparer} />
          <span>Comparer les 4 modèles</span>
        </label>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grille)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={dateCourte} minTickGap={28} tickLine={false} stroke="var(--axe)"
                 tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} />
          <YAxis width={48} tickLine={false} axisLine={false} domain={[0, "auto"]}
                 tick={{ fill: "var(--encre-attenuee)", fontSize: 12 }} tickFormatter={(v) => fmt(v, v < 10 ? 1 : 0)} />
          <Tooltip cursor={{ stroke: "var(--axe)" }} content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const x = payload[0].payload as Point;
            const lignes = [];
            if (x.observe !== undefined) lignes.push({ nom: "observé", valeur: `${fmt(x.observe, 2)} ${unite}`, couleur: "var(--encre)" });
            for (const m of series) {
              const v = x[`m_${m}`] as number | undefined;
              if (v !== undefined) lignes.push({ nom: nomsModeles[m], valeur: `${fmt(v, 2)} ${unite}`, couleur: COULEUR_MODELE[m] });
            }
            if (x.bande) lignes.push({ nom: "intervalle à 95 %", valeur: `${fmt(x.bande[0], 1)} à ${fmt(x.bande[1], 1)}`, couleur: "var(--serie-1-voile)" });
            if (x.normale !== undefined && !comparer) lignes.push({ nom: "normale", valeur: `${fmt(x.normale, 2)} ${unite}`, couleur: "var(--encre-attenuee)" });
            return <Infobulle titre={dateLongue(String(label))} lignes={lignes} />;
          }} />
          <ReferenceLine x={p.origine} stroke="var(--axe)"
                         label={{ value: "origine", position: "insideTopRight", fill: "var(--encre-secondaire)", fontSize: 12 }} />
          <Area dataKey="bande" stroke="none" fill="var(--serie-1-voile)" isAnimationActive={false} activeDot={false} />
          {!comparer && <Line dataKey="normale" stroke="var(--encre-attenuee)" strokeWidth={1.5} dot={false} isAnimationActive={false} />}
          <Line dataKey="observe" stroke="var(--encre)" strokeWidth={2} isAnimationActive={false} connectNulls={false}
                dot={{ r: 3, fill: "var(--encre)", stroke: "var(--surface)", strokeWidth: 2 }} />
          {series.map((m) => (
            <Line key={m} dataKey={`m_${m}`} stroke={COULEUR_MODELE[m]} strokeWidth={2} isAnimationActive={false}
                  dot={{ r: m === p.modele ? 4 : 3, fill: COULEUR_MODELE[m], stroke: "var(--surface)", strokeWidth: 2 }} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {comparer && (
        <div className="tableau-defilant">
          <table>
            <caption>Les 4 modèles sur la même période ({unite}{estPV ? ` pour ${fmt(p.puissance_kwc, 1)} kWc` : ""})</caption>
            <thead>
              <tr><th>Modèle</th><th className="num">Total prévu</th><th className="num">Erreur de cette prévision</th>
                <th className="num">Erreur moyenne sur le test</th></tr>
            </thead>
            <tbody>
              {series.map((m) => {
                const q = prevOf(m)!;
                return (
                  <tr key={m}>
                    <td><span className="cle-ligne" style={{ background: COULEUR_MODELE[m], marginRight: 8 }} />{nomsModeles[m]}</td>
                    <td className="num">{estPV ? fmt(q.total, decimales) : fmt(q.total / q.horizon, 2)}</td>
                    <td className="num">{q.mae_prevision === null ? "—" : fmt(q.mae_prevision, 2)}</td>
                    <td className="num">{q.mae_test_modele === null ? "—" : fmt(q.mae_test_modele, 2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <details className="tableau-details">
        <summary>Tableau détaillé ({unite}{estPV ? ` pour ${fmt(p.puissance_kwc, 1)} kWc` : ""})</summary>
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Jour</th><th className="num">Prévision</th><th className="num">Intervalle à 95 %</th>
                <th className="num">Normale</th><th className="num">Observé</th>
              </tr>
            </thead>
            <tbody>
              {p.previsions.map((x) => (
                <tr key={x.date}>
                  <td>{dateLongue(x.date)}</td>
                  <td className="num">{fmt(x.prevision * k, 2)}</td>
                  <td className="num">{x.bas === null || x.haut === null ? "—" : `${fmt(x.bas * k, 2)} à ${fmt(x.haut * k, 2)}`}</td>
                  <td className="num">{fmt(x.normale * k, 2)}</td>
                  <td className="num">{x.observe === null ? "—" : fmt(x.observe * k, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
