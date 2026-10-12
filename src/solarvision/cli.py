"""Point d'entrée unique : python -m solarvision.cli <commande>.

Chaque commande correspond à une étape du pipeline. L'option --fast limite le travail à trois
villes (une par pays) et écrit dans data/fast/, pour les essais et l'intégration continue.
"""
from __future__ import annotations

import typer

from solarvision.config import DATA, load_params, select_cities

app = typer.Typer(add_completion=False, no_args_is_help=True, help="SolarVision v2 - pipeline de bout en bout.")


def _cities(fast: bool, cities: str | None):
    return select_cities(fast=fast, only=cities.split(",") if cities else None)


@app.command()
def ingest(
    fast: bool = typer.Option(False, "--fast", help="3 villes (une par pays), sorties dans data/fast/."),
    retry_failed: bool = typer.Option(False, "--retry-failed", help="Ne traite que les villes de data/failures.json."),
    reprocess: bool = typer.Option(False, "--reprocess", help="Reconstruit les tables depuis le cache, sans réseau."),
    quality_only: bool = typer.Option(False, "--quality-only", help="Régénère seulement les rapports de qualité."),
    cities: str = typer.Option(None, "--cities", help="Liste d'identifiants séparés par des virgules."),
) -> None:
    """Télécharge les sources manquantes, puis construit les tables journalières et le manifeste."""
    from solarvision.data import ingest as ing
    from solarvision.data import process

    selected = _cities(fast, cities)
    if retry_failed:
        failed = set(ing.failed_city_ids())
        selected = [c for c in selected if c.id in failed]
        typer.echo(f"Reprise des villes en échec : {[c.id for c in selected]}")
    out = DATA / "fast" if fast else DATA
    if not (reprocess or quality_only):
        ing.run_downloads(selected)
    summary = process.process_all(selected, out)
    if len(summary):
        typer.echo(summary[["ville", "lignes", "jours_imputes", "manquants_pct", "statut"]].to_string(index=False))
    missing = [c.id for c in selected if not ing.is_complete(c)]
    if missing:
        typer.echo(f"Villes incomplètes (non traitées, jamais simulées) : {missing}")


@app.command()
def features(
    fast: bool = typer.Option(False, "--fast", help="Panel des 3 villes rapides, dans data/fast/."),
    allow_partial: bool = typer.Option(False, "--allow-partial", help="Accepte un panel sans toutes les villes."),
) -> None:
    """Construit le panel de modélisation, les découpages 90/10 et la liste des villes manquantes."""
    from solarvision.features import panel as pm

    root = DATA / "fast" if fast else DATA
    panel = pm.build_panel(root, allow_partial=allow_partial, cities=select_cities(fast=fast))
    splits = pm.load_splits(root)
    typer.echo(f"Panel : {len(panel)} lignes, {panel.shape[1]} colonnes, {panel['ville'].nunique()} villes -> {root / 'processed'}")
    first = next(iter(splits.values()))
    typer.echo(f"Découpage : {first['n_train']} jours d'apprentissage (jusqu'au {first['train_fin']}), {first['n_test']} jours de test")


@app.command()
def train(
    fast: bool = typer.Option(False, "--fast", help="3 villes, sorties dans reports/fast/."),
    force: bool = typer.Option(False, "--force", help="Recalcule même si les prévisions existent."),
    workers: int = typer.Option(8, "--workers", help="Nombre de villes traitées en parallèle."),
    cities: str = typer.Option(None, "--cities", help="Liste d'identifiants séparés par des virgules."),
    sensitivity: bool = typer.Option(False, "--sensitivity", help="Ajoute l'analyse de sensibilité aux jours imputés."),
) -> None:
    """Entraîne les modèles classiques et enregistre leurs prévisions, origine par origine."""
    from solarvision.features import panel as pm
    from solarvision.models import train as tr

    available = set(pm.load_splits(tr.data_dir(fast)))
    selected = [c.id for c in _cities(fast, cities) if c.id in available]
    results = tr.train_all(selected, fast=fast, force=force, workers=workers)
    failed = [r["ville"] for r in results if str(r["statut"]).startswith("échec")]
    typer.echo(f"{len(results) - len(failed)} ville(s) traitée(s), {len(failed)} en échec {failed if failed else ''}")
    if sensitivity:
        subset = [c for c in load_params()["fast_cities"] if c in available]
        typer.echo(tr.sensitivity_to_imputed_days(subset, fast=fast).round(4).to_string(index=False))


