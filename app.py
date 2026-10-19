"""Tableau de bord qualité du catalogue open data de Grand Poitiers.

Lancer :  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
import html
import inspect
import os
from collections import Counter
from types import SimpleNamespace

import numpy as np
import pandas as pd
import streamlit as st

from quality import charts, exports, loader, metrics
from quality import config as cfg
from quality import textkit as tk

st.set_page_config(
    page_title="Qualité du catalogue open data", page_icon="📊", layout="wide"
)

# Version minimale de Streamlit (st.cache_data, st.column_config… absents des anciennes versions)
try:
    _st_version = tuple(int(x) for x in st.__version__.split(".")[:2])
except Exception:
    _st_version = (0, 0)
if _st_version < (1, 40):
    st.error(
        f"**Streamlit {st.__version__} est trop ancien** (version 1.40 minimum). "
        "Vous lancez probablement l'application avec le Python global au lieu de l'environnement du projet. "
        "Activez le venv puis `python -m streamlit run app.py`, ou mettez à jour : `python -m pip install -U -r requirements.txt`."
    )
    st.stop()


# --------------------------------------------------------------------------- #
# Contrôle de cohérence : app.py et le dossier quality/ doivent provenir de la même version
# --------------------------------------------------------------------------- #
_REQUIRED_CFG = [
    "ANALYSED_FIELDS",
    "DEFAULT_CATALOGUE",
    "DEFAULT_PARAMS",
    "DEFAULT_SCHEMA",
    "DEFAULT_WEIGHTS",
    "FALC_RULES",
    "FALC_STATUS_LABELS",
    "FALC_COHERENCE_LABELS",
    "FALC_NOT_FROM_GUIDE",
    "FREQUENCIES",
    "FREQUENCY_ORDER",
    "GENERIC_KEYWORDS",
    "GENERIC_WORDS",
    "LEVEL_COLORS",
    "LICENCE_RULES",
    "LICENCE_VERSION_RULE",
    "METRIC_DICT",
    "DATAFAIR_DOCS",
    "KW_REFERENCE_FIELDS",
    "MISSING_FIELD_USE",
    "PALETTE",
    "PROVENANCE_RULES",
    "QUALITY_LEVELS",
    "SCORE_FORMULA",
    "SCORE_HELP",
    "SCORE_LABELS",
    "SPATIAL_RULES",
    "STOPWORDS",
]
_missing = [f"config.{n}" for n in _REQUIRED_CFG if not hasattr(cfg, n)]
if "ref_date" not in inspect.signature(charts.timeline).parameters:
    _missing.append("charts.timeline(ref_date)")
if not hasattr(metrics, "STATUT_ORDER"):
    _missing.append("metrics.STATUT_ORDER")
if _missing:
    st.error(
        "**Installation incohérente** : `app.py` est plus récent que le dossier `quality/`. "
        "Remplacez **tout** le dossier `quality/` (config.py, metrics.py, charts.py, textkit.py, loader.py, exports.py) "
        "par celui de la dernière archive, puis relancez.\n\n"
        f"Éléments manquants : {', '.join(_missing)}"
    )
    st.stop()

P_ = cfg.PALETTE
st.markdown(
    f"""
