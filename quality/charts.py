"""Graphiques Plotly interactifs (survol, zoom, légende cliquable) aux couleurs du portail."""

from __future__ import annotations

import textwrap

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .config import COLORWAY, LEVEL_COLORS, PALETTE, SEQUENTIAL

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"

STATUS_COLORS = {
    "À jour": PALETTE["good"],
    "En retard": PALETTE["warning"],
    "Très en retard": PALETTE["bad"],
    "Non évaluable (fréquence irrégulière)": PALETTE["primary_soft"],
    "Non évaluable (fréquence non renseignée)": PALETTE["muted"],
    "Non évaluable (fréquence inconnue)": PALETTE["muted"],
    "Non évaluable (date inconnue)": "#9A99B5",
}
BEFORE_COLOR = PALETTE["primary_soft"]
AFTER_COLOR = PALETTE["primary"]


def style(fig: go.Figure, height: int = 380, title: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height,
        title=(
            dict(text=title, x=0.0, font=dict(size=15, color=PALETTE["primary"]))
            if title
            else None
        ),
        font=dict(family=FONT, size=12, color=PALETTE["text"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=20, t=55 if title else 20, b=10),
        colorway=COLORWAY,
        hoverlabel=dict(font_size=12),
        legend=dict(orientation="h", y=-0.18, x=0),
    )
    fig.update_xaxes(
        gridcolor=PALETTE["grid"], zeroline=False, linecolor=PALETTE["grid"]
    )
    fig.update_yaxes(
        gridcolor=PALETTE["grid"], zeroline=False, linecolor=PALETTE["grid"]
    )
    return fig


def _auto_height(n: int, per: int = 28, base: int = 90, min_h: int = 260) -> int:
    return max(min_h, per * n + base)


def _wrap(text: str, width: int = 60) -> str:
    return "<br>".join(textwrap.wrap(str(text), width)) if text else ""


# --------------------------------------------------------------------------- #
# Barres
# --------------------------------------------------------------------------- #
def bar(
    labels,
    values,
    title=None,
    horizontal=True,
    color=None,
    height=None,
    suffix="",
    xtitle=None,
    ytitle=None,
    customdata=None,
    hovertemplate=None,
):
    labels, values = [str(x) for x in labels], list(values)
    colors = (
        list(color)
        if isinstance(color, (list, tuple))
        else [color or PALETTE["primary_mid"]] * len(values)
    )
    texts = [
        (
            f"{v:g}{suffix}"
            if isinstance(v, (int, float, np.integer, np.floating))
            else str(v)
        )
        for v in values
    ]
    if horizontal:
        trace = go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=texts,
            textposition="outside",
            cliponaxis=False,
            customdata=customdata,
            hovertemplate=hovertemplate,
        )
    else:
        trace = go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=texts,
            textposition="outside",
            cliponaxis=False,
            customdata=customdata,
            hovertemplate=hovertemplate,
        )
    fig = go.Figure(trace)
    if horizontal:
        fig.update_yaxes(autorange="reversed", title=ytitle)
        fig.update_xaxes(title=xtitle)
    else:
        fig.update_xaxes(title=xtitle)
        fig.update_yaxes(title=ytitle)
    return style(
        fig, height or (_auto_height(len(labels)) if horizontal else 380), title
    )