@app.command()
def deep(
    fast: bool = typer.Option(False, "--fast", help="3 villes, 3 époques : vérifie la chaîne, pas la performance."),
    force: bool = typer.Option(False, "--force", help="Recalcule même si les prévisions existent."),
    workers: int = typer.Option(6, "--workers", help="Nombre de villes entraînées en parallèle."),
    cities: str = typer.Option(None, "--cities", help="Liste d'identifiants séparés par des virgules."),
    walk_forward: str = typer.Option(None, "--walk-forward", help="Ville de la validation glissante (ex. tunis)."),
    skip_global: bool = typer.Option(False, "--skip-global", help="N'entraîne pas le LSTM global."),
) -> None:
    """Entraîne LSTM et GRU par ville (ex ante et ex post), puis le LSTM global."""
    import time
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from solarvision.features import panel as pm
    from solarvision.models import deep as dp
    from solarvision.models import train as tr

    available = set(pm.load_splits(tr.data_dir(fast)))
    selected = [c.id for c in _cities(fast, cities) if c.id in available]
    if walk_forward:
        table = dp.walk_forward(walk_forward, fast=fast)
        typer.echo(table.groupby(["fenetre", "taille_cachee", "dropout"])[["rmse_validation", "rmse_climatologie"]]
                   .agg(["mean", "std"]).round(4).to_string())
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(selected)))) as pool:
        futures = {pool.submit(dp.run_city, c, fast, force): c for c in selected}
        for future in as_completed(futures):
            try:
                info = future.result()
            except Exception as err:                       # noqa: BLE001
                info = {"ville": futures[future], "statut": f"échec : {err}"}
            typer.echo(f"{time.strftime('%H:%M:%S')} {info['ville']:12s} {info['statut']} {info.get('duree_s', '')}")
    if not skip_global:
        typer.echo(f"LSTM global : {dp.run_global(selected, fast=fast, force=force)}")
    typer.echo(f"Courbes de perte : {dp.collect_curves(fast)}")


@app.command()
def evaluate(fast: bool = typer.Option(False, "--fast", help="Évalue les prévisions de reports/fast/.")) -> None:
    """Calcule métriques, tests de Diebold-Mariano (HLN, Holm) et synthèse par ville."""
    from solarvision.evaluation import evaluate as ev
    from solarvision.models import train as tr

    tables = ev.run(tr.reports_dir(fast))
    wide = tables["metrics_wide"]
    view = wide[(wide["horizon"] == "tous")].pivot_table(index=["ville", "technologie"], columns="modele", values="RMSE")
    typer.echo(view.round(4).to_string())
    typer.echo(tables["synthese_ville"][["ville", "meilleur_modele_ex_ante", "rmse_meilleur", "rmse_climatologie",
                                         "gain_vs_climatologie_pct"]].round(4).to_string(index=False))


@app.command()
def recommend(fast: bool = typer.Option(False, "--fast", help="Sur les 3 villes rapides."),
              orientations: bool = typer.Option(False, "--orientations", help="Ajoute l'analyse des orientations (appels PVGIS légers).")) -> None:
    """Calcule la fiabilité de chaque technologie par ville et recommande la plus fiable, avec son incertitude."""
    import pandas as pd

    from solarvision.evaluation import evaluate as ev
    from solarvision.features import panel as pm
    from solarvision.models import train as tr
    from solarvision.recommender import model, reliability

    reports = tr.reports_dir(fast)
    panel = pm.load_panel(tr.data_dir(fast))
    wide = pd.read_csv(reports / "metrics_wide.csv", dtype={"horizon": str})
    tables = reliability.compute(panel, wide, ev.load_forecasts(reports), reports)
    typer.echo(tables["recommendation"][["ville", "technologie_recommandee", "score", "deuxieme_choix", "ecart_score",
                                         "probabilite_meilleure", "robustesse_poids", "ex_aequo"]].round(3).to_string(index=False))
    loco = model.leave_one_city_out(model.city_features(panel), tables["recommendation"], reports)
    typer.echo(loco["summary"].round(1).to_string(index=False))
    if orientations:
        from solarvision.recommender import orientations as orient

        table = orient.run(tables["recommendation"], reports)
        typer.echo(table[["ville", "technologie", "rendement_sud_kwh_kwc", "ecart_est_ouest_pct", "azimut_optimal_deg",
                          "gain_optimal_pct"]].round(2).to_string(index=False))


@app.command()
def economics(fast: bool = typer.Option(False, "--fast", help="Sur les 3 villes rapides.")) -> None:
    """Simule les bénéfices économiques (Monte-Carlo) ; toutes les hypothèses sont à vérifier (TODO_VERIFY)."""
    import pandas as pd

    from solarvision.economics import simulate
    from solarvision.features import panel as pm
    from solarvision.models import train as tr

    reports = tr.reports_dir(fast)
    metrics = reports / "metrics_wide.csv"
    tables = simulate.run(pm.load_panel(tr.data_dir(fast)), reports,
                          pd.read_csv(metrics, dtype={"horizon": str}) if metrics.exists() else None)
    typer.echo("Hypothèses non vérifiées (TODO_VERIFY) : résultats indicatifs, pas un conseil financier.")
    typer.echo(tables["ranking"][["ville", "meilleure_technologie_van", "van_p10", "van_p50", "van_p90", "temps_retour_p50",
                                  "probabilite_premiere_devant", "ecart_non_concluant"]].round(2).to_string(index=False))


def _registry(fast: bool) -> None:
    """Le mode rapide a son propre registre : il ne doit jamais remplacer le modèle de l'étude complète."""
    from solarvision.config import MODELS
    from solarvision.mlops import registry

    if fast:
        registry.use(MODELS / "registry_fast")


