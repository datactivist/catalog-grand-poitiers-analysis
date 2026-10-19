"""Calcul des indicateurs : vue par jeu de données, score composite, vue globale.

Principe : les données sont analysées TELLES QUELLES. Les normalisations (mots-clés, thématiques,
licences, couverture spatiale) ne servent qu'à mesurer ce qu'on gagnerait à les appliquer
("avant / après"), jamais à corriger les vues principales.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

import numpy as np
import pandas as pd

from . import textkit as tk
from .config import (
    FREQUENCIES, GENERIC_KEYWORDS, INTERNAL_ORIGIN_EXACT, INTERNAL_ORIGIN_SUBSTRINGS, INTERNAL_URL_DOMAINS,
    KW_REFERENCE_FIELDS, QUALITY_LEVELS, SCORE_LABELS,
)
from .loader import completeness_table, is_filled

NA_LABEL = "(non renseigné)"
TRANCHES_ORDER = ["≤ 1 mois", "1–6 mois", "6–12 mois", "1–2 ans", "> 2 ans", "Date inconnue"]
TEMPOREL_ORDER = ["Période close", "Ponctuelle (début = fin)", "Début seul (en cours)", "Fin seule",
                  "Incohérente (fin < début)", "Non renseignée"]
SPATIAL_ORDER = ["Grand Poitiers (intercommunal)", "Ville de Poitiers", "Autre commune / territoire", "Non renseigné"]
PROVENANCE_ORDER = ["Interne (Grand Poitiers / Ville de Poitiers)", "Autre organisme (nom cité)",
                    "data.gouv.fr (URL)", "Autre source web (URL)", "Non renseignée"]
LICENCE_ORDER = ["Licence Ouverte (Etalab)", "ODbL", "Creative Commons", "Autre licence", "Non renseignée"]
STATUT_ORDER = ["À jour", "En retard", "Très en retard", "Non évaluable (fréquence irrégulière)",
                "Non évaluable (fréquence non renseignée)", "Non évaluable (fréquence inconnue)",
                "Non évaluable (date inconnue)"]


# --------------------------------------------------------------------------- #
# Petites fonctions de classification (sur les valeurs brutes)
# --------------------------------------------------------------------------- #
def licence_family(label: str) -> str:
    k = tk.strip_accents(label.lower())
    if not k:
        return "Non renseignée"
    if "licence ouverte" in k or "open licence" in k or "etalab" in k:
        return "Licence Ouverte (Etalab)"
    if "odbl" in k or "open database" in k:
        return "ODbL"
    if "creative commons" in k or re.search(r"\bcc[- ]?by", k):
        return "Creative Commons"
    return "Autre licence"


def provenance_type(origin: str) -> str:
    """Règles détaillées dans config.PROVENANCE_RULES (affichées dans l'onglet Méthodologie)."""
    o = origin.strip()
    if not o:
        return "Non renseignée"
    k = tk.strip_accents(o.lower())
    internal = "Interne (Grand Poitiers / Ville de Poitiers)"
    if k.startswith(("http://", "https://", "www.")):
        if "data.gouv.fr" in k:
            return "data.gouv.fr (URL)"
        compact = k.replace("-", "").replace(" ", "")
        if any(d in compact for d in INTERNAL_URL_DOMAINS):
            return internal
        return "Autre source web (URL)"
    label = re.sub(r"\s+", " ", k).strip()
    if any(sub in label for sub in INTERNAL_ORIGIN_SUBSTRINGS) or label in INTERNAL_ORIGIN_EXACT:
        return internal
    return "Autre organisme (nom cité)"


def spatial_type(label: str) -> str:
    k = tk.strip_accents(label.lower()).strip()
    if not k:
        return "Non renseigné"
    if "grand poitiers" in k or re.search(r"\bcu\b|communaute urbaine|agglo", k):
        return "Grand Poitiers (intercommunal)"
    if re.fullmatch(r"(ville de |commune de )?poitiers", k):
        return "Ville de Poitiers"
    return "Autre commune / territoire"


def parse_owner(value: str) -> tuple[str, str]:
    """`owner` Data Fair peut être un JSON {type, name, ...} ou un simple texte."""
    v = value.strip()
    if not v:
        return "Non renseigné", ""
    if v.startswith("{"):
        try:
            import json

            d = json.loads(v)
            return str(d.get("type", "Non précisé")), str(d.get("name", d.get("id", "")))
        except Exception:
            pass
    return "Non précisé", v


def level_of(score: float) -> str:
    for thr, label in QUALITY_LEVELS:
        if score >= thr:
            return label
    return QUALITY_LEVELS[-1][1]


def _range_score(n: float, lo: float, hi: float) -> float:
    if n is None or np.isnan(n) or n <= 0:
        return 0.0
    if lo <= n <= hi:
        return 1.0
    return n / lo if n < lo else hi / n


def _c01(x) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    return float(min(1.0, max(0.0, x)))


def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.map(tk.clean_str).replace("", pd.NA), errors="coerce", utc=True, format="mixed")