def grouped_bar(
    labels,
    series: dict,
    title=None,
    horizontal=True,
    height=None,
    colors=None,
    xtitle=None,
    ytitle=None,
):
    """Plusieurs séries côte à côte (ex. Avant / Après normalisation)."""
    labels = [str(x) for x in labels]
    palette = colors or [BEFORE_COLOR, AFTER_COLOR, PALETTE["accent"]]
    fig = go.Figure()
    for i, (name, vals) in enumerate(series.items()):
        vals = list(vals)
        if horizontal:
            fig.add_trace(
                go.Bar(
                    name=name,
                    x=vals,
                    y=labels,
                    orientation="h",
                    marker_color=palette[i % len(palette)],
                    text=vals,
                    textposition="outside",
                    cliponaxis=False,
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    name=name,
                    x=labels,
                    y=vals,
                    marker_color=palette[i % len(palette)],
                    text=vals,
                    textposition="outside",
                    cliponaxis=False,
                )
            )
    fig.update_layout(barmode="group")
    if horizontal:
        fig.update_yaxes(autorange="reversed", title=ytitle)
        fig.update_xaxes(title=xtitle)
    else:
        fig.update_xaxes(title=xtitle)
        fig.update_yaxes(title=ytitle)
    h = height or (
        _auto_height(len(labels) * len(series), per=20) if horizontal else 400
    )
    return style(fig, h, title)


def stacked_bar(ct: pd.DataFrame, title=None, height=None, horizontal=False):
    """`ct` : index = catégories (axe), colonnes = séries empilées."""
    fig = go.Figure()
    for i, col in enumerate(ct.columns):
        if horizontal:
            fig.add_trace(
                go.Bar(
                    name=str(col),
                    y=[str(x) for x in ct.index],
                    x=ct[col],
                    orientation="h",
                    marker_color=COLORWAY[i % len(COLORWAY)],
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    name=str(col),
                    x=[str(x) for x in ct.index],
                    y=ct[col],
                    marker_color=COLORWAY[i % len(COLORWAY)],
                )
            )
    fig.update_layout(barmode="stack")
    if horizontal:
        fig.update_yaxes(autorange="reversed")
    return style(fig, height or 400, title)


def completeness_bar(comp: pd.DataFrame, height=None):
    """Taux de remplissage de chaque attribut, avec la description du schéma au survol."""
    comp = comp.sort_values("taux_completude", ascending=True)
    labels = [
        f"{c}{' *' if not d else ''}"
        for c, d in zip(comp["champ"], comp["dans_export"])
    ]
    colors = [
        (
            PALETTE["good"]
            if v >= 90
            else PALETTE["warning"] if v >= 50 else PALETTE["bad"]
        )
        for v in comp["taux_completude"]
    ]
    custom = np.column_stack(
        [
            comp["libelle"].astype(str),
            [_wrap(d, 60) for d in comp["description"]],
            comp["remplis"].astype(int),
            comp["total"].astype(int),
            comp["type"].astype(str),
        ]
    )
    fig = go.Figure(
        go.Bar(
            x=comp["taux_completude"],
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.1f} %" for v in comp["taux_completude"]],
            textposition="outside",
            cliponaxis=False,
            customdata=custom,
            hovertemplate=(
                "<b>%{y}</b> - %{customdata[0]} (%{customdata[4]})<br>"
                "%{x:.1f} % renseigné (%{customdata[2]} / %{customdata[3]})<br>"
                "<i>%{customdata[1]}</i><extra></extra>"
            ),
        )
    )
    fig.update_xaxes(range=[0, 112], title="% de jeux de données renseignés")
    return style(fig, height or _auto_height(len(comp), per=26, base=70))


# --------------------------------------------------------------------------- #
# Distributions
# --------------------------------------------------------------------------- #
def histogram(
    values,
    title=None,
    nbins=30,
    vlines=None,
    xtitle=None,
    ytitle="Jeux de données",
    color=None,
    height=340,
):
    vals = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    fig = go.Figure(
        go.Histogram(
            x=vals,
            nbinsx=nbins,
            marker_color=color or PALETTE["primary_mid"],
            marker_line_color="white",
            marker_line_width=1,
            hovertemplate="%{x}<br>%{y} jeux<extra></extra>",
        )
    )
    for x, label in vlines or []:
        fig.add_vline(
            x=x,
            line_dash="dash",
            line_color=PALETTE["accent"],
            annotation_text=label,
            annotation_position="top",
        )
    fig.update_xaxes(title=xtitle)
    fig.update_yaxes(title=ytitle)
    return style(fig, height, title)


