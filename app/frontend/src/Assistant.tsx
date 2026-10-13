import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { api, ReponseAssistant } from "./api";

const EXEMPLES = [
  "Quelle ville produit le plus d'électricité solaire par kWc ?",
  "Combien produira une installation de 3 kWc à Tunis les 5 prochains jours ?",
  "Quelle est la production moyenne en décembre à Paris ?",
  "Quel est le meilleur modèle de prévision et quelle est son erreur ?",
  "Comment PVGIS calcule-t-il la production photovoltaïque ?",
  "Combien d'heures de lumière naturelle par jour en hiver à Tozeur ?",
];

interface Echange {
  id: number;
  question: string;
  reponse: ReponseAssistant | null;
  erreur: string | null;
}

/** Texte de la réponse : **gras** rendu, et citations [n] transformées en pastilles qui mènent à la source. */
function TexteReponse({ texte, idEchange }: { texte: string; idEchange: number }): ReactNode {
  const morceaux = texte.split(/(\*\*[^*]+\*\*|\[\d+\])/g);
  return morceaux.map((m, i) => {
    const cite = m.match(/^\[(\d+)\]$/);
    if (cite) {
      return (
        <a key={i} className="citation" href={`#source-${idEchange}-${cite[1]}`}
           onClick={() => document.getElementById(`source-${idEchange}-${cite[1]}`)?.closest("details")?.setAttribute("open", "")}
           aria-label={cite[1] === "0" ? "Source : prévision calculée" : `Source ${cite[1]}`}>{cite[1] === "0" ? "prévision" : cite[1]}</a>
      );
    }
    if (m.startsWith("**") && m.endsWith("**")) return <strong key={i}>{m.slice(2, -2)}</strong>;
    return <span key={i}>{m}</span>;
  });
}

/** Assistant RAG : recherche dans le corpus du projet puis réponse rédigée par le LLM (API Groq), avec sources. */
export function Assistant({ demande }: { demande: { contexte: string; cle: number } | null }) {
  const [question, setQuestion] = useState("");
  const [contexte, setContexte] = useState<string | null>(null);
  const [echanges, setEchanges] = useState<Echange[]>([]);
  const [enCours, setEnCours] = useState(false);
  const champ = useRef<HTMLTextAreaElement>(null);
  const compteur = useRef(0);

  // Une prévision transmise depuis le formulaire devient le contexte de la prochaine question.
  useEffect(() => {
    if (demande) {
      setContexte(demande.contexte);
      setQuestion("Que faut-il retenir de cette prévision et quelles en sont les limites ?");
      champ.current?.focus();
    }
  }, [demande]);

  async function envoyer(e?: FormEvent, q = question) {
    e?.preventDefault();
    const texte = q.trim();
    if (texte.length < 3 || enCours) return;
    const id = ++compteur.current;
    setEnCours(true);
    setQuestion("");
    setEchanges((h) => [{ id, question: texte, reponse: null, erreur: null }, ...h]);
    try {
      const r = await api.assistant(texte, contexte);
      setEchanges((h) => h.map((x) => (x.id === id ? { ...x, reponse: r } : x)));
    } catch (err) {
      setEchanges((h) => h.map((x) => (x.id === id ? { ...x, erreur: (err as Error).message } : x)));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="carte" id="assistant" aria-labelledby="titre-assistant">
      <div className="carte-entete">
        <div>
          <h2 id="titre-assistant">Assistant (RAG)</h2>
          <p className="sous-titre">
            Il cherche les passages utiles dans les fiches des jeux de données, les résultats de l'étude, le rapport, la méthode
            PVGIS et les articles du rapport SolarVision, puis un LLM (hébergé par Groq) rédige une réponse sourcée. Une question de prévision
            (« combien produira… ») déclenche aussi le modèle LSTM.
          </p>
        </div>
      </div>

      <form className="assistant-form" onSubmit={envoyer}>
        <label htmlFor="question" className="visuellement-cache">Votre question</label>
        <textarea id="question" ref={champ} rows={2} value={question} maxLength={500}
                  placeholder="Posez votre question, par exemple : quelle ville a le plus d'heures de lumière naturelle en hiver ?"
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(); } }} />
        <button type="submit" className="bouton-principal" disabled={enCours || question.trim().length < 3}>
          {enCours ? "Recherche…" : "Demander"}
        </button>
      </form>
      {contexte && (
        <p className="contexte">
          Contexte transmis : la prévision affichée plus haut.{" "}
          <button type="button" className="lien-bouton" onClick={() => setContexte(null)}>Retirer</button>
        </p>
      )}
      <div className="exemples" aria-label="Exemples de questions">
        {EXEMPLES.map((q) => (
          <button type="button" key={q} className="puce" disabled={enCours} onClick={() => envoyer(undefined, q)}>{q}</button>
        ))}
      </div>

      <div className="echanges" aria-live="polite">
        {echanges.map((x) => (
          <article className="echange" key={x.id}>
            <p className="bulle bulle-question">{x.question}</p>
            <div className="bulle bulle-reponse">
              {x.erreur && <p className="message erreur" role="alert">{x.erreur}</p>}
              {!x.reponse && !x.erreur && (
                <p className="message attente-points">Recherche des passages puis rédaction de la réponse</p>
              )}
              {x.reponse && (
                <>
                  <p className="echange-reponse"><TexteReponse texte={x.reponse.reponse} idEchange={x.id} /></p>
                  <p className="echange-meta">
                    <span className="etiquette">{x.reponse.mode.startsWith("llm") ? `rédigée par le LLM ${x.reponse.mode.slice(4)}` : "réponse extractive (LLM indisponible)"}</span>
                    {x.reponse.prevision && <span className="etiquette">prévision calculée : {x.reponse.prevision.ville}</span>}
                  </p>
                  <details>
                    <summary>Sources ({x.reponse.sources.length})</summary>
                    <ol className="sources">
                      {x.reponse.prevision && (
                        <li id={`source-${x.id}-0`} className="source-prevision">
                          <strong>[prévision] {x.reponse.prevision.nom_modele}, {x.reponse.prevision.ville}</strong>
                          <span className="source-extrait">{x.reponse.prevision.reponse}</span>
                        </li>
                      )}
                      {x.reponse.sources.map((s) => (
                        <li key={s.rang} id={`source-${x.id}-${s.rang}`}>
                          <strong>[{s.rang}] {s.titre}</strong>
                          <span className="source-chemin">{s.source}</span>
                          <span className="source-extrait">{s.extrait}…</span>
                        </li>
                      ))}
                    </ol>
                  </details>
                </>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