def _near_duplicates(stem_sets: list[set], threshold: float) -> list[bool]:
    n = len(stem_sets)
    flags = [False] * n
    if n > 2500:  # garde-fou de performance
        return flags
    for i in range(n):
        a = stem_sets[i]
        if len(a) < 8:
            continue
        for j in range(i + 1, n):
            b = stem_sets[j]
            if len(b) < 8:
                continue
            inter = len(a & b)
            if inter and inter / len(a | b) >= threshold:
                flags[i] = flags[j] = True
    return flags


# --------------------------------------------------------------------------- #
# Vue par jeu de données
# --------------------------------------------------------------------------- #
def compute_dataset_metrics(df: pd.DataFrame, params: dict, ref_date: date) -> pd.DataFrame:
    n = len(df)
    P = params
    ref_ts = pd.Timestamp(ref_date, tz="UTC") + pd.Timedelta(days=1)

    S = {c: df[c].map(tk.clean_str) for c in df.columns}
    t_start, t_end = _to_dt(df["temporalStart"]), _to_dt(df["temporalEnd"])
    d_data, d_meta, d_create = _to_dt(df["dataUpdatedAt"]), _to_dt(df["updatedAt"]), _to_dt(df["createdAt"])

    title_keys = [tk.basic_key(t) for t in S["title"]]
    title_counts = Counter(k for k in title_keys if k)
    desc_clean = [tk.clean_markdown(d) for d in S["description"]]
    desc_keys = [tk.basic_key(d) for d in desc_clean]
    desc_counts = Counter(k for k in desc_keys if k)
    desc_stem_sets = [tk.meaningful_stems(d) for d in desc_clean]
    near_dup = _near_duplicates(desc_stem_sets, P["near_dup_threshold"])
    generic_kw_keys = {tk.norm_key(g) for g in GENERIC_KEYWORDS}

    fields = [f for f in P["completeness_fields"] if f in df.columns]
    filled_flags = pd.DataFrame({f: is_filled(df[f]).astype(int) for f in fields}) if fields else pd.DataFrame(index=df.index)

    rows = []
    for i in range(n):
        r: dict = {}
        id_val = S["id"].iat[i]
        r["dataset_id"] = id_val or f"ligne-{i + 1:04d}"
        r["titre"] = S["title"].iat[i]
        r["page"] = S["page"].iat[i]
        title, summary, desc = S["title"].iat[i], S["summary"].iat[i], S["description"].iat[i]

        # ---------------- Complétude ----------------
        if fields:
            flags = filled_flags.iloc[i]
            r["completude_pct"] = round(100 * flags.mean(), 1)
            empties = [f for f in fields if flags[f] == 0]
            r["nb_champs_vides"] = len(empties)
            r["champs_vides"] = "; ".join(empties)
            for f in fields:
                r[f"rempli_{f}"] = int(flags[f])
        else:
            r["completude_pct"], r["nb_champs_vides"], r["champs_vides"] = np.nan, 0, ""

        # ---------------- Titre ----------------
        tw = tk.word_analysis(title)
        nchar = len(title)
        letters = [c for c in title if c.isalpha()]
        upper_share = (sum(c.isupper() for c in letters) / len(letters)) if letters else 0.0
        technical = bool(
            re.search(r"_|\.(csv|xlsx?|json|geojson|shp|zip|xml)\b", title, re.I)
            or re.search(r"\b(test|brouillon|copie de|copy of|tmp)\b", title, re.I)
            or (title and " " not in title and "-" in title and len(title) > 15)
        )
        dup_title = bool(title_keys[i]) and title_counts[title_keys[i]] > 1
        r.update(
            titre_nb_caracteres=nchar,
            titre_nb_mots=len(tk.WORD_RE.findall(title)),
            titre_nb_mots_porteurs=len(tw["meaningful"]),
            titre_ratio_porteurs=round(tw["ratio"], 2) if not np.isnan(tw["ratio"]) else np.nan,
            titre_mots_non_porteurs="; ".join(tw["noise"]),
            titre_trop_court=bool(title) and nchar < P["title_min_chars"],
            titre_trop_long=nchar > P["title_max_chars"],
            titre_peu_informatif=bool(title) and len(tw["meaningful"]) < P["title_min_meaningful"],
            titre_technique=technical,
            titre_majuscules=bool(title) and len(letters) > 8 and upper_share > 0.6,
            titre_doublon=dup_title,
        )
        if title:
            meaning = _c01(len(tw["meaningful"]) / max(1, P["title_min_meaningful"])) * _c01(
                (0 if np.isnan(tw["ratio"]) else tw["ratio"]) / P.get("title_target_ratio", 0.4)
            )
            r["score_titre"] = round(100 * (
                0.25 * _range_score(nchar, P["title_min_chars"], P["title_max_chars"])
                + 0.45 * meaning + 0.15 * (0 if technical else 1) + 0.15 * (0 if dup_title else 1)), 1)
        else:
            r["score_titre"] = 0.0

        # ---------------- Résumé & description ----------------
        dw = tk.word_analysis(desc_clean[i])
        n_desc_words = len(tk.WORD_RE.findall(desc_clean[i]))
        title_stems = tk.meaningful_stems(title)
        cov_title = (len(title_stems & tk.all_stems(desc_clean[i])) / len(title_stems)) if (title_stems and desc) else np.nan
        sum_stems = tk.meaningful_stems(summary)
        novelty = (len(sum_stems - title_stems) / len(sum_stems)) if sum_stems else np.nan
        sum_sent = tk.count_sentences(summary) if summary else 0
        same_as_summary = bool(desc) and bool(summary) and tk.basic_key(summary) == desc_keys[i]
        exact_dup = bool(desc_keys[i]) and desc_counts[desc_keys[i]] > 1
        r.update(
            resume_nb_mots=len(tk.WORD_RE.findall(summary)),
            resume_nb_phrases=sum_sent,
            resume_trop_long=sum_sent > P["summary_max_sentences"],
            resume_nouveaute_vs_titre=round(novelty, 2) if not np.isnan(novelty) else np.nan,
            desc_nb_mots=n_desc_words,
            desc_courte=bool(desc) and n_desc_words < P["desc_min_words"],
            desc_nb_mots_porteurs=len(dw["meaningful"]),
            desc_ratio_porteurs=round(dw["ratio"], 2) if not np.isnan(dw["ratio"]) else np.nan,
            desc_doublon=exact_dup,
            desc_quasi_doublon=bool(exact_dup or near_dup[i]),
            desc_identique_resume=same_as_summary,
            desc_couverture_titre=round(cov_title, 2) if not np.isnan(cov_title) else np.nan,
        )
        if summary:
            sum_score = 0.4 + 0.3 * (sum_sent <= P["summary_max_sentences"]) + 0.3 * _c01(
                (0 if np.isnan(novelty) else novelty) / 0.4)
        else:
            sum_score = 0.0
        unique = 0.0 if (not desc or r["desc_quasi_doublon"] or same_as_summary) else 1.0
        r["score_description"] = round(100 * (
            0.30 * _c01(n_desc_words / P["desc_target_words"])
            + 0.15 * _c01((0 if np.isnan(dw["ratio"]) else dw["ratio"]) / P["desc_target_ratio"])
            + 0.15 * unique
            + 0.10 * _c01((0 if np.isnan(cov_title) else cov_title) / 0.5)
            + 0.30 * sum_score), 1)

        # ---------------- FALC (proxy) ----------------
        falc_text = desc if n_desc_words > 0 else summary
        fm = tk.falc_metrics(falc_text, P) if falc_text else None
        r["falc_source"] = ("description" if n_desc_words > 0 else "résumé") if fm else ""
        r.update(fm if fm else tk.FALC_EMPTY)
        r["score_falc"] = r["falc_score"] if fm else 0.0

        # ---------------- Thématiques (analysées avant les mots-clés : elles servent de référence) ----------------
        tp = tk.split_multi(S["topics"].iat[i])
        tp_keys = [tk.norm_key(t) for t in tp]
        r.update(topics_nb=len(tp), topics_nb_variantes=len(set(tp)) - len(set(tp_keys)))
        if not tp:
            tp_score = 0.0
        elif len(tp) <= P["topics_max"]:
            tp_score = 100.0
        else:
            tp_score = max(40.0, 100 - 25 * (len(tp) - P["topics_max"]))

        # ---------------- Mots-clés ----------------
        kw = tk.split_multi(S["keywords"].iat[i])
        kw_keys = [tk.norm_key(k) for k in kw]
        raw_distinct, norm_distinct = len(set(kw)), len(set(kw_keys))
        variantes = raw_distinct - norm_distinct

        # Complémentarité : le mot-clé ajoute-t-il du vocabulaire absent des autres métadonnées ?
        ref_stems = {
            lab: tk.all_stems(desc_clean[i] if col == "description" else S[col].iat[i])
            for lab, col in KW_REFERENCE_FIELDS.items()
        }
        ref_union = set().union(*ref_stems.values())
        topic_set = set(tp_keys)
        kw_detail, n_red, n_par, n_comp, new_roots, tot_roots = [], 0, 0, 0, 0, 0
        for k in kw:
            roots = tk.all_stems(k)
            if not roots:  # uniquement des mots vides : non évaluable
                continue
            present = sum(s_ in ref_union for s_ in roots)
            couv = present / len(roots)
            classe = "redondant" if couv >= 1 else ("complémentaire" if couv == 0 else "partiel")
            n_red += classe == "redondant"
            n_par += classe == "partiel"
            n_comp += classe == "complémentaire"
            new_roots += len(roots) - present
            tot_roots += len(roots)
            kw_detail.append({
                "mot_cle": k, "classe": classe, "couverture": couv,
                "present_dans": [lab for lab, ss in ref_stems.items() if all(s_ in ss for s_ in roots)],
                "egal_thematique": tk.norm_key(k) in topic_set,
            })
        new_pct = (100 * new_roots / tot_roots) if tot_roots else np.nan
        if np.isnan(new_pct):
            comp_sc = 0.0
        elif new_pct <= P["kw_comp_low"]:
            comp_sc = new_pct / P["kw_comp_low"] if P["kw_comp_low"] > 0 else 1.0
        elif new_pct <= P["kw_comp_high"]:
            comp_sc = 1.0
        else:
            comp_sc = 1 - 0.5 * (new_pct - P["kw_comp_high"]) / max(1e-9, 100 - P["kw_comp_high"])
        r.update(
            kw_nb=len(kw),
            kw_nb_distincts_brut=raw_distinct,
            kw_nb_distincts_norm=norm_distinct,
            kw_variantes_internes=variantes,
            kw_nb_redondants=n_red, kw_nb_partiels=n_par, kw_nb_complementaires=n_comp,
            kw_vocab_nouveau_pct=round(new_pct, 1) if not np.isnan(new_pct) else np.nan,
            kw_egaux_thematique=sum(d["egal_thematique"] for d in kw_detail),
            kw_complementarite_score=round(100 * comp_sc, 1),
            kw_generiques=sum(k in generic_kw_keys for k in kw_keys),
            kw_hors_plage=(len(kw) > 0 and not (P["kw_min"] <= len(kw) <= P["kw_max"])),
        )
        if kw:
            kw_score = 100 * (0.5 * _range_score(len(kw), P["kw_min"], P["kw_max"])
                              + 0.25 * (1 - variantes / max(1, raw_distinct))
                              + 0.25 * comp_sc)
        else:
            kw_score = 0.0
        r["score_mots_cles_themes"] = round(0.6 * kw_score + 0.4 * tp_score, 1)

        # ---------------- Licence / provenance / propriétaire / schéma ----------------
        lic = S["license"].iat[i]
        r["licence"] = lic
        r["licence_famille"] = licence_family(lic)
        r["licence_version_precisee"] = bool(re.search(r"\d", lic)) if lic else False
        origin = S["origin"].iat[i]
        r["origine"] = origin
        r["provenance_type"] = provenance_type(origin)
        o_type, o_name = parse_owner(S["owner"].iat[i])
        r["proprietaire_type"], r["proprietaire_nom"] = o_type, o_name
        ct, cv, cu = S["conformsTo"].iat[i], S["conformsToVersion"].iat[i], S["conformsToUrl"].iat[i]
        r["schema_declare"] = bool(ct)
        r["schema_nom"] = ct
        r["schema_complet"] = bool(ct and cv and cu)
        r["score_schema"] = 100.0 if r["schema_complet"] else (50.0 if ct else 0.0)

        # ---------------- Spatial / temporel ----------------
        sp = S["spatial"].iat[i]
        r["spatial"] = sp
        r["spatial_type"] = spatial_type(sp)
        ts_, te_ = t_start.iat[i], t_end.iat[i]
        hs, he = pd.notna(ts_), pd.notna(te_)
        if not hs and not he:
            tt = "Non renseignée"
        elif hs and not he:
            tt = "Début seul (en cours)"
        elif he and not hs:
            tt = "Fin seule"
        elif te_ < ts_:
            tt = "Incohérente (fin < début)"
        elif te_ == ts_:
            tt = "Ponctuelle (début = fin)"
        else:
            tt = "Période close"
        r["temporel_type"] = tt
        r["temporel_debut"] = ts_.date().isoformat() if hs else ""
        r["temporel_fin"] = te_.date().isoformat() if he else ""
        r["temporel_duree_jours"] = int((te_ - ts_).days) if (hs and he and te_ >= ts_) else np.nan

        # ---------------- Mises à jour ----------------
        code = S["frequency"].iat[i]
        if code in FREQUENCIES:
            f_label, interval = FREQUENCIES[code]
        else:
            f_label, interval = (code if code else "Non renseignée"), None
        r["frequence"], r["frequence_libelle"], r["frequence_jours_attendus"] = code, f_label, interval if interval else np.nan
        du = d_data.iat[i]
        if pd.isna(du):
            days = np.nan
            cat, tranche = "Date inconnue", "Date inconnue"
        else:
            days = max(0, int((ref_ts - du).total_seconds() // 86400))
            y = min(du.year, ref_date.year)
            cat = (f"Mise à jour en {ref_date.year}" if y == ref_date.year
                   else f"Mise à jour en {ref_date.year - 1}" if y == ref_date.year - 1
                   else f"Mise à jour avant {ref_date.year - 1}")
            tranche = ("≤ 1 mois" if days <= 30 else "1–6 mois" if days <= 183 else "6–12 mois" if days <= 365
                       else "1–2 ans" if days <= 730 else "> 2 ans")
        r["date_maj_donnees"] = du.date().isoformat() if pd.notna(du) else ""
        r["jours_depuis_maj_donnees"] = days
        r["categorie_maj"], r["tranche_anciennete"] = cat, tranche
        dm = d_meta.iat[i]
        r["jours_depuis_maj_metadonnees"] = max(0, int((ref_ts - dm).total_seconds() // 86400)) if pd.notna(dm) else np.nan
        dc = d_create.iat[i]
        r["jamais_mis_a_jour_depuis_creation"] = bool(pd.notna(du) and pd.notna(dc) and (du - dc) <= pd.Timedelta(days=1))
        if pd.isna(du):
            statut, retard, fresh = "Non évaluable (date inconnue)", np.nan, 0.0
        elif interval is None:
            statut = ("Non évaluable (fréquence irrégulière)" if code == "irregular"
                      else "Non évaluable (fréquence non renseignée)" if not code
                      else "Non évaluable (fréquence inconnue)")
            retard = np.nan
            fresh = float(np.interp(days, [0, 180, 365, 730, 1095], [100, 100, 75, 40, 0]))
        else:
            due = interval * P["due_tolerance"] + P["due_grace_days"]
            retard = max(0.0, days - due)
            statut = "À jour" if days <= due else ("En retard" if days <= 2 * due else "Très en retard")
            fresh = 100.0 if days <= due else float(np.clip(100 * (1 - (days - due) / (2 * due)), 0, 100))
        r["statut_fraicheur"], r["retard_jours"] = statut, (round(retard) if not pd.isna(retard) else np.nan)
        r["score_fraicheur"] = round(fresh, 1)
        r["score_natif_data_fair"] = pd.to_numeric(S["metadataScore"].iat[i], errors="coerce")

        # ---------------- Alertes ----------------
        al = []
        if not title:
            al.append("Titre absent")
        else:
            if r["titre_trop_court"]:
                al.append(f"Titre trop court (< {P['title_min_chars']} caractères)")
            if r["titre_trop_long"]:
                al.append(f"Titre trop long (> {P['title_max_chars']} caractères)")
            if r["titre_peu_informatif"]:
                al.append("Titre peu informatif (peu de mots porteurs de sens)")
            if technical:
                al.append("Titre technique (séparateurs _, extension…)")
            if r["titre_majuscules"]:
                al.append("Titre en capitales")
            if dup_title:
                al.append("Titre en doublon")
        if not desc:
            al.append("Description absente")
        else:
            if r["desc_courte"]:
                al.append(f"Description courte (< {P['desc_min_words']} mots)")
            if r["desc_quasi_doublon"]:
                al.append("Description dupliquée / quasi identique à un autre jeu")
            if same_as_summary:
                al.append("Description identique au résumé")
        if not summary:
            al.append("Résumé absent")
        else:
            if r["resume_trop_long"]:
                al.append(f"Résumé trop long (> {P['summary_max_sentences']} phrases)")
            if not np.isnan(novelty) and novelty < 0.2:
                al.append("Résumé qui répète le titre")
        if fm and r["falc_score"] < 50:
            al.append("Texte difficile à lire (proxy FALC < 50)")
        if not kw:
            al.append("Mots-clés absents")
        else:
            if len(kw) < P["kw_min"]:
                al.append(f"Peu de mots-clés (< {P['kw_min']})")
            elif len(kw) > P["kw_max"]:
                al.append(f"Trop de mots-clés (> {P['kw_max']})")
            if variantes > 0:
                al.append(f"Mots-clés en variantes ({variantes})")
            if r["kw_generiques"] > 0:
                al.append("Mots-clés génériques")
            if (n_red + n_par + n_comp) > 0 and n_comp == 0 and n_par == 0:
                al.append("Mots-clés sans vocabulaire nouveau (tous déjà présents ailleurs dans les métadonnées)")
        if not tp:
            al.append("Thématique absente")
        elif len(tp) > P["topics_max"]:
            al.append(f"Trop de thématiques (> {P['topics_max']})")
        if not lic:
            al.append("Licence absente")
        elif not r["licence_version_precisee"]:
            al.append("Licence sans version")
        if not origin:
            al.append("Provenance absente")
        if not code:
            al.append("Fréquence de mise à jour absente")
        if not sp:
            al.append("Couverture spatiale absente")
        if tt.startswith("Incohérente"):
            al.append("Couverture temporelle incohérente")
        if statut in ("En retard", "Très en retard"):
            al.append(f"Mise à jour {statut.lower()} ({days} j, fréquence {f_label.lower()})")
        r["nb_alertes"], r["alertes"] = len(al), " | ".join(al)

        # Colonnes internes (listes) pour les vues avant/après
        r["_kw_raw"], r["_kw_keys"], r["_tp_raw"], r["_tp_keys"] = kw, kw_keys, tp, tp_keys
        r["_kw_detail"] = kw_detail
        r["_titre_bruit"] = tw["noise"]
        rows.append(r)

    m = pd.DataFrame(rows)
    m.index = df.index
    return m


def apply_scores(m: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Score global = moyenne pondérée des scores par dimension (pondérations normalisées)."""
    m = m.copy()
    w = pd.Series({k: float(v) for k, v in weights.items() if k in SCORE_LABELS and k in m.columns})
    if w.sum() <= 0:
        w[:] = 1.0
    w = w / w.sum()
    m["score_completude"] = m["completude_pct"].fillna(0.0)
    m["score_global"] = (m[list(w.index)].fillna(0.0) * w).sum(axis=1).round(1)
    m["niveau_qualite"] = m["score_global"].map(level_of)
    return m


# --------------------------------------------------------------------------- #
# Avant / après normalisation
# --------------------------------------------------------------------------- #
def normalization_report(lists: list[list[str]], key_fn=tk.norm_key) -> dict:
    raw_counter, key_counter = Counter(), Counter()
    variants: dict[str, Counter] = defaultdict(Counter)
    per_raw, per_norm = [], []
    for lst in lists:
        raw_set = set(lst)
        keys = {key_fn(x) for x in raw_set}
        raw_counter.update(raw_set)
        key_counter.update(keys)
        for x in raw_set:
            variants[key_fn(x)][x] += 1
        per_raw.append(len(raw_set))
        per_norm.append(len(keys))
    canon = {k: v.most_common(1)[0][0] for k, v in variants.items()}
    clusters = pd.DataFrame([
        {"cle_normalisee": k, "forme_retenue": canon[k],
         "variantes": " ; ".join(f"{v} ({c})" for v, c in variants[k].most_common()),
         "n_variantes": len(variants[k]), "jeux_concernes": key_counter[k]}
        for k in key_counter
    ])
    if clusters.empty:
        clusters = pd.DataFrame(columns=["cle_normalisee", "forme_retenue", "variantes", "n_variantes", "jeux_concernes"])
    d_raw, d_norm = len(raw_counter), len(key_counter)
    hap_raw = sum(1 for c in raw_counter.values() if c == 1)
    hap_norm = sum(1 for c in key_counter.values() if c == 1)
    stats = {
        "occurrences": int(sum(per_raw)),
        "distincts_brut": d_raw, "distincts_norm": d_norm,
        "reduction_pct": round(100 * (d_raw - d_norm) / d_raw, 1) if d_raw else 0.0,
        "hapax_brut": hap_raw, "hapax_norm": hap_norm,
        "hapax_pct_brut": round(100 * hap_raw / d_raw, 1) if d_raw else 0.0,
        "hapax_pct_norm": round(100 * hap_norm / d_norm, 1) if d_norm else 0.0,
        "moy_par_jeu_brut": round(float(np.mean(per_raw)), 2) if per_raw else 0.0,
        "moy_par_jeu_norm": round(float(np.mean(per_norm)), 2) if per_norm else 0.0,
        "jeux_avec_variantes": int(sum(a > b for a, b in zip(per_raw, per_norm))),
        "n_variantes_multiples": int((clusters["n_variantes"] > 1).sum()) if len(clusters) else 0,
    }
    return {
        "stats": stats,
        "raw_counter": raw_counter,
        "norm_counter": Counter({canon[k]: c for k, c in key_counter.items()}),
        "clusters": clusters.sort_values(["n_variantes", "jeux_concernes"], ascending=False).reset_index(drop=True),
        "per_dataset_raw": per_raw, "per_dataset_norm": per_norm,
    }


# --------------------------------------------------------------------------- #
# Vue globale (format long) : une ligne par indicateur / modalité
# --------------------------------------------------------------------------- #
def _stat(rows, groupe, indic, valeur, unite="", modalite="", total=None):
    pct = round(100 * valeur / total, 1) if (total and unite in ("jeux de données", "mots-clés")) else np.nan
    rows.append(dict(groupe=groupe, indicateur=indic, modalite=modalite,
                     valeur=(round(float(valeur), 2) if isinstance(valeur, (float, np.floating)) else valeur),
                     unite=unite, total_reference=total if total is not None else np.nan, pourcentage=pct))


def _dist(rows, groupe, indic, series: pd.Series, order=None, total=None):
    s = series.replace("", NA_LABEL).fillna(NA_LABEL).astype(str)
    total = total if total is not None else len(s)
    vc = s.value_counts()
    if order:
        idx = [o for o in order if o in vc.index] + [x for x in vc.index if x not in order]
        vc = vc.reindex(idx)
    for mod, c in vc.items():
        _stat(rows, groupe, indic, int(c), "jeux de données", mod, total)


def _dist_num(rows, groupe, indic, series: pd.Series, total=None):
    total = total if total is not None else len(series)
    for mod, c in series.dropna().astype(int).value_counts().sort_index().items():
        _stat(rows, groupe, indic, int(c), "jeux de données", str(mod), total)


def _flag(rows, groupe, indic, series: pd.Series, total=None):
    total = total if total is not None else len(series)
    _stat(rows, groupe, indic, int(series.fillna(False).astype(bool).sum()), "jeux de données", "", total)


def _describe(rows, groupe, indic, series: pd.Series, unite):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return
    for stat, val in (("moyenne", s.mean()), ("médiane", s.median()), ("min", s.min()), ("max", s.max())):
        _stat(rows, groupe, indic, float(val), unite, stat)


def compute_global(m: pd.DataFrame, raw: pd.DataFrame, schema: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Vue globale du catalogue : pour chaque indicateur, ses scores / valeurs (format long)."""
    rows: list[dict] = []
    N = len(m)
    G = "Général"
    _stat(rows, G, "nombre_jeux_donnees", N, "jeux de données", total=N)
    _stat(rows, G, "score_global_moyen", float(m["score_global"].mean()) if N else np.nan, "points /100")
    _stat(rows, G, "score_global_median", float(m["score_global"].median()) if N else np.nan, "points /100")
    for dim, label in SCORE_LABELS.items():
        if dim in m.columns:
            _stat(rows, G, "score_moyen_par_dimension", float(m[dim].mean()) if N else np.nan, "points /100", dim)
    _dist(rows, G, "repartition_niveau_qualite", m["niveau_qualite"], order=[lv for _, lv in QUALITY_LEVELS])
    _stat(rows, G, "score_natif_data_fair_moyen", float(m["score_natif_data_fair"].mean()), "points /100")

    # Complétude : tous les attributs
    C = "Complétude"
    comp = completeness_table(raw, schema)
    for r in comp.itertuples():
        _stat(rows, C, "taux_completude", int(r.remplis), "jeux de données", r.champ, int(r.total))
    _stat(rows, C, "completude_moyenne_par_jeu (champs retenus)", float(m["completude_pct"].mean()) if N else np.nan, "%")

    # Propriétaire
    _dist(rows, "Propriétaire", "jeux_par_type_proprietaire", m["proprietaire_type"])
    owners = m.loc[m["proprietaire_nom"] != "", "proprietaire_nom"]
    if len(owners):
        _dist(rows, "Propriétaire", "jeux_par_proprietaire", owners, total=N)

    # Titre
    T = "Titre"
    _describe(rows, T, "nombre_caracteres_titre", m["titre_nb_caracteres"], "caractères")
    _describe(rows, T, "nombre_mots_titre", m["titre_nb_mots"], "mots")
    _describe(rows, T, "nombre_mots_porteurs_titre", m["titre_nb_mots_porteurs"], "mots")
    _stat(rows, T, "seuil_titre_trop_court", params["title_min_chars"], "caractères")
    for col, ind in [("titre_trop_court", "titres_trop_courts"), ("titre_trop_long", "titres_trop_longs"),
                     ("titre_peu_informatif", "titres_peu_informatifs"), ("titre_technique", "titres_techniques"),
                     ("titre_majuscules", "titres_en_capitales"), ("titre_doublon", "titres_en_doublon")]:
        _flag(rows, T, ind, m[col], N)

    # Description & résumé
    D = "Description & résumé"
    _describe(rows, D, "nombre_mots_description", m["desc_nb_mots"], "mots")
    _stat(rows, D, "seuil_description_trop_courte", params["desc_min_words"], "mots")
    _stat(rows, D, "descriptions_absentes", int((m["desc_nb_mots"] == 0).sum()), "jeux de données", total=N)
    for col, ind in [("desc_courte", "descriptions_trop_courtes"), ("desc_doublon", "descriptions_en_doublon_exact"),
                     ("desc_quasi_doublon", "descriptions_quasi_doublons"), ("desc_identique_resume", "descriptions_identiques_au_resume"),
                     ("resume_trop_long", "resumes_trop_longs")]:
        _flag(rows, D, ind, m[col], N)
    _describe(rows, D, "densite_sens_description", m["desc_ratio_porteurs"], "ratio")
    _describe(rows, D, "couverture_titre_dans_description", m["desc_couverture_titre"], "ratio")
    _describe(rows, D, "information_nouvelle_resume_vs_titre", m["resume_nouveaute_vs_titre"], "ratio")
    _dist_num(rows, D, "repartition_nombre_phrases_resume", m["resume_nb_phrases"])

    # FALC
    F = "Lisibilité FALC (proxy)"
    for col, unite in [("falc_score", "points /100"), ("falc_mots_par_phrase", "mots/phrase"),
                       ("falc_pct_phrases_longues", "%"), ("falc_pct_mots_longs", "%"),
                       ("falc_sigles_pour_100_mots", "sigles/100 mots"), ("falc_flesch_fr", "indice"),
                       ("falc_pct_mots_rares", "%")]:
        _describe(rows, F, col, m[col], unite)
    _flag(rows, F, "textes_score_falc_inferieur_50", m["falc_score"].lt(50), N)

    # Licence
    L = "Licence"
    _dist(rows, L, "jeux_par_licence (libellé brut)", m["licence"])
    _dist(rows, L, "jeux_par_famille_de_licence (après regroupement)", m["licence_famille"], order=LICENCE_ORDER)
    _stat(rows, L, "licences_sans_version", int((m["licence"].ne("") & ~m["licence_version_precisee"]).sum()),
          "jeux de données", total=N)

    # Provenance
    _dist(rows, "Provenance", "jeux_par_type_provenance", m["provenance_type"], order=PROVENANCE_ORDER)

    # Thématiques
    TH = "Thématiques"
    rep_tp = normalization_report(list(m["_tp_raw"]))
    for lbl, c in rep_tp["raw_counter"].most_common():
        _stat(rows, TH, "jeux_par_thematique (brut)", int(c), "jeux de données", lbl, N)
    for lbl, c in rep_tp["norm_counter"].most_common():
        _stat(rows, TH, "jeux_par_thematique (après normalisation)", int(c), "jeux de données", lbl, N)
    _dist_num(rows, TH, "repartition_nombre_de_thematiques_par_jeu", m["topics_nb"])
    for k, v in rep_tp["stats"].items():
        _stat(rows, TH, f"normalisation_{k}", v)

    # Mots-clés
    K = "Mots-clés"
    rep = normalization_report(list(m["_kw_raw"]))
    for k, v in rep["stats"].items():
        _stat(rows, K, f"normalisation_{k}", v)
    _dist_num(rows, K, "repartition_jeux_par_nombre_de_mots_cles", m["kw_nb"])
    _dist_num(rows, K, "repartition_jeux_par_nombre_de_mots_cles_distincts_apres_normalisation", m["kw_nb_distincts_norm"])
    for lbl, c in rep["raw_counter"].most_common():
        _stat(rows, K, "occurrences_mot_cle (brut)", int(c), "jeux de données", lbl, N)
    for lbl, c in rep["norm_counter"].most_common():
        _stat(rows, K, "occurrences_mot_cle (après normalisation)", int(c), "jeux de données", lbl, N)

    # Complémentarité des mots-clés avec les autres métadonnées
    details = [d for lst in m["_kw_detail"] for d in lst]
    n_eval = len(details)
    for classe in ("redondant", "partiel", "complémentaire"):
        _stat(rows, K, "complementarite_mots_cles_par_classe", sum(d["classe"] == classe for d in details), "mots-clés", classe, n_eval)
    for lab in KW_REFERENCE_FIELDS:
        _stat(rows, K, "mots_cles_entierement_presents_dans", sum(lab in d["present_dans"] for d in details), "mots-clés", lab, n_eval)
    _stat(rows, K, "mots_cles_egaux_a_une_thematique", sum(d["egal_thematique"] for d in details), "mots-clés", "", n_eval)
    _describe(rows, K, "vocabulaire_nouveau_par_jeu", m["kw_vocab_nouveau_pct"], "%")
    _stat(rows, K, "jeux_sans_vocabulaire_nouveau",
          int(((m["kw_nb_redondants"] + m["kw_nb_partiels"] + m["kw_nb_complementaires"] > 0)
               & (m["kw_nb_complementaires"] == 0) & (m["kw_nb_partiels"] == 0)).sum()), "jeux de données", "", N)

    # Fréquence & mises à jour
    U = "Mises à jour"
    _dist(rows, U, "repartition_par_frequence_de_mise_a_jour", m["frequence_libelle"])
    _dist(rows, U, "repartition_par_categorie_derniere_maj", m["categorie_maj"])
    _dist(rows, U, "repartition_par_anciennete", m["tranche_anciennete"], order=TRANCHES_ORDER)
    _dist(rows, U, "repartition_par_statut_fraicheur", m["statut_fraicheur"], order=STATUT_ORDER)
    cross = m.assign(_x=m["frequence_libelle"] + " | " + m["tranche_anciennete"])
    _dist(rows, U, "croisement_frequence_x_anciennete", cross["_x"])
    _flag(rows, U, "jeux_jamais_mis_a_jour_depuis_creation", m["jamais_mis_a_jour_depuis_creation"], N)

    # Spatial & temporel
    SP = "Couverture spatiale"
    _dist(rows, SP, "repartition_par_libelle_spatial (brut)", m["spatial"])
    _dist(rows, SP, "repartition_par_type_de_couverture (après regroupement)", m["spatial_type"], order=SPATIAL_ORDER)
    _dist(rows, "Couverture temporelle", "repartition_par_type_de_couverture_temporelle", m["temporel_type"], order=TEMPOREL_ORDER)

    # Schéma
    SC = "Schémas de données"
    _stat(rows, SC, "jeux_declarant_un_schema", int(m["schema_declare"].sum()), "jeux de données", total=N)
    _stat(rows, SC, "jeux_schema_complet (nom+version+url)", int(m["schema_complet"].sum()), "jeux de données", total=N)
    _dist(rows, SC, "jeux_par_schema_declare", m.loc[m["schema_declare"], "schema_nom"], total=N)

    out = pd.DataFrame(rows, columns=["groupe", "indicateur", "modalite", "valeur", "unite", "total_reference", "pourcentage"])
    return out