def score_histogram(m: pd.DataFrame, title=None, height=340):
    fig = px.histogram(
        m,
        x="score_global",
        color="niveau_qualite",
        nbins=20,
        color_discrete_map=LEVEL_COLORS,
        category_orders={"niveau_qualite": list(LEVEL_COLORS)},
        labels={
            "score_global": "Score global",
            "niveau_qualite": "Niveau",
            "count": "Jeux",
        },
    )
    fig.update_layout(barmode="stack", bargap=0.05)
    fig.update_yaxes(title="Jeux de données")
    return style(fig, height, title)


def donut(labels, values, title=None, colors=None, height=340):
    fig = go.Figure(
        go.Pie(
            labels=[str(x) for x in labels],
            values=list(values),
            hole=0.55,
            marker=dict(colors=colors or COLORWAY, line=dict(color="white", width=2)),
            textinfo="percent",
            sort=False,
            hovertemplate="%{label}<br>%{value} jeux (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(legend=dict(orientation="v", y=0.5, x=1.02))
    return style(fig, height, title)


def heatmap(ct: pd.DataFrame, title=None, height=None, xtitle=None, ytitle=None):
    n = len(SEQUENTIAL) - 1
    scale = [[i / n, c] for i, c in enumerate(SEQUENTIAL)]
    fig = go.Figure(
        go.Heatmap(
            z=ct.values,
            x=[str(c) for c in ct.columns],
            y=[str(i) for i in ct.index],
            colorscale=scale,
            text=ct.values,
            texttemplate="%{text}",
            showscale=False,
            xgap=2,
            ygap=2,
            hovertemplate="%{y}<br>%{x}<br><b>%{z}</b> jeux<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed", title=ytitle)
    fig.update_xaxes(title=xtitle, side="top")
    return style(fig, height or _auto_height(len(ct), per=34, base=110), title)


# --------------------------------------------------------------------------- #
# Nuages de points / autres
# --------------------------------------------------------------------------- #
def title_words_scatter(m: pd.DataFrame, height=360):
    fig = px.scatter(
        m,
        x="titre_nb_mots",
        y="titre_nb_mots_porteurs",
        hover_name="titre",
        color_discrete_sequence=[PALETTE["primary_mid"]],
        opacity=0.6,
        labels={
            "titre_nb_mots": "Mots du titre",
            "titre_nb_mots_porteurs": "dont mots porteurs de sens",
        },
    )
    mx = float(max(1, m["titre_nb_mots"].max()))
    fig.add_trace(
        go.Scatter(
            x=[0, mx],
            y=[0, mx],
            mode="lines",
            name="100 % porteurs",
            line=dict(color=PALETTE["accent"], dash="dot"),
            hoverinfo="skip",
        )
    )
    return style(fig, height)


def freshness_strip(m: pd.DataFrame, params: dict, order: list[str], height=460):
    d = m.dropna(subset=["jours_depuis_maj_donnees"]).copy()
    d["jours"] = d["jours_depuis_maj_donnees"].clip(lower=1)
    fig = px.strip(
        d,
        x="frequence_libelle",
        y="jours",
        color="statut_fraicheur",
        hover_name="titre",
        color_discrete_map=STATUS_COLORS,
        category_orders={"frequence_libelle": order},
        hover_data={
            "jours": True,
            "frequence_libelle": False,
            "statut_fraicheur": True,
        },
        labels={
            "jours": "Jours depuis la dernière mise à jour",
            "frequence_libelle": "Fréquence déclarée",
            "statut_fraicheur": "Statut",
        },
    )
    thr = (
        m.dropna(subset=["frequence_jours_attendus"])
        .groupby("frequence_libelle")["frequence_jours_attendus"]
        .first()
        * params["due_tolerance"]
        + params["due_grace_days"]
    )
    if len(thr):
        fig.add_trace(
            go.Scatter(
                x=list(thr.index),
                y=list(thr.values),
                mode="markers",
                name="Seuil de retard",
                marker=dict(
                    symbol="line-ew",
                    size=34,
                    line=dict(width=3, color=PALETTE["primary"]),
                ),
                hovertemplate="Seuil : %{y:.0f} jours<extra></extra>",
            )
        )
    fig.update_yaxes(
        type="log", title="Jours depuis la dernière mise à jour (échelle log)"
    )
    fig.update_xaxes(title=None)
    return style(fig, height)


def radar(values: dict, title=None, height=340):
    labels, vals = list(values.keys()), [float(v) for v in values.values()]
    fig = go.Figure(
        go.Scatterpolar(
            r=vals + vals[:1],
            theta=labels + labels[:1],
            fill="toself",
            line=dict(color=PALETTE["primary"], width=2),
            fillcolor="rgba(90,82,199,0.25)",
            hovertemplate="%{theta}<br><b>%{r:.0f}</b>/100<extra></extra>",
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, 100], gridcolor=PALETTE["grid"]),
            angularaxis=dict(gridcolor=PALETTE["grid"]),
        ),
        showlegend=False,
    )
    return style(fig, height, title)


def scatter_native(m: pd.DataFrame, height=380):
    d = m.dropna(subset=["score_natif_data_fair"])
    fig = px.scatter(
        d,
        x="score_natif_data_fair",
        y="score_global",
        color="niveau_qualite",
        hover_name="titre",
        color_discrete_map=LEVEL_COLORS,
        category_orders={"niveau_qualite": list(LEVEL_COLORS)},
        labels={
            "score_natif_data_fair": "metadataScore (Data Fair)",
            "score_global": "Score global (ce tableau de bord)",
            "niveau_qualite": "Niveau",
        },
    )
    return style(fig, height)


def timeline(m: pd.DataFrame, ref_date=None, height=None):
    """Périodes couvertes. Les périodes ponctuelles (début = fin), invisibles sous forme de barre, sont
    représentées par un losange ; les périodes en cours (début seul) vont jusqu'à la date de référence.
    """
    d = m[m["temporel_debut"] != ""].copy()
    if d.empty:
        return None
    d["debut"] = pd.to_datetime(d["temporel_debut"])
    d["fin"] = pd.to_datetime(d["temporel_fin"].replace("", pd.NA))
    ongoing = d["fin"].isna()
    d.loc[ongoing, "fin"] = (
        pd.Timestamp(ref_date)
        if ref_date is not None
        else pd.Timestamp.today().normalize()
    )
    punct = d["temporel_type"].str.startswith("Ponctuelle")
    bars, points = d[~punct], d[punct]
    d = d.sort_values("debut")
    if len(bars):
        fig = px.timeline(
            bars,
            x_start="debut",
            x_end="fin",
            y="titre",
            color="temporel_type",
            color_discrete_sequence=COLORWAY,
            labels={"temporel_type": "Type", "titre": ""},
        )
    else:
        fig = go.Figure()
    if len(points):
        fig.add_trace(
            go.Scatter(
                x=points["debut"],
                y=points["titre"],
                mode="markers",
                name="Ponctuelle (début = fin)",
                marker=dict(
                    symbol="diamond",
                    size=13,
                    color=PALETTE["accent"],
                    line=dict(width=1, color="white"),
                ),
                hovertemplate="%{y}<br>%{x|%d/%m/%Y}<extra>Ponctuelle</extra>",
            )
        )
    fig.update_yaxes(
        title=None,
        showticklabels=len(d) <= 30,
        categoryorder="array",
        categoryarray=list(dict.fromkeys(d["titre"])),
        autorange="reversed",
    )
    return style(fig, height or _auto_height(len(d), per=24, base=110, min_h=300))
