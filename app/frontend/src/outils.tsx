import { useEffect, useState } from "react";

// Formats français : séparateur de milliers, virgule décimale.
const nf = (decimales: number) =>
  new Intl.NumberFormat("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
export const fmt = (v: number, decimales = 0) => nf(decimales).format(v);

const jourMois = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", timeZone: "UTC" });
const jourComplet = new Intl.DateTimeFormat("fr-FR", {
  weekday: "short", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
});
const jourNumerique = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", timeZone: "UTC" });
export const dateCourte = (iso: string) => jourMois.format(new Date(iso));
export const dateLongue = (iso: string) => jourComplet.format(new Date(iso));
export const dateChiffres = (iso: string) => jourNumerique.format(new Date(iso));
export const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

// Couleur attachée au pays (jamais à son rang) : trois premiers emplacements de la palette catégorielle,
// validés deux à deux pour les daltonismes, en clair comme en sombre (voir styles.css).
export const COULEUR_PAYS: Record<string, string> = {
  France: "var(--serie-1)", Tunisie: "var(--serie-2)", Espagne: "var(--serie-3)",
};

interface Etat<T> {
  donnees: T | null;
  erreur: string | null;
  enCours: boolean;
}

/** Charge une ressource. Pendant un rechargement, les données précédentes restent affichées. */
export function useChargement<T>(charger: () => Promise<T>, dependances: unknown[]): Etat<T> {
  const [etat, setEtat] = useState<Etat<T>>({ donnees: null, erreur: null, enCours: true });
  useEffect(() => {
    let actif = true;
    setEtat((e) => ({ ...e, enCours: true }));
    charger()
      .then((donnees) => actif && setEtat({ donnees, erreur: null, enCours: false }))
      .catch((err: Error) => actif && setEtat((e) => ({ donnees: e.donnees, erreur: err.message, enCours: false })));
    return () => {
      actif = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependances);
  return etat;
}

interface LigneInfobulle {
  nom: string;
  valeur: string;
  couleur?: string;
}

/** Infobulle commune : la valeur en évidence, le nom en retrait, une courte ligne de la couleur de la série. */
export function Infobulle({ titre, lignes }: { titre: string; lignes: LigneInfobulle[] }) {
  return (
    <div className="infobulle">
      <div className="infobulle-titre">{titre}</div>
      {lignes.map((l) => (
        <div className="infobulle-ligne" key={l.nom}>
          <span className="cle-ligne" style={{ background: l.couleur ?? "transparent" }} />
          <strong>{l.valeur}</strong>
          <span>{l.nom}</span>
        </div>
      ))}
    </div>
  );
}

export function Message({ erreur, enCours, vide }: { erreur: string | null; enCours: boolean; vide: boolean }) {
  if (erreur) return <p className="message erreur" role="alert">{erreur}</p>;
  if (enCours && vide) return <p className="message">Chargement…</p>;
  return null;
}

/** Courbe miniature (12 valeurs mensuelles) : une seule série, sans axe, pour comparer des formes. */
export function Sparkline({ valeurs, couleur, largeur = 96, hauteur = 28, max }: {
  valeurs: number[]; couleur: string; largeur?: number; hauteur?: number; max?: number;
}) {
  const haut = max ?? Math.max(...valeurs);
  const pts = valeurs.map((v, i) => [2 + (i * (largeur - 4)) / (valeurs.length - 1), hauteur - 2 - ((hauteur - 4) * v) / haut]);
  const chemin = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg width={largeur} height={hauteur} viewBox={`0 0 ${largeur} ${hauteur}`} aria-hidden="true" className="sparkline">
      <path d={`${chemin} L${largeur - 2},${hauteur - 2} L2,${hauteur - 2} Z`} fill={couleur} opacity="0.12" />
      <path d={chemin} fill="none" stroke={couleur} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** Rang (0 à 6) d'une valeur sur la rampe séquentielle bleue des cartes de chaleur (classes .c0 à .c6). */
export const marche = (v: number, mini: number, maxi: number) =>
  maxi <= mini ? 3 : Math.max(0, Math.min(6, Math.round((6 * (v - mini)) / (maxi - mini))));

type Theme = "auto" | "light" | "dark";
const LIBELLE_THEME: Record<Theme, string> = { auto: "Thème automatique", light: "Thème clair", dark: "Thème sombre" };

/** Bascule de thème (automatique, clair, sombre), mémorisée dans le navigateur quand c'est possible. */
export function BoutonTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem("theme") as Theme) || "auto"; } catch { return "auto"; }
  });
  useEffect(() => {
    if (theme === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch { /* stockage indisponible : thème non mémorisé */ }
  }, [theme]);
  const suivant: Record<Theme, Theme> = { auto: "light", light: "dark", dark: "auto" };
  return (
    <button type="button" className="bouton-theme" onClick={() => setTheme(suivant[theme])}
            aria-label={`${LIBELLE_THEME[theme]} (cliquer pour changer)`} title={LIBELLE_THEME[theme]}>
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
        {theme === "dark" ? (
          <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" fill="currentColor" />
        ) : theme === "light" ? (
          <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="4" fill="currentColor" />
            {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
              <line key={a} x1={12 + 7 * Math.cos((a * Math.PI) / 180)} y1={12 + 7 * Math.sin((a * Math.PI) / 180)}
                    x2={12 + 9.5 * Math.cos((a * Math.PI) / 180)} y2={12 + 9.5 * Math.sin((a * Math.PI) / 180)} />
            ))}
          </g>
        ) : (
          <g fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="8" />
            <path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" />
          </g>
        )}
      </svg>
    </button>
  );
}

/** Logo : un soleil stylisé (décoratif, non porteur de données). */
export function Soleil({ taille = 28 }: { taille?: number }) {
  const rayons = Array.from({ length: 8 }, (_, i) => (i * Math.PI) / 4);
  return (
    <svg width={taille} height={taille} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="6.5" fill="var(--soleil)" />
      {rayons.map((a) => (
        <line key={a} x1={16 + 9.5 * Math.cos(a)} y1={16 + 9.5 * Math.sin(a)} x2={16 + 13.5 * Math.cos(a)}
              y2={16 + 13.5 * Math.sin(a)} stroke="var(--soleil)" strokeWidth="2.4" strokeLinecap="round" />
      ))}
    </svg>
  );
}
