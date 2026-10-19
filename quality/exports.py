"""Construction des deux exports CSV (vue globale, vue par jeu de données)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SCORE_LABELS

# Ordre de lecture des colonnes de la vue par jeu
_FIRST = ["dataset_id", "titre", "page", "score_global", "niveau_qualite", *SCORE_LABELS.keys(),
          "nb_alertes", "alertes", "completude_pct", "nb_champs_vides", "champs_vides"]


def _tidy_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Colonnes décimales qui ne contiennent que des entiers (+ vides) -> entiers (pas de '207,0')."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            s = out[c].dropna()
            if len(s) and np.isfinite(s).all() and (s == s.round()).all():
                out[c] = out[c].round().astype("Int64")
    return out


def dataset_view(m: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par jeu de données, une colonne par indicateur (sans colonnes internes)."""
    cols = [c for c in m.columns if not c.startswith("_")]
    ordered = [c for c in _FIRST if c in cols] + [c for c in cols if c not in _FIRST]
    out = m[ordered].copy()
    if "page" in out and (out["page"] == "").all():
        out = out.drop(columns=["page"])
    for c in out.columns:  # booléens lisibles dans Excel
        if out[c].dtype == bool:
            out[c] = out[c].map({True: "oui", False: "non"})
    out = out.sort_values("score_global", ascending=True).reset_index(drop=True)
    return _tidy_numeric(out)


def global_view(g: pd.DataFrame) -> pd.DataFrame:
    """Vue globale (format long). `valeur` mêle comptages (entiers) et moyennes (décimaux)."""
    out = g.copy()

    def clean(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        if isinstance(v, (float, np.floating)) and float(v).is_integer():
            return int(v)
        return v

    out["valeur"] = pd.Series([clean(v) for v in out["valeur"]], index=out.index, dtype=object)
    return _tidy_numeric(out)


def to_csv_bytes(df: pd.DataFrame, excel_fr: bool = True) -> bytes:
    """CSV UTF-8 avec BOM. `excel_fr=True` : séparateur ';' et virgule décimale (ouverture directe dans Excel FR)."""
    sep, dec = (";", ",") if excel_fr else (",", ".")
    out = df.copy()
    for c in out.columns:  # colonnes 'object' contenant des décimaux (ex. `valeur`)
        if out[c].dtype == object:
            out[c] = out[c].map(
                lambda v: (f"{v:.2f}".rstrip("0").rstrip(".").replace(".", dec))
                if isinstance(v, (float, np.floating)) and not np.isnan(v) else v
            )
    return out.to_csv(index=False, sep=sep, decimal=dec).encode("utf-8-sig")
