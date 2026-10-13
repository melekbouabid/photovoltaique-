"""Graphiques SVG des pages de l'application.

Règles suivies : un seul axe par graphique, marques fines, grille discrète, texte à l'encre (jamais à la
couleur de la série), couleurs attribuées à l'entité dans un ordre fixe (variables CSS --series-1..3),
légende dès qu'il y a deux séries, étiquettes directes, et une infobulle par marque (balise <title>).
Chaque graphique est accompagné d'un tableau dans la page.
"""
from __future__ import annotations

from html import escape

# Couleur par entité, toujours la même d'une page à l'autre.
ROLE_BY_ENTITY = {"crystSi": 1, "CIS": 2, "CdTe": 3, "France": 1, "Tunisie": 2, "Espagne": 3}


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def legend(entries: list[tuple[str, int]]) -> str:
    """Légende : pastille colorée, libellé à l'encre."""
    items = "".join(f'<span class="legend-item"><span class="swatch" style="background:var(--series-{role})"></span>{escape(name)}</span>'
                    for name, role in entries)
    return f'<div class="legend">{items}</div>'


def bar_chart(rows: list[tuple[str, float]], unit: str, role: int = 1, digits: int = 2, width: int = 640,
              roles: list[int] | None = None) -> str:
    """Barres horizontales triées par l'appelant, valeur écrite au bout de chaque barre."""
    if not rows:
        return ""
    label_w, value_w, bar_h, gap = 150, 90, 14, 8
    top = max(v for _, v in rows) or 1.0
    scale = (width - label_w - value_w) / top
    height = len(rows) * (bar_h + gap) + gap
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Graphique en barres ({escape(unit)})">']
    parts.append(f'<line x1="{label_w}" y1="0" x2="{label_w}" y2="{height}" class="axis"/>')
    for i, (label, value) in enumerate(rows):
        y, w = gap + i * (bar_h + gap), max(value * scale, 1)
        color = roles[i] if roles else role
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h - 3}" class="tick" text-anchor="end">{escape(label)}</text>')
        # Extrémité arrondie côté valeur seulement : la barre reste ancrée à l'axe.
        parts.append(f'<path d="M{label_w},{y} h{w - 4:.1f} a4,4 0 0 1 4,4 v{bar_h - 8} a4,4 0 0 1 -4,4 h-{w - 4:.1f} z" '
                     f'fill="var(--series-{color})"><title>{escape(label)} : {_fmt(value, digits)} {escape(unit)}</title></path>')
        parts.append(f'<text x="{label_w + w + 6:.1f}" y="{y + bar_h - 3}" class="value">{_fmt(value, digits)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def forecast_chart(history: list[dict], forecasts: list[dict], unit: str, width: int = 720, height: int = 300) -> str:
    """Historique observé, prévision avec son intervalle, normale saisonnière et observation réelle si elle existe."""
    left, right, top, bottom = 48, 16, 14, 34
    dates = [p["date"] for p in history] + [p["date"] for p in forecasts]
    values = [p["observation"] for p in history] + [v for p in forecasts for v in (p["borne_haute"], p["observation"], p["normale"])]
    y_max = max(values) * 1.08 or 1.0
    x = lambda i: left + i * (width - left - right) / max(len(dates) - 1, 1)                  # noqa: E731
    y = lambda v: top + (1 - v / y_max) * (height - top - bottom)                             # noqa: E731
    n = len(history)
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Prévision à 7 jours ({escape(unit)})">']
    for k in range(5):
        v = y_max * k / 4
        parts.append(f'<line x1="{left}" y1="{y(v):.1f}" x2="{width - right}" y2="{y(v):.1f}" class="grid"/>'
                     f'<text x="{left - 6}" y="{y(v) + 4:.1f}" class="tick" text-anchor="end">{_fmt(v, 1)}</text>')
    for i in range(0, len(dates), max(1, len(dates) // 7)):
        parts.append(f'<text x="{x(i):.1f}" y="{height - 12}" class="tick" text-anchor="middle">{dates[i][8:]}/{dates[i][5:7]}</text>')
    band = " ".join(f"{x(n + i):.1f},{y(p['borne_haute']):.1f}" for i, p in enumerate(forecasts)) + " " + \
        " ".join(f"{x(n + i):.1f},{y(p['borne_basse']):.1f}" for i, p in reversed(list(enumerate(forecasts))))
    parts.append(f'<polygon points="{band}" class="band"><title>Intervalle de prévision à 95 %</title></polygon>')
    line = lambda pts, cls: f'<polyline points="{" ".join(pts)}" class="{cls}"/>'             # noqa: E731
    parts.append(line([f"{x(n + i):.1f},{y(p['normale']):.1f}" for i, p in enumerate(forecasts)], "line normal"))
    observed = [f"{x(i):.1f},{y(p['observation']):.1f}" for i, p in enumerate(history)] + \
        [f"{x(n + i):.1f},{y(p['observation']):.1f}" for i, p in enumerate(forecasts)]
    parts.append(line(observed, "line observed"))
    anchor = [f"{x(n - 1):.1f},{y(history[-1]['observation']):.1f}"]
    parts.append(line(anchor + [f"{x(n + i):.1f},{y(p['prevision']):.1f}" for i, p in enumerate(forecasts)], "line forecast"))
    for i, p in enumerate(forecasts):
        parts.append(f'<circle cx="{x(n + i):.1f}" cy="{y(p["prevision"]):.1f}" r="4" class="dot forecast">'
                     f'<title>{p["date"]} (J+{p["horizon"]}) : prévu {_fmt(p["prevision"])}, intervalle {_fmt(p["borne_basse"])} à '
                     f'{_fmt(p["borne_haute"])}, observé {_fmt(p["observation"])} {escape(unit)}</title></circle>')
    parts.append(f'<line x1="{x(n - 1):.1f}" y1="{top}" x2="{x(n - 1):.1f}" y2="{height - bottom}" class="marker"/>'
                 f'<text x="{x(n - 1) + 5:.1f}" y="{top + 10}" class="tick">date d\'émission</text></svg>')
    return "".join(parts)


def map_chart(cities: list[dict], label_key: str | None = None, width: int = 640, height: int = 420) -> str:
    """Carte simple : chaque ville à sa longitude et sa latitude, colorée par pays."""
    if not cities:
        return ""
    lons, lats = [c["lon"] for c in cities], [c["lat"] for c in cities]
    pad = 40
    x = lambda lon: pad + (lon - min(lons)) / (max(lons) - min(lons) or 1) * (width - 2 * pad)      # noqa: E731
    y = lambda lat: height - pad - (lat - min(lats)) / (max(lats) - min(lats) or 1) * (height - 2 * pad)   # noqa: E731
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Carte des villes de l\'étude">']
    for c in cities:
        role = ROLE_BY_ENTITY.get(c["pays"], 1)
        extra = f" - {c[label_key]}" if label_key and c.get(label_key) else ""
        parts.append(f'<circle cx="{x(c["lon"]):.1f}" cy="{y(c["lat"]):.1f}" r="5" fill="var(--series-{role})" class="ring">'
                     f'<title>{escape(c["nom"])} ({escape(c["pays"])}){escape(extra)}</title></circle>'
                     f'<text x="{x(c["lon"]) + 8:.1f}" y="{y(c["lat"]) + 4:.1f}" class="tick">{escape(c["nom"])}</text>')
    parts.append("</svg>")
    return "".join(parts)