<style>
.gp-header {{background: linear-gradient(135deg, {P_['primary']} 0%, #4B44B0 100%); color: white;
  padding: 1.3rem 1.8rem; border-radius: 14px; margin-bottom: 1rem;}}
.gp-header h1 {{color: white; margin: 0; font-size: 1.65rem; padding: 0;}}
.gp-header p {{color: #DAD8F8; margin: .25rem 0 0 0; font-size: .95rem;}}
div[data-testid="stMetric"] {{background: {P_['bg_soft']}; border-left: 5px solid {P_['primary']};
  padding: .7rem 1rem; border-radius: 10px;}}
div[data-testid="stMetricLabel"] p {{color: {P_['muted']}; font-size: .85rem;}}
h3.gp-h3 {{color: {P_['primary']}; margin: 1.2rem 0 .2rem 0; padding: 0; font-size: 1.2rem;}}
.hint {{cursor: help; color: {P_['primary_mid']}; font-size: .85em; margin-left: .35rem;}}
.gp-note {{color: {P_['muted']}; font-size: .88rem; margin-bottom: .6rem;}}
.gp-read {{background: {P_['bg_soft']}; border-left: 4px solid {P_['accent']}; border-radius: 6px;
  padding: .45rem .8rem; margin: .1rem 0 1rem 0; font-size: .87rem; color: {P_['text']};}}
.stTabs [data-baseweb="tab"] {{font-weight: 600; color: {P_['muted']};}}
.stTabs [aria-selected="true"] {{color: {P_['primary']};}}
.stTabs [data-baseweb="tab-highlight"] {{background-color: {P_['accent']};}}
section[data-testid="stSidebar"] {{background: {P_['bg_soft']};}}
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Compatibilité entre versions de Streamlit (use_container_width -> width="stretch")
# --------------------------------------------------------------------------- #
def _wide_kwargs(fn) -> dict:
    """`width="stretch"` sur les Streamlit récents (où `use_container_width` est déprécié et affiche des
    avertissements) ; `use_container_width=True` sur les anciens."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}
    width = params.get("width")
    if width is not None and "stretch" in str(width.annotation):
        return {"width": "stretch"}
    if "use_container_width" in params:
        try:  # repli par numéro de version si l'annotation n'est pas exploitable
            major, minor = (int(x) for x in st.__version__.split(".")[:2])
            if (major, minor) >= (1, 50):
                return {"width": "stretch"}
        except Exception:
            pass
        return {"use_container_width": True}
    if width is not None:
        return {"width": "stretch"}
    return {}


_WIDE = {
    name: _wide_kwargs(getattr(st, name))
    for name in ("plotly_chart", "dataframe", "download_button")
}


def show(fig, key: str | None = None):
    if fig is not None:
        st.plotly_chart(fig, key=key, **_WIDE["plotly_chart"])


def table(df: pd.DataFrame, height: int | None = None, column_config=None):
    kw = dict(hide_index=True, **_WIDE["dataframe"])
    if height:
        kw["height"] = height
    if column_config:
        kw["column_config"] = column_config
    st.dataframe(df, **kw)


def note(text: str):
    st.markdown(f"<div class='gp-note'>{text}</div>", unsafe_allow_html=True)


def docs_links(keys, prefix: str = "📘 Documentation Data Fair :"):
    """Liens (vérifiés) vers la documentation Data Fair, à l'endroit où ils sont utiles."""
    links = " · ".join(
        f'<a href="{cfg.DATAFAIR_DOCS[k][1]}" target="_blank" rel="noopener">{cfg.DATAFAIR_DOCS[k][0]}</a>'
        for k in keys
    )
    note(f"{prefix} {links}")


def reading(fn):
    """Clé de lecture d'un graphique : `fn` renvoie une phrase calculée sur les données affichées.
    En cas d'erreur (ex. données filtrées vides), la clé est simplement omise."""
    try:
        txt = fn()
    except Exception:
        if os.environ.get("GP_DEBUG"):
            raise
        txt = None
    if txt:
        st.markdown(
            f"<div class='gp-read'><b>🔎 Lecture</b> - {txt}</div>",
            unsafe_allow_html=True,
        )


def fr(x, d: int = 0) -> str:
    """Nombre au format français (espace pour les milliers, virgule décimale)."""
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


# --------------------------------------------------------------------------- #
# Chargement
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Chargement du schéma…")
def load_schema_cached(sch_bytes: bytes) -> pd.DataFrame:
    return loader.load_schema(sch_bytes)


@st.cache_data(show_spinner="Calcul des indicateurs…")
def analyse(cat_bytes: bytes, params: dict, ref_date: dt.date):
    df = loader.load_catalogue(cat_bytes)
    m = metrics.compute_dataset_metrics(df, params, ref_date)
    return df, m


# --------------------------------------------------------------------------- #
# En-tête + barre latérale (entrées)
# --------------------------------------------------------------------------- #
st.markdown(
    "<div class='gp-header'><h1>📊 Qualité du catalogue open data</h1>"
    "<p>État des lieux des métadonnées du catalogue.</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### ⚙️ Paramètres")
    up_cat = st.file_uploader(
        "Catalogue (CSV)", type="csv", help="Par défaut : data/catalogue-opendata.csv"
    )
    up_sch = st.file_uploader(
        "Schéma de métadonnées (CSV)",
        type="csv",
        help="Par défaut : data/schema-metadonnees.csv",
    )
    ref_date = st.date_input(
        "Date de référence",
        value=dt.date.today(),
        help="Sert à calculer l'ancienneté des mises à jour.",
    )

cat_bytes = up_cat.getvalue() if up_cat else cfg.DEFAULT_CATALOGUE.read_bytes()
sch_bytes = up_sch.getvalue() if up_sch else cfg.DEFAULT_SCHEMA.read_bytes()
schema = load_schema_cached(sch_bytes)
HINTS = loader.schema_hints(schema)
raw_all = loader.load_catalogue(cat_bytes)

P = dict(cfg.DEFAULT_PARAMS)
weights = dict(cfg.DEFAULT_WEIGHTS)
with st.sidebar:
    with st.expander("Seuils & règles"):
        st.caption("Titre")
        P["title_min_chars"] = st.number_input(
            "Nb mini de caractères (X)", 5, 100, int(P["title_min_chars"])
        )
        P["title_max_chars"] = st.number_input(
            "Nb maxi de caractères", 50, 300, int(P["title_max_chars"])
        )
        P["title_min_meaningful"] = st.number_input(
            "Nb mini de mots porteurs de sens", 1, 6, int(P["title_min_meaningful"])
        )
        st.caption("Description & résumé")
        P["desc_min_words"] = st.number_input(
            "Nb mini de mots (Y)", 5, 300, int(P["desc_min_words"])
        )
        P["summary_max_sentences"] = st.number_input(
            "Résumé : phrases maximum", 1, 5, int(P["summary_max_sentences"])
        )
        st.caption("Mots-clés & thématiques")
        P["kw_min"] = st.number_input("Mots-clés : minimum", 0, 10, int(P["kw_min"]))
        P["kw_max"] = st.number_input("Mots-clés : maximum", 3, 30, int(P["kw_max"]))
        P["topics_max"] = st.number_input(
            "Thématiques : maximum", 1, 10, int(P["topics_max"])
        )
        P["kw_comp_low"] = st.number_input(
            "Vocabulaire nouveau : seuil bas (%)",
            0,
            50,
            int(P["kw_comp_low"]),
            help="En dessous, les mots-clés sont jugés trop redondants avec le reste des métadonnées.",
        )
        P["kw_comp_high"] = st.number_input(
            "Vocabulaire nouveau : seuil haut (%)",
            50,
            100,
            int(P["kw_comp_high"]),
            help="Au-delà, on ne peut plus distinguer un synonyme utile d'un mot hors sujet.",
        )
        st.caption("FALC (proxy)")
        P["falc_target_sentence_words"] = st.number_input(
            "Mots par phrase visés", 8, 30, int(P["falc_target_sentence_words"])
        )
        P["falc_long_sentence_words"] = st.number_input(
            "Phrase 'longue' à partir de (mots)",
            10,
            60,
            int(P["falc_long_sentence_words"]),
        )
        st.caption("Fraîcheur")
        P["due_tolerance"] = st.number_input(
            "Tolérance sur l'intervalle attendu (×)",
            1.0,
            3.0,
            float(P["due_tolerance"]),
            0.05,
        )
        P["due_grace_days"] = st.number_input(
            "Jours de grâce", 0, 30, int(P["due_grace_days"])
        )
    with st.expander("Pondération du score global"):
        for key, label in cfg.SCORE_LABELS.items():
            weights[key] = st.slider(
                label,
                0,
                100,
                int(cfg.DEFAULT_WEIGHTS[key]),
                5,
                help=cfg.SCORE_HELP[key],
            )
        st.caption("Les poids sont normalisés automatiquement.")
    with st.expander("Champs comptés dans la complétude"):
        default_fields = [f for f in cfg.ANALYSED_FIELDS if f in raw_all.columns]
        sel_fields = st.multiselect(
            "Champs",
            list(raw_all.columns),
            default=default_fields,
            help="`owner` n'existe pas dans l'export actuel : colonne créée vide, comptée comme non renseignée.",
        )
        P["completeness_fields"] = tuple(sel_fields)

raw, m_all = analyse(cat_bytes, P, ref_date)
m_all = metrics.apply_scores(m_all, weights)

# --------------------------------------------------------------------------- #
# Filtres globaux
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### 🔎 Filtres")
    all_topics = sorted({t for lst in m_all["_tp_raw"] for t in lst})
    has_no_topic = any(len(lst) == 0 for lst in m_all["_tp_raw"])
    sel_topics = st.multiselect(
        "Thématique", all_topics + ([metrics.NA_LABEL] if has_no_topic else [])
    )
    sel_spatial = st.multiselect(
        "Couverture spatiale",
        [x for x in metrics.SPATIAL_ORDER if x in set(m_all["spatial_type"])],
    )
    sel_prov = st.multiselect(
        "Provenance",
        [x for x in metrics.PROVENANCE_ORDER if x in set(m_all["provenance_type"])],
    )
    sel_level = st.multiselect(
        "Niveau de qualité", [lv for _, lv in cfg.QUALITY_LEVELS]
    )

mask = pd.Series(True, index=m_all.index)
if sel_topics:
    mask &= m_all["_tp_raw"].map(
        lambda l: any(t in sel_topics for t in l)
        or (not l and metrics.NA_LABEL in sel_topics)
    )
if sel_spatial:
    mask &= m_all["spatial_type"].isin(sel_spatial)
if sel_prov:
    mask &= m_all["provenance_type"].isin(sel_prov)
if sel_level:
    mask &= m_all["niveau_qualite"].isin(sel_level)
m = m_all[mask]
if m.empty:
    st.warning("Aucun jeu de données ne correspond aux filtres sélectionnés.")
    st.stop()
raw_f = raw.loc[m.index].copy()
raw_f.attrs = dict(raw.attrs)
g = metrics.compute_global(m, raw_f, schema, P)

# --------------------------------------------------------------------------- #
# Exports (barre latérale, toujours accessibles)
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### ⬇️ Exports")
    csv_fr = st.radio(
        "Format CSV", ["Excel FR (; et virgule)", "Standard (, et point)"], index=0
    ).startswith("Excel")
    st.download_button(
        "Vue globale du catalogue",
        exports.to_csv_bytes(exports.global_view(g), csv_fr),
        file_name="catalogue_vue_globale.csv",
        mime="text/csv",
        help="Pour chaque indicateur : sa valeur / son score (format long).",
        **_WIDE["download_button"],
    )
    st.download_button(
        "Vue détaillée par jeu de données",
        exports.to_csv_bytes(exports.dataset_view(m), csv_fr),
        file_name="catalogue_vue_par_jeu.csv",
        mime="text/csv",
        help="Une ligne par jeu, une colonne par indicateur.",
        **_WIDE["download_button"],
    )
    if len(m) < len(m_all):
        st.caption(
            f"⚠️ Les exports reflètent les filtres actifs ({len(m)} / {len(m_all)} jeux)."
        )


# --------------------------------------------------------------------------- #
# Utilitaires d'affichage
# --------------------------------------------------------------------------- #
def section(title: str, keys=(), sub: str | None = None):
    """Titre de section avec infobulle ⓘ reprenant les descriptions du schéma de métadonnées."""
    tips = [HINTS[k] for k in keys if k in HINTS]
    tip_html = ""
    if tips:
        tip = html.escape("\n".join(tips), quote=True).replace("\n", "&#10;")
        tip_html = f"<span class='hint' title=\"{tip}\">ⓘ</span>"
    st.markdown(f"<h3 class='gp-h3'>{title}{tip_html}</h3>", unsafe_allow_html=True)
    if sub:
        note(sub)


def vc(series: pd.Series, order=None) -> pd.Series:
    s = (
        series.replace("", metrics.NA_LABEL)
        .fillna(metrics.NA_LABEL)
        .astype(str)
        .value_counts()
    )
    if order:
        s = s.reindex(
            [o for o in order if o in s.index] + [x for x in s.index if x not in order]
        )
    return s


def pct(n, d) -> str:
    return f"{100 * n / d:.0f} %" if d else "n/a"


N = len(m)
ref_year = ref_date.year

# =========================================================================== #
# Calculs communs aux onglets
# =========================================================================== #
wsum = sum(weights.values()) or 1
dims = [d for d in cfg.SCORE_LABELS if d in m.columns]


def classification_block(kind: str):
    """Règles de regroupement (provenance / spatial / licence) + nombre de jeux + exemples réels + table complète."""
    rules, col_raw, col_type, label = {
        "provenance": (
            cfg.PROVENANCE_RULES,
            "origine",
            "provenance_type",
            "origine saisie",
        ),
        "spatial": (cfg.SPATIAL_RULES, "spatial", "spatial_type", "libellé saisi"),
        "licence": (cfg.LICENCE_RULES, "licence", "licence_famille", "libellé saisi"),
    }[kind]
    t = pd.DataFrame(rules, columns=["Catégorie", "Règle appliquée"])
    t["Jeux"] = t["Catégorie"].map(m[col_type].value_counts()).fillna(0).astype(int)
    ex = (
        m[m[col_raw] != ""]
        .groupby(col_type)[col_raw]
        .apply(
            lambda s: " · ".join(
                x if len(x) <= 60 else x[:57] + "…"
                for x in s.value_counts().head(3).index
            )
        )
    )
    t["Exemples les plus fréquents"] = t["Catégorie"].map(ex).fillna("-")
    table(t)
    with st.expander(f"Voir toutes les valeurs ({label}) et la catégorie attribuée"):
        full = (
            m.groupby([col_type, col_raw])
            .size()
            .reset_index(name="Jeux")
            .rename(
                columns={col_type: "Catégorie attribuée", col_raw: label.capitalize()}
            )
        )
        full[label.capitalize()] = full[label.capitalize()].replace("", "(vide)")
        table(
            full.sort_values(["Catégorie attribuée", "Jeux"], ascending=[True, False]),
            height=320,
        )


tabs = st.tabs(
    [
        "🏠 Synthèse",
        "✅ Complétude",
        "📝 Titres",
        "📖 Descriptions & FALC",
        "🏷️ Thématiques & mots-clés",
        "📜 Licences, provenance & schémas",
        "🌍 Spatial & temporel",
        "🕒 Mises à jour",
        "🔎 Jeux de données",
        "📚 Méthodologie",
    ]
)

# =========================================================================== #
# 1. Synthèse
# =========================================================================== #
with tabs[0]:
    ev = m[m["statut_fraicheur"].isin(["À jour", "En retard", "Très en retard"])]
    c = st.columns(5)
    c[0].metric(
        "Jeux de données",
        f"{N}",
        help=f"Sur {len(m_all)} au total (filtres actifs : {N < len(m_all)})",
    )
    c[1].metric(
        "Score global moyen",
        f"{m['score_global'].mean():.0f} / 100",
        help="Moyenne pondérée des dimensions. Pondérations modifiables dans la barre latérale.",
    )
    c[2].metric(
        "Complétude moyenne",
        f"{m['completude_pct'].mean():.0f} %",
        help="Part des champs retenus qui sont renseignés, en moyenne par jeu.",
    )
    c[3].metric(
        "À jour (selon fréquence)",
        pct((ev["statut_fraicheur"] == "À jour").sum(), len(ev)),
        help=f"Calculé sur les {len(ev)} jeux dont la fréquence est renseignée et évaluable.",
    )
    c[4].metric(
        "Alertes par jeu",
        f"{m['nb_alertes'].mean():.1f}",
        help="Nombre moyen de défauts détectés par jeu.",
    )

    a, b = st.columns([3, 2])
    lv = vc(m["niveau_qualite"], [x for _, x in cfg.QUALITY_LEVELS])
    with a:
        section("Répartition des scores")
        show(charts.score_histogram(m), "syn_hist")
        reading(
            lambda: (
                f"chaque barre regroupe les jeux dont le score global est dans une même tranche ; la couleur donne le niveau. "
                f"Ici, {lv.reindex(['A – Très bon', 'B – Bon']).fillna(0).sum():.0f} jeux sur {N} sont au niveau A ou B, "
                f"{lv.reindex(['C – À améliorer', 'D – Prioritaire']).fillna(0).sum():.0f} au niveau C ou D. "
                f"Le score médian est de {m['score_global'].median():.0f}/100."
            )
        )
    with b:
        section("Niveaux de qualité", sub="A ≥ 80 · B ≥ 65 · C ≥ 50 · D < 50")
        show(
            charts.donut(
                lv.index,
                lv.values,
                colors=[cfg.LEVEL_COLORS.get(x, P_["muted"]) for x in lv.index],
            ),
            "syn_donut",
        )
        reading(
            lambda: f"{pct(lv.iloc[0], N)} des jeux sont au niveau « {lv.index[0]} » ({int(lv.iloc[0])} jeux) ; "
            f"le niveau D (prioritaire) en regroupe {int(lv.get('D – Prioritaire', 0))}."
        )

    section(
        "Score moyen par dimension",
        sub=f"Chaque jeu reçoit une note de 0 à 100 dans chacune des 7 dimensions (complétude, titre, fraîcheur…). "
        f"Chaque barre est la <b>moyenne de ces notes sur les {N} jeux</b> du périmètre ; le % entre parenthèses est le "
        f"<b>poids de la dimension dans le score global</b> (réglable dans la barre latérale). "
        f"Rouge &lt; 50 · orange &lt; 75 · vert ≥ 75.",
    )
    vals = [round(float(m[d].mean()), 1) for d in dims]
    fig = charts.bar(
        [f"{cfg.SCORE_LABELS[d]} ({100 * weights[d] / wsum:.0f} %)" for d in dims],
        vals,
        color=[
            P_["good"] if v >= 75 else P_["warning"] if v >= 50 else P_["bad"]
            for v in vals
        ],
        height=330,
    )
    fig.update_xaxes(range=[0, 112])
    show(fig, "syn_dims")

    def _dims_reading():
        active = [(d, v) for d, v in zip(dims, vals) if weights[d] > 0]
        best, worst = max(active, key=lambda x: x[1]), min(active, key=lambda x: x[1])
        return (
            f"en moyenne, les jeux obtiennent {fr(best[1], 0)}/100 en « {cfg.SCORE_LABELS[best[0]]} » (dimension la mieux notée) "
            f"et {fr(worst[1], 0)}/100 en « {cfg.SCORE_LABELS[worst[0]]} » (la moins bien notée) : c'est là que le gain potentiel est le plus grand."
        )

    reading(_dims_reading)

    section(
        "Jeux de données à corriger en priorité",
        sub="Les 10 scores les plus bas du périmètre filtré.",
    )
    worst = m.nsmallest(10, "score_global")[
        ["titre", "score_global", "niveau_qualite", "nb_alertes", "alertes"]
    ]
    table(
        worst,
        column_config={
            "titre": "Titre",
            "niveau_qualite": "Niveau",
            "nb_alertes": "Alertes",
            "alertes": "Détail des alertes",
            "score_global": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"
            ),
        },
    )

    with st.expander("Comparaison avec le score natif Data Fair (`metadataScore`)"):
        d = m.dropna(subset=["score_natif_data_fair"])
        if len(d) > 2:
            st.write(
                f"Corrélation entre les deux scores : **{d['score_global'].corr(d['score_natif_data_fair']):.2f}** "
                f"(n = {len(d)})."
            )
        show(charts.scatter_native(m), "syn_native")
        reading(
            lambda: "chaque point est un jeu. Plus il est en haut à droite, mieux il est noté à la fois par Data Fair et par ce tableau de bord ; "
            "un point éloigné de la diagonale signale un désaccord entre les deux méthodes."
        )
        st.caption(HINTS.get("metadataScore", ""))
        note(
            "La formule de ce score (10 critères, 20 points) est décrite dans le schéma de métadonnées, champ `metadataScore` : "
            "voir le tableau « Détail par attribut » de l'onglet Complétude."
        )
        docs_links(["accueil"])

# =========================================================================== #
# 2. Complétude
# =========================================================================== #
with tabs[1]:
    comp = loader.completeness_table(raw_f, schema)
    section(
        "Taux de remplissage de chaque attribut",
        sub="Toutes les colonnes de l'export, telles quelles. Survolez une barre pour lire la description du schéma. "
        "Les champs marqués * ne sont pas dans le fichier exporté : le tableau de bord les crée vides (à 0 %).",
    )
    show(charts.completeness_bar(comp), "comp_bar")
    docs_links(
        ["admin_jeux", "contributeur"],
        "📘 Où renseigner ces métadonnées dans Data Fair :",
    )

    def _comp_reading():
        e = comp[comp["dans_export"]]
        low, top = (
            e.sort_values("taux_completude").iloc[0],
            e.sort_values("taux_completude").iloc[-1],
        )
        return (
            f"« {low['champ']} » n'est renseigné que pour {low['taux_completude']:.0f} % des jeux ({low['remplis']} sur {low['total']}), "
            f"contre {top['taux_completude']:.0f} % pour « {top['champ']} ». "
            f"{int((e['taux_completude'] < 50).sum())} des {len(e)} attributs de l'export sont renseignés à moins de 50 %."
        )

    reading(_comp_reading)

    section("Détail par attribut")
    table(
        comp[
            [
                "champ",
                "libelle",
                "groupe",
                "type",
                "remplis",
                "vides",
                "taux_completude",
                "description",
            ]
        ],
        height=420,
        column_config={
            "champ": "Clé",
            "libelle": "Libellé",
            "groupe": "Groupe",
            "type": "Type",
            "remplis": "Remplis",
            "vides": "Vides",
            "description": "Description (schéma)",
            "taux_completude": st.column_config.ProgressColumn(
                "% rempli", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )

    a, b = st.columns(2)
    with a:
        section(
            "Complétude par jeu", sub="Sur les champs retenus dans la barre latérale."
        )
        show(
            charts.histogram(
                m["completude_pct"], nbins=20, xtitle="% de champs renseignés"
            ),
            "comp_hist",
        )
        reading(
            lambda: f"la moitié des jeux ont au moins {m['completude_pct'].median():.0f} % de leurs champs retenus renseignés ; "
            f"{int((m['completude_pct'] < 50).sum())} jeux ({pct((m['completude_pct'] < 50).sum(), N)}) sont sous 50 %."
        )
    with b:
        section("Nombre de champs vides par jeu")
        e = vc(m["nb_champs_vides"].astype(int).astype(str))
        e = e.reindex(sorted(e.index, key=int))
        show(
            charts.bar(
                e.index,
                e.values,
                horizontal=False,
                xtitle="Champs vides",
                ytitle="Jeux de données",
            ),
            "comp_empty",
        )
        reading(
            lambda: f"la situation la plus fréquente : {int(e.max())} jeux ont exactement {e.idxmax()} champs vides "
            f"sur les {len(P['completeness_fields'])} champs retenus."
        )

    in_export = list(raw.attrs.get("columns_in_export", raw.columns))
    known = [c_ for c_ in in_export if c_ in set(schema["cle"])]
    unknown = [c_ for c_ in in_export if c_ not in set(schema["cle"])]
    not_exp = loader.schema_fields_not_exported(raw, schema)
    not_exp = not_exp.assign(
        utile=not_exp["cle"].map(cfg.MISSING_FIELD_USE).fillna("-")
    )
    with st.expander(
        f"Champs définis dans le schéma mais absents de l'export ({len(not_exp)} sur {len(schema)})"
    ):
        note(
            f"Le fichier exporté contient <b>{len(in_export)} colonnes</b>, dont <b>{len(known)}</b> sont définies dans le schéma "
            f"(le schéma définit {len(schema)} champs). Les <b>{len(not_exp)} champs ci-dessous</b> sont dans le schéma mais pas dans le fichier. "
            f"Trois d'entre eux : <code>id</code>, <code>page</code>, <code>owner</code>, apparaissent quand même dans le graphique ci-dessus "
            f"(marqués *) car le tableau de bord les crée vides pour que leurs indicateurs fonctionnent dès qu'ils seront exportés."
        )
        if unknown:
            st.warning(
                f"Colonnes de l'export absentes du schéma : {', '.join(unknown)}"
            )
        table(
            not_exp.rename(
                columns={
                    "groupe": "Groupe",
                    "cle": "Clé",
                    "libelle": "Libellé",
                    "type": "Type",
                    "description": "Description",
                    "utile": "Utile pour ce tableau de bord",
                }
            ),
            height=360,
        )
    with st.expander(f"Colonnes présentes dans l'export ({len(in_export)})"):
        st.write(", ".join(f"`{c_}`" for c_ in in_export))
    with st.expander("Conformité des valeurs au type déclaré dans le schéma"):
        tc = loader.type_conformity(raw_f, schema)
        table(
            tc,
            column_config={
                "taux_conformite": st.column_config.ProgressColumn(
                    "% conforme", min_value=0, max_value=100, format="%.0f"
                )
            },
        )

# =========================================================================== #
# 3. Titres
# =========================================================================== #
with tabs[2]:
    section(
        "Titres",
        ["title"],
        "Longueur, mais surtout pertinence : un titre long fait de mots creux n'apprend rien.",
    )
    c = st.columns(4)
    c[0].metric("Longueur moyenne", f"{m['titre_nb_caracteres'].mean():.0f} car.")
    c[1].metric(
        f"Titres < {P['title_min_chars']} car.",
        f"{int(m['titre_trop_court'].sum())}",
        help=f"Soit {pct(m['titre_trop_court'].sum(), N)} des jeux",
    )
    c[2].metric(
        "Titres peu informatifs",
        f"{int(m['titre_peu_informatif'].sum())}",
        help=f"Moins de {P['title_min_meaningful']} mots porteurs de sens",
    )
    c[3].metric(
        "Titres techniques / doublons",
        f"{int(m['titre_technique'].sum())} / {int(m['titre_doublon'].sum())}",
        help="Techniques : underscore, extension de fichier, slug. Doublons : même titre qu'un autre jeu.",
    )

    a, b = st.columns(2)
    with a:
        section("Nombre de caractères")
        show(
            charts.histogram(
                m["titre_nb_caracteres"],
                nbins=25,
                vlines=[(P["title_min_chars"], f"X = {P['title_min_chars']}")],
                xtitle="Caractères",
            ),
            "tit_chars",
        )
        reading(
            lambda: f"{int(m['titre_trop_court'].sum())} titres ({pct(m['titre_trop_court'].sum(), N)}) sont à gauche du trait "
            f"(moins de {P['title_min_chars']} caractères) ; le titre médian compte {m['titre_nb_caracteres'].median():.0f} caractères."
        )
    with b:
        section(
            "Mots du titre vs mots porteurs de sens",
            sub="Un point sous la diagonale = des mots qui n'apportent rien (de, des, jeu, données…).",
        )
        show(charts.title_words_scatter(m), "tit_scatter")
        reading(
            lambda: f"un point sur la diagonale est un titre composé uniquement de mots porteurs de sens. "
            f"{int((m['titre_ratio_porteurs'] < 0.5).sum())} titres ({pct((m['titre_ratio_porteurs'] < 0.5).sum(), N)}) "
            f"ont plus de la moitié de leurs mots sans valeur."
        )

    a, b = st.columns(2)
    with a:
        section("Mots sans valeur les plus fréquents dans les titres")
        noise = Counter(
            w.lower() for lst in m["_titre_bruit"] for w in lst
        ).most_common(15)
        if noise:
            show(
                charts.bar(
                    [w for w, _ in noise], [c_ for _, c_ in noise], color=P_["accent"]
                ),
                "tit_noise",
            )
            reading(
                lambda: f"le mot « {noise[0][0]} » apparaît {noise[0][1]} fois dans les titres sans apporter d'information "
                f"(mot vide ou mot creux, voir l'onglet Méthodologie)."
            )
    with b:
        section("Nombre de mots porteurs de sens")
        mp = vc(m["titre_nb_mots_porteurs"].clip(upper=8).astype(int).astype(str))
        mp = mp.reindex(sorted(mp.index, key=int))
        show(
            charts.bar(
                [f"{k}{'+' if k == '8' else ''}" for k in mp.index],
                mp.values,
                horizontal=False,
                xtitle="Mots porteurs de sens",
                ytitle="Jeux de données",
            ),
            "tit_meaning",
        )
        reading(
            lambda: f"{int(mp.max())} titres contiennent exactement {mp.idxmax()} mots porteurs de sens (cas le plus fréquent) ; "
            f"{int(m['titre_peu_informatif'].sum())} en ont moins de {P['title_min_meaningful']}."
        )

    section("Titres à retravailler")
    flags = {
        "Trop courts": "titre_trop_court",
        "Peu informatifs": "titre_peu_informatif",
        "Techniques": "titre_technique",
        "En doublon": "titre_doublon",
        "En capitales": "titre_majuscules",
        "Trop longs": "titre_trop_long",
    }
    choice = st.selectbox(
        "Afficher", [f"{k} ({int(m[v].sum())})" for k, v in flags.items()]
    )
    col = flags[choice.rsplit(" (", 1)[0]]
    table(
        m.loc[
            m[col],
            [
                "titre",
                "titre_nb_caracteres",
                "titre_nb_mots",
                "titre_nb_mots_porteurs",
                "titre_mots_non_porteurs",
                "score_titre",
            ],
        ].sort_values("score_titre"),
        column_config={
            "titre": "Titre",
            "titre_nb_caracteres": "Caractères",
            "titre_nb_mots": "Mots",
            "titre_nb_mots_porteurs": "Mots porteurs",
            "titre_mots_non_porteurs": "Mots sans valeur",
            "score_titre": st.column_config.ProgressColumn(
                "Score titre", min_value=0, max_value=100, format="%.0f"
            ),
        },
    )

# =========================================================================== #
# 4. Descriptions & FALC
# =========================================================================== #
with tabs[3]:
    section("Descriptions", ["description"], "Longueur, unicité, lien avec le titre.")
    n_abs = int((m["desc_nb_mots"] == 0).sum())
    c = st.columns(5)
    c[0].metric("Longueur médiane", f"{m['desc_nb_mots'].median():.0f} mots")
    c[1].metric(
        f"Courtes (< {P['desc_min_words']} mots)",
        f"{int(m['desc_courte'].sum())}",
        help=f"+ {n_abs} absentes",
    )
    c[2].metric("Absentes", f"{n_abs}")
    c[3].metric(
        "Dupliquées",
        f"{int(m['desc_quasi_doublon'].sum())}",
        help="Identiques ou quasi identiques (≥ 85 % de similarité) à celle d'un autre jeu.",
    )
    c[4].metric(
        "= résumé",
        f"{int(m['desc_identique_resume'].sum())}",
        help="Description identique au résumé.",
    )

    a, b = st.columns(2)
    with a:
        section(
            "Nombre de mots de la description",
            sub="Valeurs au-delà de 400 mots regroupées.",
        )
        show(
            charts.histogram(
                m["desc_nb_mots"].clip(upper=400),
                nbins=30,
                vlines=[(P["desc_min_words"], f"Y = {P['desc_min_words']}")],
                xtitle="Mots",
            ),
            "desc_hist",
        )
        reading(
            lambda: f"{int(m['desc_courte'].sum())} descriptions sont à gauche du trait (moins de {P['desc_min_words']} mots), "
            f"auxquelles s'ajoutent {n_abs} descriptions absentes ; la description médiane compte {m['desc_nb_mots'].median():.0f} mots."
        )
    with b:
        section("Défauts détectés")
        items = {
            "Description absente": n_abs,
            f"Description < {P['desc_min_words']} mots": int(m["desc_courte"].sum()),
            "Description dupliquée": int(m["desc_quasi_doublon"].sum()),
            "Description = résumé": int(m["desc_identique_resume"].sum()),
            "Résumé absent": int((m["resume_nb_mots"] == 0).sum()),
            f"Résumé > {P['summary_max_sentences']} phrases": int(
                m["resume_trop_long"].sum()
            ),
            "Résumé qui répète le titre": int(
                (m["resume_nouveaute_vs_titre"] < 0.2).sum()
            ),
        }
        show(
            charts.bar(
                list(items), list(items.values()), color=P_["accent"], height=340
            ),
            "desc_flags",
        )
        reading(
            lambda: f"le défaut le plus fréquent est « {max(items, key=items.get)} » : {max(items.values())} jeux "
            f"({pct(max(items.values()), N)}). Un même jeu peut cumuler plusieurs défauts."
        )

    a, b = st.columns(2)
    with a:
        section(
            "Résumé : nombre de phrases",
            ["summary"],
            "Le schéma demande « une à deux phrases maximum ».",
        )
        ph = m["resume_nb_phrases"].clip(upper=5).astype(int)
        phv = ph.value_counts().sort_index()
        show(
            charts.bar(
                [f"{i}{'+' if i == 5 else ''}" for i in phv.index],
                phv.values,
                horizontal=False,
                color=[
                    P_["good"] if i <= P["summary_max_sentences"] else P_["warning"]
                    for i in phv.index
                ],
                xtitle="Phrases",
                ytitle="Jeux de données",
            ),
            "sum_sent",
        )
        reading(
            lambda: f"{int(m['resume_trop_long'].sum())} résumés ({pct(m['resume_trop_long'].sum(), N)}) dépassent "
            f"{P['summary_max_sentences']} phrases (barres orange) ; {int(phv.get(0, 0))} jeux n'ont pas de résumé."
        )
    with b:
        section(
            "Le résumé apporte-t-il de l'information en plus du titre ?",
            sub="Part des mots porteurs du résumé absents du titre. Proche de 0 : le résumé répète le titre.",
        )
        show(
            charts.histogram(
                m["resume_nouveaute_vs_titre"],
                nbins=20,
                xtitle="Information nouvelle (0 à 1)",
            ),
            "sum_novelty",
        )
        reading(
            lambda: f"pour {int((m['resume_nouveaute_vs_titre'] < 0.2).sum())} résumé(s), moins de 20 % des mots porteurs ne figurent pas déjà "
            f"dans le titre : ils le répètent presque entièrement. Le résumé médian apporte "
            f"{100 * m['resume_nouveaute_vs_titre'].median():.0f} % de mots nouveaux."
        )

    st.divider()
    section(
        "Lisibilité : proxy FALC",
        sub="Facile à Lire et à Comprendre : un vrai FALC se valide avec des relecteurs. Ici, un proxy automatique "
        "inspiré de quelques-unes de ses règles ; une partie des sous-notes ne vient pas du guide (voir le tableau de comparaison dans l'onglet Méthodologie). "
        "Calculé sur la description, à défaut le résumé.",
    )
    if not tk.HAS_WORDFREQ:
        st.info(
            "L'indicateur « mots rares / jargon » est désactivé : installez `wordfreq` (pip install wordfreq)."
        )
    c = st.columns(4)
    c[0].metric("Score FALC moyen", f"{m['falc_score'].mean():.0f} / 100")
    c[1].metric(
        "Mots / phrase (moyenne)",
        f"{m['falc_mots_par_phrase'].mean():.1f}",
        help=f"Cible retenue par le projet : {P['falc_target_sentence_words']} mots (le guide FALC ne donne pas de chiffre)",
    )
    c[2].metric(
        "Textes ≤ cible",
        pct(
            (m["falc_mots_par_phrase"] <= P["falc_target_sentence_words"]).sum(),
            m["falc_mots_par_phrase"].notna().sum(),
        ),
    )
    c[3].metric(
        "Mots longs (moyenne)",
        f"{m['falc_pct_mots_longs'].mean():.1f} %",
        help=f"Mots de {P['falc_long_word_syllables']} syllabes ou plus",
    )
    a, b = st.columns(2)
    with a:
        show(
            charts.histogram(
                m["falc_mots_par_phrase"],
                nbins=25,
                title="Longueur moyenne des phrases (mots)",
                vlines=[(P["falc_target_sentence_words"], "cible retenue")],
            ),
            "falc_asl",
        )
        reading(
            lambda: f"la phrase moyenne compte {m['falc_mots_par_phrase'].median():.0f} mots (médiane) ; "
            f"{int((m['falc_mots_par_phrase'] <= P['falc_target_sentence_words']).sum())} textes restent sous la cible de "
            f"{P['falc_target_sentence_words']} mots (à gauche du trait)."
        )
    with b:
        show(
            charts.histogram(
                m["falc_score"],
                nbins=20,
                title="Score FALC (0-100)",
                color=P_["primary"],
            ),
            "falc_score",
        )
        reading(
            lambda: f"le score FALC médian est de {m['falc_score'].median():.0f}/100 ; "
            f"{int((m['falc_score'] < 50).sum())} textes sont sous 50 (difficiles à lire)."
        )
    a, b = st.columns(2)
    with a:
        show(
            charts.histogram(
                m["falc_flesch_fr"],
                nbins=25,
                title="Indice de Flesch (adaptation française)",
                vlines=[(60, "texte standard")],
            ),
            "falc_flesch",
        )
        reading(
            lambda: f"plus l'indice est élevé, plus le texte est facile (au-dessus de 60 : lecture aisée ; 30 à 50 : difficile). "
            f"Indice médian ici : {m['falc_flesch_fr'].median():.0f} ; {int((m['falc_flesch_fr'] < 50).sum())} textes sont sous 50."
        )
    with b:
        avg = {
            "Phrases longues (%)": m["falc_pct_phrases_longues"].mean(),
            "Mots longs (%)": m["falc_pct_mots_longs"].mean(),
            "Sigles / 100 mots": m["falc_sigles_pour_100_mots"].mean(),
            "Textes avec balisage (%)": 100 * m["falc_balisage"].astype(float).mean(),
            "Textes avec parenthèses (%)": 100 * (m["falc_nb_parentheses"] > 0).mean(),
            "Textes avec liens bruts (%)": 100 * (m["falc_nb_urls"] > 0).mean(),
        }
        if tk.HAS_WORDFREQ:
            avg["Mots rares (%)"] = m["falc_pct_mots_rares"].mean()
        show(
            charts.bar(
                list(avg),
                [round(float(v), 1) for v in avg.values()],
                title="Points de friction (moyenne)",
                color=P_["accent"],
                height=320,
            ),
            "falc_friction",
        )
        reading(
            lambda: f"en moyenne, {avg['Phrases longues (%)']:.0f} % des phrases dépassent {P['falc_long_sentence_words']} mots, "
            f"{avg['Mots longs (%)']:.0f} % des mots sont longs, et {avg['Textes avec balisage (%)']:.0f} % des textes contiennent du balisage Markdown/HTML."
        )
    section("Textes les plus difficiles à lire")
    hard = m.dropna(subset=["falc_score"]).nsmallest(10, "falc_score")
    table(
        hard[
            [
                "titre",
                "falc_score",
                "falc_mots_par_phrase",
                "falc_pct_mots_longs",
                "falc_sigles_pour_100_mots",
                "falc_source",
            ]
        ],
        column_config={
            "titre": "Titre",
            "falc_mots_par_phrase": "Mots/phrase",
            "falc_pct_mots_longs": "% mots longs",
            "falc_sigles_pour_100_mots": "Sigles/100 mots",
            "falc_source": "Texte analysé",
            "falc_score": st.column_config.ProgressColumn(
                "Score FALC", min_value=0, max_value=100, format="%.0f"
            ),
        },
    )

# =========================================================================== #
# 5. Thématiques & mots-clés
# =========================================================================== #
with tabs[4]:
    rep_tp = metrics.normalization_report(list(m["_tp_raw"]))
    rep_kw = metrics.normalization_report(list(m["_kw_raw"]))

    section(
        "Thématiques",
        ["topics"],
        "Un jeu peut avoir plusieurs thématiques (séparées par « ; »).",
    )
    st_tp = rep_tp["stats"]
    if st_tp["distincts_brut"] == st_tp["distincts_norm"]:
        st.success(
            f"Les {st_tp['distincts_brut']} thématiques utilisées sont déjà cohérentes : "
            "aucune variante de casse, d'accent ou de pluriel détectée."
        )
    else:
        st.warning(
            f"{st_tp['distincts_brut']} thématiques distinctes → {st_tp['distincts_norm']} après normalisation simple."
        )
    a, b = st.columns([3, 2])
    with a:
        tp = rep_tp["raw_counter"].most_common()
        show(
            charts.bar(
                [k for k, _ in tp],
                [v for _, v in tp],
                title="Jeux de données par thématique",
                color=P_["primary_mid"],
            ),
            "tp_bar",
        )
        reading(
            lambda: f"la thématique « {tp[0][0]} » est attribuée à {tp[0][1]} jeux ({pct(tp[0][1], N)}). "
            f"Un jeu pouvant avoir plusieurs thématiques, le total des barres peut dépasser {N}."
        )
    with b:
        nbt = vc(m["topics_nb"].astype(int).astype(str))
        nbt = nbt.reindex(sorted(nbt.index, key=int))
        show(
            charts.bar(
                nbt.index,
                nbt.values,
                title="Nombre de thématiques par jeu",
                horizontal=False,
                xtitle="Thématiques",
                ytitle="Jeux de données",
            ),
            "tp_nb",
        )
        reading(
            lambda: f"{int(nbt.max())} jeux ont {nbt.idxmax()} thématique(s) (cas le plus fréquent) ; "
            f"{int((m['topics_nb'] == 0).sum())} n'en ont aucune."
        )

    st.divider()
    section(
        "Mots-clés : avant / après normalisation simple",
        ["keywords"],
        "Normalisation appliquée uniquement pour la mesure : minuscules, accents, ponctuation et séparateurs, pluriel simple. "
        "Elle montre l'ampleur du problème actuel et ce qu'on gagnerait à le corriger.",
    )
    docs_links(
        ["contributeur"],
        "📘 Saisie des mots-clés et thématiques : cours « Ajout de métadonnées, concepts et demandes de publications » du",
    )
    s = rep_kw["stats"]
    c = st.columns(4)
    c[0].metric(
        "Mots-clés distincts",
        s["distincts_brut"],
        delta=f"{s['distincts_norm'] - s['distincts_brut']} après normalisation",
        delta_color="off",
    )
    c[1].metric(
        "Vocabulaire redondant",
        f"{s['reduction_pct']} %",
        help="Part des mots-clés distincts qui sont une variante d'un autre.",
    )
    c[2].metric(
        "Jeux avec variantes internes",
        s["jeux_avec_variantes"],
        help="Jeux qui saisissent plusieurs variantes du même mot-clé (ex. élection ; élections).",
    )
    c[3].metric(
        "Mots-clés utilisés une seule fois",
        f"{s['hapax_pct_brut']} %",
        delta=f"{s['hapax_pct_norm'] - s['hapax_pct_brut']:.1f} pt après normalisation",
        delta_color="off",
        help="Un vocabulaire qui ne sert qu'une fois ne permet pas de regrouper les jeux.",
    )

    a, b = st.columns(2)
    top_raw = rep_kw["raw_counter"].most_common(20)
    top_norm = rep_kw["norm_counter"].most_common(20)
    with a:
        show(
            charts.bar(
                [k for k, _ in top_raw],
                [v for _, v in top_raw],
                title="Top 20 mots-clés tels que saisis",
                color=charts.BEFORE_COLOR,
            ),
            "kw_top_raw",
        )
        reading(
            lambda: f"« {top_raw[0][0]} » est saisi sous cette forme exacte dans {top_raw[0][1]} jeux. "
            f"Les variantes d'orthographe sont comptées séparément."
        )
    with b:
        show(
            charts.bar(
                [k for k, _ in top_norm],
                [v for _, v in top_norm],
                title="Top 20 mots-clés après normalisation",
                color=charts.AFTER_COLOR,
            ),
            "kw_top_norm",
        )
        reading(
            lambda: f"après regroupement des variantes, « {top_norm[0][0]} » concerne {top_norm[0][1]} jeux, contre "
            f"{rep_kw['raw_counter'].get(top_norm[0][0], 0)} pour la seule forme « {top_norm[0][0]} » telle que saisie."
        )

    a, b = st.columns(2)
    with a:
        pr, pn = pd.Series(rep_kw["per_dataset_raw"]), pd.Series(
            rep_kw["per_dataset_norm"]
        )
        idx = sorted(set(pr.clip(upper=15)) | set(pn.clip(upper=15)))
        before = [int((pr.clip(upper=15) == i).sum()) for i in idx]
        after = [int((pn.clip(upper=15) == i).sum()) for i in idx]
        show(
            charts.grouped_bar(
                [f"{i}{'+' if i == 15 else ''}" for i in idx],
                {"Avant": before, "Après normalisation": after},
                title="Jeux par nombre de mots-clés distincts",
                horizontal=False,
                xtitle="Mots-clés",
                ytitle="Jeux de données",
            ),
            "kw_dist",
        )

        def _kwdist_reading():
            j = max(range(len(idx)), key=lambda t: abs(before[t] - after[t]))
            return (
                f"avant normalisation, {before[j]} jeux ont {idx[j]} mots-clés distincts ; après, {after[j]}. "
                f"Les jeux « perdent » des mots-clés parce que certains n'étaient que des variantes d'un autre."
            )

        reading(_kwdist_reading)
    with b:
        gain = pd.DataFrame(
            {
                "Indicateur": [
                    "Mots-clés distincts",
                    "Utilisés une seule fois",
                    "Moyenne par jeu",
                ],
                "Avant": [s["distincts_brut"], s["hapax_brut"], s["moy_par_jeu_brut"]],
                "Après": [s["distincts_norm"], s["hapax_norm"], s["moy_par_jeu_norm"]],
            }
        )
        section("Gain potentiel")
        table(gain)
        st.caption(
            f"{s['n_variantes_multiples']} mots-clés existent sous plusieurs formes."
        )

    section(
        "Variantes détectées",
        sub="Chaque ligne = un même mot-clé saisi de plusieurs façons (nombre de jeux entre parenthèses).",
    )
    cl = rep_kw["clusters"]
    cl = cl[cl["n_variantes"] > 1][
        ["forme_retenue", "n_variantes", "jeux_concernes", "variantes"]
    ]
    table(
        cl,
        height=380,
        column_config={
            "forme_retenue": "Forme la plus fréquente",
            "n_variantes": "Formes",
            "jeux_concernes": "Jeux",
            "variantes": "Toutes les variantes",
        },
    )

    # ------------------------------------------------------------------ complémentarité
    st.divider()
    section(
        "Complémentarité des mots-clés avec les autres métadonnées",
        ["keywords"],
        "Un mot-clé n'ajoute un chemin de recherche que s'il contient un terme absent du titre, du résumé, de la description, des thématiques "
        "et de tout autre champ sur lequel la recherche du portail porte déjà. Chaque mot-clé est classé : "
        "<b>redondant</b> (tous ses mots figurent déjà ailleurs), <b>complémentaire</b> (aucun de ses mots n'apparaît ailleurs) ou <b>partiel</b>. "
        "Un mot-clé redondant n'est pas une faute, il sert aussi de filtre et de point de regroupement, mais un jeu dont <i>tous</i> les mots-clés le sont "
        "n'ajoute aucun vocabulaire. Un mot-clé 100 % nouveau n'est ni bon ni mauvais en soi : il peut être un synonyme utile ou un mot hors sujet.",
    )
    kd = pd.DataFrame(
        [dict(d, jeu=idx) for idx, lst in m["_kw_detail"].items() for d in lst]
    )
    if kd.empty:
        st.info("Aucun mot-clé évaluable sur ce périmètre.")
    else:
        n_kw = len(kd)
        cls = kd["classe"].value_counts()
        no_new = m[
            (
                (
                    m["kw_nb_redondants"]
                    + m["kw_nb_partiels"]
                    + m["kw_nb_complementaires"]
                )
                > 0
            )
            & (m["kw_nb_complementaires"] == 0)
            & (m["kw_nb_partiels"] == 0)
        ]
        c = st.columns(4)
        c[0].metric(
            "Mots-clés redondants",
            pct(cls.get("redondant", 0), n_kw),
            help=f"{int(cls.get('redondant', 0))} sur {n_kw} mots-clés évaluables",
        )
        c[1].metric(
            "Mots-clés complémentaires",
            pct(cls.get("complémentaire", 0), n_kw),
            help=f"{int(cls.get('complémentaire', 0))} sur {n_kw}",
        )
        c[2].metric(
            "Jeux sans vocabulaire nouveau",
            len(no_new),
            help="Jeux dont tous les mots-clés sont redondants avec les autres métadonnées",
        )
        c[3].metric(
            "Vocabulaire nouveau (médiane)",
            f"{m['kw_vocab_nouveau_pct'].median():.0f} %",
            help="Part des mots des mots-clés absents du reste des métadonnées, par jeu",
        )
        a, b = st.columns(2)
        with a:
            order = ["redondant", "partiel", "complémentaire"]
            cl = cls.reindex(order).fillna(0).astype(int)
            show(
                charts.donut(
                    cl.index,
                    cl.values,
                    title="Classe des mots-clés",
                    colors=[P_["muted"], P_["primary_mid"], P_["good"]],
                ),
                "kwc_donut",
            )
            reading(
                lambda: f"sur {n_kw} mots-clés, {int(cl['redondant'])} ({pct(cl['redondant'], n_kw)}) répètent des mots déjà présents ailleurs "
                f"et {int(cl['complémentaire'])} ({pct(cl['complémentaire'], n_kw)}) apportent un vocabulaire entièrement nouveau."
            )
        with b:
            labs = list(cfg.KW_REFERENCE_FIELDS)
            cnts = [
                int(kd["present_dans"].map(lambda l, lab=lab: lab in l).sum())
                for lab in labs
            ]
            show(
                charts.bar(
                    [f"… {lab}" for lab in labs],
                    [round(100 * c_ / n_kw, 1) for c_ in cnts],
                    title="Mots-clés entièrement présents dans… (%)",
                    suffix=" %",
                    color=P_["primary_mid"],
                    height=330,
                ),
                "kwc_fields",
            )
            reading(
                lambda: f"{pct(max(cnts), n_kw)} des mots-clés se retrouvent en entier dans « {labs[cnts.index(max(cnts))]} » ; "
                f"{int(kd['egal_thematique'].sum())} mot(s)-clé(s) sont identiques à une thématique. "
                f"Un mot-clé peut figurer dans plusieurs champs : les barres ne s'additionnent pas."
            )
        show(
            charts.histogram(
                m["kw_vocab_nouveau_pct"],
                nbins=20,
                title="Part de vocabulaire nouveau par jeu (%)",
                vlines=[
                    (P["kw_comp_low"], f"{P['kw_comp_low']} %"),
                    (P["kw_comp_high"], f"{P['kw_comp_high']} %"),
                ],
                xtitle="% des mots des mots-clés absents des autres métadonnées",
            ),
            "kwc_hist",
        )
        reading(
            lambda: f"{int((m['kw_vocab_nouveau_pct'] == 0).sum())} jeux sont à 0 % (aucun mot nouveau). "
            f"Entre les deux traits ({P['kw_comp_low']} à {P['kw_comp_high']} %), la complémentarité est jugée équilibrée dans le score : "
            f"{int(m['kw_vocab_nouveau_pct'].between(P['kw_comp_low'], P['kw_comp_high']).sum())} jeux s'y trouvent."
        )
        a, b = st.columns(2)
        with a:
            section("Mots-clés complémentaires les plus fréquents")
            comp_kw = (
                kd[kd["classe"] == "complémentaire"]
                .assign(cle=lambda d: d["mot_cle"].map(tk.norm_key))
                .groupby("cle")
                .agg(
                    Mot_clé=("mot_cle", lambda x: x.value_counts().index[0]),
                    Jeux=("jeu", "nunique"),
                )
                .sort_values("Jeux", ascending=False)
                .head(15)
                .reset_index(drop=True)
            )
            table(comp_kw)
        with b:
            section("Jeux sans vocabulaire nouveau")
            table(
                no_new[["titre", "kw_nb", "kw_vocab_nouveau_pct"]]
                .sort_values("kw_nb", ascending=False)
                .head(15),
                column_config={
                    "titre": "Titre",
                    "kw_nb": "Mots-clés",
                    "kw_vocab_nouveau_pct": "Vocabulaire nouveau (%)",
                },
            )

    st.divider()
    section("Mots-clés génériques et nombre de mots-clés")
    c = st.columns(4)
    c[0].metric(
        "Avec mots-clés génériques",
        int((m["kw_generiques"] > 0).sum()),
        help="Jeux contenant « données », « data », « opendata », « open data », « jeu de données » ou « dataset » "
        "(liste fixe, voir Méthodologie).",
    )
    c[1].metric("Sans mot-clé", int((m["kw_nb"] == 0).sum()))
    c[2].metric(
        f"Moins de {P['kw_min']} mots-clés",
        int(((m["kw_nb"] > 0) & (m["kw_nb"] < P["kw_min"])).sum()),
    )
    c[3].metric(
        f"Plus de {P['kw_max']} mots-clés", int((m["kw_nb"] > P["kw_max"]).sum())
    )
    note(
        f"Plage cible : {P['kw_min']} à {P['kw_max']} mots-clés par jeu (modifiable dans la barre latérale). "
        "Les trois dernières mesures sont exclusives : un jeu n'est compté que dans une seule."
    )
    section(
        "Mots-clés les plus répandus",
        sub="Part des jeux qui portent ce mot-clé (après normalisation). Un mot-clé présent partout "
        "discrimine peu : à surveiller, même s'il n'est pas « générique ».",
    )
    common = pd.DataFrame(
        [
            (k, v, round(100 * v / N, 1))
            for k, v in rep_kw["norm_counter"].most_common(10)
        ],
        columns=["Mot-clé", "Jeux", "% des jeux"],
    )
    table(
        common,
        column_config={
            "% des jeux": st.column_config.ProgressColumn(
                "% des jeux", min_value=0, max_value=100, format="%.1f"
            )
        },
    )

# =========================================================================== #
# 6. Licences, provenance & schémas
# =========================================================================== #
with tabs[5]:
    section(
        "Licences : avant / après regroupement",
        ["license"],
        "À gauche, les libellés tels que saisis ; à droite, regroupés par famille.",
    )
    a, b = st.columns(2)
    lr = vc(m["licence"])
    lf = vc(m["licence_famille"], metrics.LICENCE_ORDER)
    with a:
        show(
            charts.bar(
                lr.index, lr.values, title="Libellés saisis", color=charts.BEFORE_COLOR
            ),
            "lic_raw",
        )
        reading(
            lambda: f"le libellé « {lr.index[0]} » est utilisé par {int(lr.iloc[0])} jeux ({pct(lr.iloc[0], N)}) ; "
            f"{len(lr)} libellés différents (dont « non renseigné ») sont présents."
        )
    with b:
        show(
            charts.bar(
                lf.index,
                lf.values,
                title="Familles de licences",
                color=charts.AFTER_COLOR,
            ),
            "lic_fam",
        )
        reading(
            lambda: f"après regroupement, {len(lr)} libellés deviennent {len(lf)} familles ; "
            f"la famille « {lf.index[0]} » regroupe {int(lf.iloc[0])} jeux ({pct(lf.iloc[0], N)})."
        )
    no_ver = int((m["licence"].ne("") & ~m["licence_version_precisee"]).sum())
    st.caption(
        f"{no_ver} jeux ({pct(no_ver, N)}) ont une licence sans numéro de version (ex. « Licence Ouverte / Open Licence »)."
    )
    with st.expander("Comment les licences sont-elles regroupées ?"):
        classification_block("licence")
        st.caption(cfg.LICENCE_VERSION_RULE)

    st.divider()
    section(
        "Provenance",
        ["origin"],
        "Type déduit du champ `origin` (nom d'organisme ou URL).",
    )
    a, b = st.columns([2, 3])
    pv = vc(m["provenance_type"], metrics.PROVENANCE_ORDER)
    with a:
        show(charts.donut(pv.index, pv.values), "prov_donut")
        reading(
            lambda: f"{pct(pv.iloc[0], N)} des jeux ont une provenance « {pv.index[0]} » ({int(pv.iloc[0])} jeux)."
        )
    with b:
        top_all = vc(m["origine"])
        top = top_all.drop(metrics.NA_LABEL, errors="ignore").head(15)
        show(
            charts.bar(
                [x if len(x) < 60 else x[:57] + "…" for x in top.index],
                top.values,
                title="Origines les plus citées (valeur brute, hors non renseigné)",
                color=P_["primary_mid"],
            ),
            "prov_top",
        )
        reading(
            lambda: f"la valeur « {top.index[0][:60]} » est la plus citée : {int(top.iloc[0])} jeux. "
            f"{int(top_all.get(metrics.NA_LABEL, 0))} jeux n'ont aucune origine. "
            f"Les origines saisies différemment (casse, accents, URL) sont comptées séparément ici."
        )
    with st.expander(
        "Comment la provenance est-elle classée ? (règles, exemples, toutes les valeurs)"
    ):
        note(
            "Les règles sont appliquées dans l'ordre du tableau ; les exemples sont tirés de votre catalogue."
        )
        classification_block("provenance")
        st.caption(
            "Limite : la catégorie décrit d'où vient la donnée (le domaine de l'URL ou le nom saisi), pas toujours qui l'a produite. "
            "Un jeu de Grand Poitiers republié sur data.gouv.fr est classé « data.gouv.fr »."
        )
    with st.expander("Qu'est-ce que le « poids » d'une provenance ?"):
        st.markdown(
            "Quand on compte les jeux par provenance, **chaque jeu compte pour 1**. Or un jeu de 50 lignes et un jeu de 5 millions de lignes "
            "comptent pareil, de même qu'un jeu que personne n'utilise et un jeu réutilisé dans dix applications.\n\n"
            "**Pondérer**, c'est donner à chaque jeu un poids qui reflète son importance réelle avant d'additionner par provenance : "
            "nombre de lignes (`count`), taille (`storageSize`) ou nombre de réutilisations (`nbUsedInVirtual`, `nbApplications`). "
            "Exemple : si 10 jeux « INSEE » représentent 90 % du volume de données mais seulement 5 % des jeux, un comptage simple "
            "sous-estime fortement leur place dans le catalogue.\n\n"
            "Ces champs ne sont pas dans l'export actuel : **le poids est donc de 1 par jeu**. "
        )

    st.divider()
    section(
        "Propriétaire",
        ["owner"],
        "La colonne `owner` n'existe pas dans l'export actuel : elle est traitée comme vide.",
    )
    ow = vc(m["proprietaire_type"])
    docs_links(
        ["admin_jeux"], "📘 Propriétaire, visibilité et types de jeux dans Data Fair :"
    )
    show(charts.bar(ow.index, ow.values, color=P_["muted"], height=220), "owner_bar")
    reading(
        lambda: f"{int(ow.iloc[0])} jeux ({pct(ow.iloc[0], N)}) sont classés « {ow.index[0]} » : tant que `owner` n'est pas exporté, "
        f"cet indicateur ne peut pas distinguer les propriétaires."
    )
    if (m["proprietaire_nom"] != "").any():
        on = vc(m.loc[m["proprietaire_nom"] != "", "proprietaire_nom"])
        show(
            charts.bar(
                on.index,
                on.values,
                title="Jeux par propriétaire",
                color=P_["primary_mid"],
            ),
            "owner_names",
        )

    st.divider()
    section(
        "Schémas de données",
        ["conformsTo", "conformsToVersion", "conformsToUrl"],
        "Seule la déclaration de conformité est mesurable : l'export ne contient pas la structure des données.",
    )
    nd = int(m["schema_declare"].sum())
    c = st.columns(3)
    c[0].metric("Jeux déclarant un schéma", f"{nd} / {N}", help=pct(nd, N))
    c[1].metric(
        "Déclaration complète (nom + version + URL)", int(m["schema_complet"].sum())
    )
    c[2].metric("Sans schéma", f"{pct(N - nd, N)}")
    if nd:
        table(
            m.loc[m["schema_declare"], ["titre", "schema_nom", "schema_complet"]],
            column_config={
                "titre": "Titre",
                "schema_nom": "Schéma déclaré",
                "schema_complet": "Complet",
            },
        )

# =========================================================================== #
# 7. Spatial & temporel
# =========================================================================== #
with tabs[6]:
    section(
        "Couverture spatiale : avant / après regroupement",
        ["spatial"],
        "Libellés saisis (à gauche) et regroupement Grand Poitiers / Ville de Poitiers / autre commune (à droite).",
    )
    a, b = st.columns(2)
    sr = vc(m["spatial"])
    sr_f = sr.drop(metrics.NA_LABEL, errors="ignore")
    sty = vc(m["spatial_type"], metrics.SPATIAL_ORDER)
    with a:
        show(
            charts.bar(
                sr.index, sr.values, title="Libellés saisis", color=charts.BEFORE_COLOR
            ),
            "sp_raw",
        )

        def _sp_raw_reading():
            txt = (
                f"le libellé « {sr_f.index[0]} » est le plus utilisé : {int(sr_f.iloc[0])} jeux ({pct(sr_f.iloc[0], N)}) ; "
                f"{int(sr.get(metrics.NA_LABEL, 0))} jeux n'ont aucun libellé."
            )
            if {"Poitiers", "Ville de Poitiers"} <= set(sr_f.index):
                txt += " « Poitiers » et « Ville de Poitiers » sont deux libellés pour la même chose."
            return txt

        reading(_sp_raw_reading)
    with b:
        show(
            charts.bar(
                sty.index,
                sty.values,
                title="Type de couverture",
                color=charts.AFTER_COLOR,
            ),
            "sp_type",
        )
        reading(
            lambda: (
                f"{int(sty.get('Grand Poitiers (intercommunal)', 0))} jeux ({pct(sty.get('Grand Poitiers (intercommunal)', 0), N)}) couvrent "
                f"l'ensemble de Grand Poitiers, {int(sty.get('Ville de Poitiers', 0))} la seule ville de Poitiers, "
                f"{int(sty.get('Autre commune / territoire', 0))} une autre commune ; "
                f"{int(sty.get('Non renseigné', 0))} n'ont pas de couverture renseignée."
            )
        )
    with st.expander("Comment les libellés spatiaux sont-ils regroupés ?"):
        classification_block("spatial")

    section("Couverture spatiale × provenance")
    ct = pd.crosstab(m["spatial_type"], m["provenance_type"])
    ct = ct.reindex([x for x in metrics.SPATIAL_ORDER if x in ct.index])
    show(charts.stacked_bar(ct, horizontal=True, height=320), "sp_prov")

    def _sp_prov_reading():
        row = (
            "Grand Poitiers (intercommunal)"
            if "Grand Poitiers (intercommunal)" in ct.index
            else ct.index[0]
        )
        tot = int(ct.loc[row].sum())
        prov = ct.loc[row].idxmax()
        x = int(ct.loc[row, prov])
        other = (
            "data.gouv.fr (URL)"
            if "data.gouv.fr (URL)" in ct.columns
            else ct.columns[0]
        )
        return (
            f"parmi les {tot} jeux dont la couverture est « {row} », {x} ({pct(x, tot)}) ont une provenance « {prov} » "
            f"et {int(ct.loc[row, other])} une provenance « {other} »."
        )

    reading(_sp_prov_reading)

    st.divider()
    section(
        "Couverture temporelle",
        ["temporalStart", "temporalEnd"],
        "Peu renseignée : la complétude est l'information principale.",
    )
    a, b = st.columns([2, 3])
    tt = vc(m["temporel_type"], metrics.TEMPOREL_ORDER)
    with a:
        show(
            charts.bar(
                tt.index,
                tt.values,
                color=[
                    P_["muted"] if k == "Non renseignée" else P_["primary_mid"]
                    for k in tt.index
                ],
                height=320,
            ),
            "tmp_type",
        )
        reading(
            lambda: f"{int(tt.get('Non renseignée', 0))} jeux ({pct(tt.get('Non renseignée', 0), N)}) n'ont aucune couverture temporelle ; "
            f"{int(tt.get('Période close', 0))} ont une période close et {int(tt.get('Ponctuelle (début = fin)', 0))} une date unique."
        )
    with b:
        tl = charts.timeline(m, ref_date)
        if tl is not None:
            show(tl, "tmp_timeline")
            reading(
                lambda: "chaque barre est la période couverte par un jeu ; chaque losange rose est un jeu à date unique (début = fin). "
                f"Période couverte au total : de {m.loc[m['temporel_debut'] != '', 'temporel_debut'].min()[:4]} "
                f"à {m.loc[m['temporel_fin'] != '', 'temporel_fin'].max()[:4]}."
            )
        else:
            st.info("Aucun jeu avec une période renseignée.")

# =========================================================================== #
# 8. Mises à jour
# =========================================================================== #
with tabs[7]:
    section(
        "Dernière mise à jour des données",
        ["dataUpdatedAt", "frequency"],
        f"Date de référence : {ref_date:%d/%m/%Y}. Dernière mise à jour = `dataUpdatedAt` (les modifications de métadonnées n'y sont pas comptées).",
    )
    docs_links(
        ["contributeur"],
        "📘 Mises à jour automatiques : cours « Programmer des mises à jour automatiques de données » du",
    )
    n_never = int(m["jamais_mis_a_jour_depuis_creation"].sum())
    stale = m[m["statut_fraicheur"].isin(["En retard", "Très en retard"])]
    ev = m[m["statut_fraicheur"].isin(["À jour", "En retard", "Très en retard"])]
    c = st.columns(4)
    c[0].metric(
        "À jour (selon fréquence)",
        pct((ev["statut_fraicheur"] == "À jour").sum(), len(ev)),
        help=f"Sur {len(ev)} jeux évaluables",
    )
    c[1].metric("En retard", len(stale))
    c[2].metric(
        "Fréquence non évaluable",
        int(m["statut_fraicheur"].str.startswith("Non évaluable").sum()),
        help="Fréquence absente, irrégulière ou date inconnue.",
    )
    c[3].metric(
        "Jamais mis à jour depuis la création",
        n_never,
        help="Dernière mise à jour des données au plus 1 jour après la création du jeu (ou antérieure) : "
        "les données n'ont jamais été rechargées depuis la mise en ligne.",
    )

    a, b = st.columns(2)
    cats = [
        f"Mise à jour en {ref_year}",
        f"Mise à jour en {ref_year - 1}",
        f"Mise à jour avant {ref_year - 1}",
        "Date inconnue",
    ]
    cv = vc(m["categorie_maj"], cats)
    tv = vc(m["tranche_anciennete"], metrics.TRANCHES_ORDER)
    with a:
        show(
            charts.bar(
                cv.index,
                cv.values,
                title="Par catégorie de mise à jour",
                horizontal=False,
                color=[P_["good"], P_["primary_mid"], P_["warning"], P_["muted"]][
                    : len(cv)
                ],
            ),
            "up_cat",
        )
        reading(
            lambda: f"{int(cv.get(cats[0], 0))} jeux ont été mis à jour en {ref_year}, {int(cv.get(cats[1], 0))} en {ref_year - 1} "
            f"et {int(cv.get(cats[2], 0))} avant {ref_year - 1}."
        )
    with b:
        show(
            charts.bar(
                tv.index,
                tv.values,
                title="Par ancienneté",
                horizontal=False,
                color=P_["primary_mid"],
            ),
            "up_age",
        )
        reading(
            lambda: f"{pct(tv.get('≤ 1 mois', 0) + tv.get('1–6 mois', 0), N)} des jeux ont été mis à jour il y a moins de 6 mois ; "
            f"{pct(tv.get('1–2 ans', 0) + tv.get('> 2 ans', 0), N)} il y a plus d'un an."
        )

    present = [x for x in cfg.FREQUENCY_ORDER if x in set(m["frequence_libelle"])]
    others = sorted(set(m["frequence_libelle"]) - set(present) - {"Non renseignée"})
    f_order = (
        present
        + others
        + (
            ["Non renseignée"]
            if "Non renseignée" in set(m["frequence_libelle"])
            else []
        )
    )
    a, b = st.columns([2, 3])
    fv = vc(m["frequence_libelle"], f_order)
    ctf = pd.crosstab(m["frequence_libelle"], m["tranche_anciennete"])
    ctf = (
        ctf.reindex(
            index=f_order,
            columns=[c_ for c_ in metrics.TRANCHES_ORDER if c_ in ctf.columns],
        )
        .fillna(0)
        .astype(int)
    )
    with a:
        show(
            charts.bar(
                fv.index,
                fv.values,
                title="Fréquence de mise à jour déclarée",
                color=[
                    P_["muted"] if k == "Non renseignée" else P_["primary_mid"]
                    for k in fv.index
                ],
            ),
            "up_freq",
        )
        reading(
            lambda: f"{int(fv.get('Non renseignée', 0))} jeux ({pct(fv.get('Non renseignée', 0), N)}) ne déclarent aucune fréquence ; "
            f"{int(fv.get('Irrégulière', 0))} déclarent une fréquence « irrégulière »."
        )
    with b:
        show(charts.heatmap(ctf, title="Fréquence déclarée × ancienneté"), "up_heat")

        def _heat_reading():
            (f_, t_), n_ = ctf.stack().idxmax(), int(ctf.stack().max())
            return f"la case la plus remplie : {n_} jeux de fréquence « {f_} » dont la dernière mise à jour remonte à « {t_} »."

        reading(_heat_reading)

    section(
        "Fraîcheur réelle vs fréquence déclarée",
        sub="Chaque point est un jeu. Le trait indique le seuil de retard (intervalle attendu × tolérance + jours de grâce). "
        "Les fréquences en continu sont évaluées comme quotidiennes.",
    )
    show(charts.freshness_strip(m, P, f_order), "up_strip")
    reading(
        lambda: f"un point situé au-dessus du trait de sa colonne est un jeu en retard sur sa fréquence déclarée : "
        f"{len(stale)} jeux sont dans ce cas. Les colonnes sans trait (irrégulière, non renseignée) ne peuvent pas être évaluées."
    )

    sv = vc(m["statut_fraicheur"], metrics.STATUT_ORDER)
    show(
        charts.bar(
            sv.index,
            sv.values,
            title="Statut de fraîcheur",
            color=[charts.STATUS_COLORS.get(k, P_["muted"]) for k in sv.index],
            height=320,
        ),
        "up_status",
    )
    reading(
        lambda: f"{int(sv.get('À jour', 0))} jeux sont à jour, {int(sv.get('En retard', 0) + sv.get('Très en retard', 0))} en retard, "
        f"et {int(sv[[i for i in sv.index if i.startswith('Non évaluable')]].sum())} ne sont pas évaluables faute de fréquence exploitable ou de date."
    )

    section("Jeux en retard")
    if len(stale):
        table(
            stale.sort_values("retard_jours", ascending=False)[
                [
                    "titre",
                    "frequence_libelle",
                    "date_maj_donnees",
                    "jours_depuis_maj_donnees",
                    "retard_jours",
                    "statut_fraicheur",
                ]
            ],
            column_config={
                "titre": "Titre",
                "frequence_libelle": "Fréquence",
                "date_maj_donnees": "Dernière MAJ",
                "jours_depuis_maj_donnees": "Jours écoulés",
                "retard_jours": "Retard (jours)",
                "statut_fraicheur": "Statut",
            },
        )
    else:
        st.success("Aucun jeu en retard par rapport à sa fréquence déclarée.")

# =========================================================================== #
# 9. Jeux de données (explorateur)
# =========================================================================== #
with tabs[8]:
    section(
        "Explorateur",
        sub="Filtrez, triez, puis sélectionnez un jeu pour voir son profil détaillé.",
    )
    f1, f2, f3 = st.columns([2, 2, 3])
    q = f1.text_input("Recherche dans le titre")
    lo, hi = f2.slider("Score global", 0, 100, (0, 100))
    alert_kw = f3.text_input(
        "Alerte contient", placeholder="ex. « Licence », « doublon », « retard »"
    )
    ex = m[(m["score_global"].between(lo, hi))]
    if q:
        ex = ex[ex["titre"].str.contains(q, case=False, na=False, regex=False)]
    if alert_kw:
        ex = ex[ex["alertes"].str.contains(alert_kw, case=False, na=False, regex=False)]
    st.caption(f"{len(ex)} jeu(x)")
    cols = [
        "titre",
        "score_global",
        "niveau_qualite",
        *cfg.SCORE_LABELS.keys(),
        "nb_alertes",
        "alertes",
    ]
    cc = {
        "titre": "Titre",
        "niveau_qualite": "Niveau",
        "nb_alertes": "Alertes",
        "alertes": "Détail des alertes",
        "score_global": st.column_config.ProgressColumn(
            "Score", min_value=0, max_value=100, format="%.0f"
        ),
    }
    for k, lbl in cfg.SCORE_LABELS.items():
        cc[k] = st.column_config.NumberColumn(lbl, format="%.0f")
    table(ex.sort_values("score_global")[cols], height=380, column_config=cc)

    if len(ex):
        section("Profil d'un jeu de données")
        labels = {
            i: f"{r.titre}  ({r.score_global:.0f})"
            for i, r in ex.sort_values("score_global").iterrows()
        }
        pick = st.selectbox(
            "Jeu de données", list(labels), format_func=lambda i: labels[i]
        )
        r = m.loc[pick]
        a, b = st.columns([2, 3])
        with a:
            show(
                charts.radar({cfg.SCORE_LABELS[d]: r[d] for d in dims}, height=360),
                "ds_radar",
            )
            reading(
                lambda: "chaque axe est une dimension notée sur 100 : plus la surface colorée est grande, meilleur est le jeu. "
                f"Ici, point fort : « {cfg.SCORE_LABELS[max(dims, key=lambda d: r[d])]} » ; "
                f"point faible : « {cfg.SCORE_LABELS[min(dims, key=lambda d: r[d])]} »."
            )
        with b:
            st.markdown(f"**{r['titre']}**")
            st.metric(
                "Score global",
                f"{r['score_global']:.0f} / 100",
                help=r["niveau_qualite"],
            )
            st.markdown("**Alertes**" if r["nb_alertes"] else "✅ Aucune alerte")
            for al in [x for x in r["alertes"].split(" | ") if x]:
                st.markdown(f"- {al}")
            if r["page"]:
                st.markdown(f"[Voir sur le portail]({r['page']})")
        facts = pd.DataFrame(
            {
                "Indicateur": [
                    "Titre (car. / mots porteurs)",
                    "Description (mots)",
                    "Résumé (phrases)",
                    "FALC",
                    "Mots-clés (brut → normalisé)",
                    "Thématiques",
                    "Licence",
                    "Provenance",
                    "Couverture spatiale",
                    "Fréquence / dernière MAJ",
                ],
                "Valeur": [
                    f"{r['titre_nb_caracteres']} / {r['titre_nb_mots_porteurs']}",
                    f"{r['desc_nb_mots']}",
                    f"{r['resume_nb_phrases']}",
                    (
                        "n/a"
                        if pd.isna(r["falc_score"])
                        else f"{r['falc_score']:.0f}/100 · {r['falc_mots_par_phrase']} mots/phrase"
                    ),
                    f"{r['kw_nb_distincts_brut']} → {r['kw_nb_distincts_norm']}",
                    "; ".join(r["_tp_raw"]) or "-",
                    r["licence"] or "-",
                    f"{r['provenance_type']}",
                    f"{r['spatial'] or '-'} ({r['spatial_type']})",
                    f"{r['frequence_libelle']} / {r['date_maj_donnees'] or '-'} ({r['statut_fraicheur']})",
                ],
            }
        )
        table(facts)

# =========================================================================== #
# 10. Méthodologie
# =========================================================================== #
with tabs[9]:
    section("Principes")
    st.markdown(
        "- Les données sont analysées **telles quelles**. Les normalisations (mots-clés, thématiques, licences, couverture spatiale) "
        "ne servent qu'à mesurer ce qu'on gagnerait à les appliquer.\n"
        "- Un champ vide est un défaut mesuré, pas une donnée à exclure. Les colonnes absentes de l'export (ex. `owner`) sont créées vides, "
        "de sorte que les indicateurs fonctionneront dès qu'elles seront exportées.\n"
        "- Les seuils et pondérations sont modifiables dans la barre latérale ; les exports reflètent ces réglages.\n"
        "- Chaque graphique est accompagné d'une **clé de lecture** calculée automatiquement sur les données affichées."
    )

    section(
        "Score global et pondération actuelle",
        sub="Le score global est la moyenne pondérée des 7 scores par dimension. Un champ absent donne 0 à la dimension concernée.",
    )
    wt = pd.DataFrame(
        {
            "Dimension": [cfg.SCORE_LABELS[k] for k in cfg.SCORE_LABELS],
            "Poids actuel (%)": [
                round(100 * weights[k] / wsum, 1) for k in cfg.SCORE_LABELS
            ],
            "Calcul détaillé": [cfg.SCORE_FORMULA[k] for k in cfg.SCORE_LABELS],
        }
    )
    table(wt)

    section(
        "Vocabulaire : mots vides, mots creux, mots porteurs de sens, mots difficiles"
    )
    st.markdown(
        "- **Mot vide** : mot grammatical sans contenu propre (*de, la, des, pour, dans, et, que…*). Liste fixe, ci-dessous.\n"
        "- **Mot creux** : mot qui occupe de la place dans un titre ou une description sans dire de quoi on parle "
        "(*jeu, données, liste, tableau, fichier, contient, présente…*). Liste fixe, ci-dessous, établie par nos soins à partir de ce type de "
        "catalogue (`GENERIC_WORDS` dans `quality/config.py`).\n"
        "- **Mot porteur de sens** : mot d'au moins 3 lettres qui n'est ni un mot vide ni un mot creux. Les chiffres ne comptent pas. "
        "Comparaison sans accents ni casse.\n"
        "- **Mot long** (FALC) : mot d'au moins 4 syllabes. **Le guide FALC ne contient aucune règle sur la longueur des mots** : c'est un proxy choisi par le projet. "
        "Les syllabes sont estimées en comptant les groupes de voyelles consécutives (e muet final ignoré). Sur un test de 34 mots comptés à la main, "
        "20 sont exacts ; l'estimateur **sous-estime** (« création » compté 2 au lieu de 3, « situation » 3 au lieu de 4) et ne surestime jamais le "
        "caractère « long » : la part de mots longs affichée est donc plutôt un minimum.\n"
        "- **Mot rare / jargon** (FALC) : mot de fréquence *Zipf* inférieure à 3,0 en français, d'après la bibliothèque `wordfreq` "
        "(échelle logarithmique ; 3,0 ≈ 1 occurrence par million de mots). Les noms propres et sigles sortent souvent comme « rares ». "
        "Indicateur actif seulement si `wordfreq` est installé.\n"
        "- **Racine d'un mot** : mot sans accents ni casse, privé de son *s* ou *x* final (pluriel simple). Sert à rapprocher *élection* et *élections*. "
        "Les pluriels irréguliers (*animaux* / *animal*) et les synonymes ne sont pas rapprochés."
    )
    with st.expander(f"Liste des mots vides ({len(cfg.STOPWORDS)})"):
        st.write(", ".join(sorted(cfg.STOPWORDS)))
    with st.expander(f"Liste des mots creux ({len(cfg.GENERIC_WORDS)})"):
        st.write(", ".join(sorted(cfg.GENERIC_WORDS)))

    section("Mots-clés : génériques, complémentarité, plage")
    st.markdown(
        f"- **Mot-clé générique** : mot-clé qui, après normalisation, est égal à l'un de ceux de cette liste fixe, choisie par nos soins : "
        f"*{', '.join(sorted(cfg.GENERIC_KEYWORDS))}*. Sur votre catalogue actuel, aucun jeu n'en contient. "
        "Une approche complémentaire, par les données, est le tableau « mots-clés les plus répandus ».\n"
        "- **Complémentarité** (remplace l'ancien « ancrage dans le texte », qui traitait à tort un mot-clé absent du texte comme un défaut). "
        f"On décompose chaque mot-clé en racines de mots (hors mots vides) et on les cherche dans les racines des autres métadonnées : "
        f"{', '.join(cfg.KW_REFERENCE_FIELDS)}. Le mot-clé est **redondant** si toutes ses racines y figurent, **complémentaire** si aucune n'y figure, "
        "**partiel** sinon. Un mot-clé qui ne contient que des mots vides est ignoré.\n"
        "- **Vocabulaire nouveau d'un jeu** : part des racines de ses mots-clés absentes des autres métadonnées. "
        f"**Score de complémentarité** : pleine note entre {P['kw_comp_low']} et {P['kw_comp_high']} % de vocabulaire nouveau ; il monte de 0 à 100 "
        f"entre 0 et {P['kw_comp_low']} % ; il redescend jusqu'à 50 entre {P['kw_comp_high']} et 100 %. **Ce plateau est un choix du projet** : "
        "aucune référence ne dit quelle part de vocabulaire nouveau est idéale. Il pèse 25 % du score « mots-clés », soit environ 2 % du score global.\n"
        "- **Limites** : la comparaison est lexicale. « balades » n'est pas rapproché de « randonner » ni de « promenade », et un mot-clé complémentaire "
        "peut être aussi bien un synonyme utile qu'un terme hors sujet ou un simple libellé thématique (« finances »). La mesure ne juge pas la pertinence. "
        "Elle ne dit pas non plus si la recherche du portail porte sur les mots-clés, le titre ou la description : à vérifier sur votre portail.\n"
        f"- **Plage cible** : {P['kw_min']} à {P['kw_max']} mots-clés par jeu (modifiable). « Sans mot-clé », « moins de {P['kw_min']} » et "
        f"« plus de {P['kw_max']} » sont trois cas distincts et exclusifs."
    )

    section(
        "Règles de regroupement : provenance, couverture spatiale, licence",
        sub="Appliquées uniquement pour regrouper et mesurer. Les valeurs saisies ne sont jamais modifiées.",
    )
    st.markdown("**Provenance** (champ `origin`) : règles appliquées dans l'ordre")
    classification_block("provenance")
    st.caption(
        "Choix et limites : (1) seule une origine contenant « Grand Poitiers », ou égale à « Poitiers / Ville / Commune / Mairie de Poitiers », est "
        "« interne », on n'utilise pas « contient Poitiers » pour ne pas classer l'Université ou le CHU de Poitiers comme internes ; "
        "(2) les autres communes de l'agglomération sont classées « autre organisme » ; (3) un jeu de Grand Poitiers republié sur data.gouv.fr "
        "est classé « data.gouv.fr » ; (4) les valeurs peu informatives (« Jeux de données national ») tombent dans « autre organisme »."
    )
    st.markdown("**Couverture spatiale** (champ `spatial`)")
    classification_block("spatial")
    st.markdown("**Licence** (champ `license`)")
    classification_block("licence")
    st.caption(cfg.LICENCE_VERSION_RULE)

    section(
        "Fréquences de mise à jour",
        sub="Valeurs du champ `frequency` (vocabulaire Dublin Core utilisé par Data Fair) et traitement appliqué.",
    )
    fcount = raw_f["frequency"].fillna("").astype(str).str.strip().value_counts()
    rows_f = [
        (
            "(vide)",
            "Non renseignée",
            "-",
            "-",
            int(fcount.get("", 0)),
            "Non évaluable : le producteur n'a rien déclaré",
        )
    ]
    for code, (lbl, itv) in cfg.FREQUENCIES.items():
        n_ = int(fcount.get(code, 0))
        if n_ == 0 and code not in (
            "irregular",
            "continuous",
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "semiannual",
            "annual",
        ):
            continue
        thr = f"{itv * P['due_tolerance'] + P['due_grace_days']:.0f} j" if itv else "-"
        how = (
            "Non évaluable : mise à jour SANS rythme fixe, déclarée comme telle par le producteur, on ne peut donc pas parler de retard"
            if code == "irregular"
            else (
                "Évaluée comme quotidienne"
                if code == "continuous"
                else "Évaluée : retard si l'ancienneté dépasse le seuil"
            )
        )
        rows_f.append((code, lbl, f"{itv} j" if itv else "-", thr, n_, how))
    table(
        pd.DataFrame(
            rows_f,
            columns=[
                "Valeur dans l'export",
                "Libellé",
                "Intervalle attendu",
                "Seuil de retard",
                "Jeux",
                "Traitement",
            ],
        )
    )
    st.caption(
        "Seuil de retard = intervalle attendu × tolérance + jours de grâce (réglables). À jour ≤ seuil · en retard ≤ 2 × seuil · très en retard au-delà."
    )

    section("Référentiel FALC : ce que nous mesurons, comparé au guide officiel")
    st.markdown(
        "**Source vérifiée** : *L'information pour tous - règles européennes pour une information facile à lire et à comprendre* "
        "(Unapei / Inclusion Europe, édition 2009), lu en entier. Le guide est organisé en **5 sections par type de support** : règles générales "
        "(20 règles), informations écrites (42), électroniques (30), vidéo, audio. Pour un texte, il demande d'appliquer les sections 1 et 2. "
        "Les références ci-dessous se lisent « §1 r.14 » = section 1, règle 14.\n\n"
        "**Ce que nous n'avons pas consulté** : la liste de vérification officielle (plus de 50 questions, citée à la fin du guide) et les éventuelles "
        "versions plus récentes du guide. L'accès automatisé au site de l'Unapei étant bloqué, le texte lu est une copie hébergée par santetresfacile.fr.\n\n"
        "**Le tableau n'est pas exhaustif** : il reprend les règles du guide observables dans des champs texte, et signale pour chaque indicateur "
        "mesuré s'il correspond bien à une règle du guide. *Le référentiel exact à appliquer reste à arrêter avec le client.*"
    )
    fr_t = pd.DataFrame(
        cfg.FALC_RULES,
        columns=[
            "Famille",
            "Règle (reformulée)",
            "Réf. guide",
            "Statut",
            "Indicateur(s)",
            "Cohérence",
            "Remarque",
        ],
    )
    fr_t["Statut"] = fr_t["Statut"].map(cfg.FALC_STATUS_LABELS)
    fr_t["Cohérence"] = fr_t["Cohérence"].map(cfg.FALC_COHERENCE_LABELS)
    n_ok = int((fr_t["Cohérence"] == cfg.FALC_COHERENCE_LABELS["ok"]).sum())
    n_part = int((fr_t["Cohérence"] == cfg.FALC_COHERENCE_LABELS["partiel"]).sum())
    n_out = int((fr_t["Cohérence"] == cfg.FALC_COHERENCE_LABELS["hors_guide"]).sum())
    st.caption(
        f"Parmi les indicateurs mesurés : {n_ok} cohérents avec le guide, {n_part} partiels ou proxys, {n_out} absents du guide."
    )
    table(fr_t, height=520)
    st.markdown(
        "**Dans notre score FALC, ce qui ne vient pas du guide** (à valider ou à retirer avec le client) :"
    )
    for item in cfg.FALC_NOT_FROM_GUIDE:
        st.markdown(f"- {item}")

    section("Dictionnaire des indicateurs")
    table(
        pd.DataFrame(
            cfg.METRIC_DICT,
            columns=["Colonne(s) export", "Groupe", "Libellé", "Description"],
        ),
        height=520,
    )

    section("Références Data Fair")
    st.markdown(
        "- La **formule du `metadataScore`** (10 critères, 20 points) est décrite dans le fichier de schéma de métadonnées que vous avez fourni "
        "(champ `metadataScore`, visible dans l'onglet Complétude).\n"
        "- Les liens ci-dessous ont été vérifiés lors de la conception de ce tableau de bord ; le glossaire de la plateforme est accessible depuis "
        "l'accueil de la documentation."
    )
    docs_links(["accueil", "contributeur", "admin_jeux"], "📘")

    section("Limites connues")
    st.markdown(
        "- **Pas de vérification réelle de conformité aux schémas** : seule la déclaration `conformsTo` est mesurable.\n"
        "- **Couverture spatiale** : libellé texte uniquement (pas de géométrie dans l'export).\n"
        "- **Pas de « poids » de provenance** par volume ou réutilisation : chaque jeu compte pour 1 (voir l'explication dans l'onglet Licences, provenance & schémas).\n"
        "- **Les indicateurs de sens** (mots porteurs, complémentarité des mots-clés, nouveauté du résumé) reposent sur des listes de mots et "
        "une racinisation simple : ils signalent des pistes, pas des verdicts.\n"
        "- **FALC** : un score élevé n'est pas une labellisation FALC.\n"
        "- **Fraîcheur** : « en continu » est évalué comme quotidien ; « irrégulière » n'est pas évaluable.\n"
        "- **« Jamais mis à jour depuis la création »** dépend de `createdAt` : si les jeux ont été recréés lors d'une migration du portail, "
        "cet indicateur reflète la date de migration, pas celle de la première publication."
    )