@app.command()
def register(fast: bool = typer.Option(False, "--fast", help="Registre du mode rapide (models/registry_fast).")) -> None:
    """Enregistre les modèles candidats, puis promeut le meilleur si la règle de promotion le permet."""
    from solarvision.mlops import candidates

    _registry(fast)
    for result in candidates.register_and_promote(fast):
        typer.echo(" | ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in result.items()))


@app.command()
def rollback(fast: bool = typer.Option(False, "--fast")) -> None:
    """Revient à la version précédemment en production."""
    from solarvision.mlops import registry

    _registry(fast)
    pointer = registry.rollback()
    typer.echo(f"Production : {pointer['nom']} {pointer['version']} (remplace {pointer['remplace']['nom']} {pointer['remplace']['version']})")


@app.command()
def monitor(fast: bool = typer.Option(False, "--fast")) -> None:
    """Mesure la dérive des données et l'erreur glissante du modèle en production."""
    import json

    from solarvision.evaluation import evaluate as ev
    from solarvision.features import panel as pm
    from solarvision.mlops import registry
    from solarvision.models import train as tr
    from solarvision.monitoring import drift

    _registry(fast)
    active = registry.current()
    # Sans modèle en production, on suit le modèle statistique : le suivi ne doit pas dépendre d'une promotion.
    model = active["nom"] if active else "arima_fourier"
    root, reports = tr.data_dir(fast), tr.reports_dir(fast)
    summary = drift.run(pm.load_panel(root), pm.load_splits(root), ev.load_forecasts(reports), model, reports)
    typer.echo(json.dumps({k: summary[k] for k in ("modele_suivi", "derive", "part_des_jours_en_alerte_erreur_pct",
                                                    "villes_en_alerte_erreur_en_fin_de_periode")}, ensure_ascii=False, indent=2))


@app.command()
def serve(fast: bool = typer.Option(False, "--fast", help="Sert les 3 villes rapides."),
          host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(8001, "--port")) -> None:
    """Lance l'API et l'application multi-pages (documentation de l'API sur /docs)."""
    import os

    import uvicorn

    if fast:
        os.environ["SOLARVISION_FAST"] = "1"
    uvicorn.run("solarvision.serving.api:app", host=host, port=port)


@app.command()
def pipeline(fast: bool = typer.Option(False, "--fast", help="3 villes, peu d'époques : parcours complet en quelques minutes."),
             workers: int = typer.Option(8, "--workers")) -> None:
    """Enchaîne toutes les étapes dans l'ordre et s'arrête à la première qui échoue."""
    import subprocess
    import sys
    import time

    flag = ["--fast"] if fast else []
    steps = [["ingest", *flag], ["features", *flag, *([] if fast else ["--allow-partial"])],
             ["train", *flag, "--workers", str(workers), "--sensitivity"], ["deep", *flag], ["evaluate", *flag],
             ["recommend", *flag], ["economics", *flag], ["register", *flag], ["monitor", *flag]]
    for step in steps:
        t0 = time.time()
        typer.echo(f"=== {' '.join(step)}")
        code = subprocess.run([sys.executable, "-m", "solarvision.cli", *step], check=False).returncode
        if code != 0:
            typer.echo(f"Étape en échec : {' '.join(step)} (code {code})")
            raise typer.Exit(code)
        typer.echo(f"    terminé en {time.time() - t0:.0f} s")


@app.command()
def report(fast: bool = typer.Option(False, "--fast", help="Rapport sur les 3 villes rapides.")) -> None:
    """Génère le rapport (Word et PDF) à partir des fichiers produits par le pipeline."""
    from solarvision.reporting import report as rp

    _registry(fast)
    for kind, path in rp.build(fast).items():
        typer.echo(f"{kind} : {path}")


@app.command(name="llm-pack")
def llm_pack(fast: bool = typer.Option(False, "--fast"), city: str = typer.Option("tunis", "--city")) -> None:
    """Prépare docs/llm/ : statistiques et prompts générés, gabarits vides pour le travail de l'étudiant."""
    import pandas as pd

    from solarvision.features import panel as pm
    from solarvision.models import train as tr
    from solarvision.reporting import exploration
    from solarvision.reporting import llm_pack as lp

    root, reports = tr.data_dir(fast), tr.reports_dir(fast)
    stats = exploration.run(pm.load_panel(root), pm.load_splits(root), reports)
    for line in lp.build(stats, pd.read_csv(reports / "metrics_wide.csv", dtype={"horizon": str}), city):
        typer.echo(line)


@app.command()
def status() -> None:
    """État du cache : sources complètes ou non, ville par ville."""
    from solarvision.data import ingest as ing

    for city in select_cities():
        s = ing.source_status(city)
        typer.echo(f"{city.id:12s} {city.code_pays}  " + "  ".join(f"{k}={'oui' if v else 'non'}" for k, v in s.items())
                   + (f"  (reste {len(ing.pending_series(city))} appels PVGIS)" if not s["pvgis"] else ""))


if __name__ == "__main__":
    app()
