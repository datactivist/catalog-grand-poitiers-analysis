"""Chargement du catalogue et du schéma de métadonnées, sans aucune correction des données."""

from __future__ import annotations

import io
import re
from typing import IO

import pandas as pd

from .config import EXPECTED_COLUMNS


def _read_csv(source, **kwargs) -> pd.DataFrame:
    """Lit un CSV (chemin, fichier uploadé ou bytes) en essayant plusieurs encodages / séparateurs."""
    if hasattr(source, "read"):
        raw = source.read()
    elif isinstance(source, (bytes, bytearray)):
        raw = bytes(source)
    else:
        with open(source, "rb") as fh:
            raw = fh.read()
    last_err = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError as err:
            last_err = err
            continue
        header = text.split("\n", 1)[0]
        sep = ";" if header.count(";") > header.count(",") else ","
        return pd.read_csv(
            io.StringIO(text), sep=sep, dtype=str, keep_default_na=True, **kwargs
        )
    raise ValueError(f"Impossible de décoder le fichier : {last_err}")


def load_catalogue(source) -> pd.DataFrame:
    """Charge le catalogue tel quel. Les colonnes attendues mais absentes sont créées vides
    (ex. `owner`) afin que tous les indicateurs soient calculables dès qu'elles apparaîtront.
    """
    df = _read_csv(source)
    df.columns = [c.strip() for c in df.columns]
    df.attrs["columns_in_export"] = list(df.columns)
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df.reset_index(drop=True)
    return df


def _dedupe_group(value) -> str:
    """Corrige les groupes dupliqués du schéma ('Propriété & visibilitéPropriété & visibilité')."""
    if not isinstance(value, str):
        return ""
    v = value.strip()
    half = len(v) // 2
    if half and len(v) % 2 == 0 and v[:half] == v[half:]:
        return v[:half]
    return v


def load_schema(source) -> pd.DataFrame:
    sch = _read_csv(source)
    sch.columns = [c.strip() for c in sch.columns]
    rename = {
        "Groupe": "groupe",
        "Clé": "cle",
        "Libellé": "libelle",
        "Type": "type",
        "Description": "description",
    }
    sch = sch.rename(columns=rename)
    for col in ["groupe", "cle", "libelle", "type", "description"]:
        if col not in sch.columns:
            sch[col] = ""
    sch["groupe"] = sch["groupe"].map(_dedupe_group)
    for col in ["cle", "libelle", "type", "description"]:
        sch[col] = sch[col].fillna("").astype(str).str.strip()
    return sch[["groupe", "cle", "libelle", "type", "description"]].reset_index(
        drop=True
    )


def schema_hints(schema: pd.DataFrame) -> dict[str, str]:
    """clé -> 'Libellé (Type) - Description' pour les infobulles."""
    hints = {}
    for r in schema.itertuples():
        txt = f"{r.libelle or r.cle} ({r.type})" if r.type else (r.libelle or r.cle)
        if r.description:
            txt += f" - {r.description}"
        hints[r.cle] = txt
    return hints


def is_filled(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype(str).str.strip() != "")


def completeness_table(df: pd.DataFrame, schema: pd.DataFrame) -> pd.DataFrame:
    """Taux de remplissage de CHAQUE attribut (colonnes de l'export + colonnes attendues absentes)."""
    in_export = set(df.attrs.get("columns_in_export", df.columns))
    sch = schema.set_index("cle")
    rows = []
    for col in df.columns:
        n = len(df)
        filled = int(is_filled(df[col]).sum())
        info = sch.loc[col] if col in sch.index else None
        rows.append(
            {
                "champ": col,
                "libelle": (info["libelle"] if info is not None else col),
                "groupe": (info["groupe"] if info is not None else ""),
                "type": (info["type"] if info is not None else ""),
                "description": (info["description"] if info is not None else ""),
                "remplis": filled,
                "vides": n - filled,
                "total": n,
                "taux_completude": round(100 * filled / n, 1) if n else 0.0,
                "dans_export": col in in_export,
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("taux_completude", ascending=False).reset_index(drop=True)


def schema_fields_not_exported(df: pd.DataFrame, schema: pd.DataFrame) -> pd.DataFrame:
    in_export = set(df.attrs.get("columns_in_export", df.columns))
    return schema[~schema["cle"].isin(in_export)].reset_index(drop=True)


_INT_RE = re.compile(r"^-?\d+(\.0+)?$")
_BOOL = {"true", "false", "oui", "non", "0", "1", "yes", "no"}


def type_conformity(df: pd.DataFrame, schema: pd.DataFrame) -> pd.DataFrame:
    """Les valeurs respectent-elles le type déclaré dans le schéma de métadonnées ?"""
    in_export = set(df.attrs.get("columns_in_export", df.columns))
    rows = []
    for r in schema.itertuples():
        if r.cle not in df.columns or r.cle not in in_export:
            continue
        col = df[r.cle]
        vals = col[is_filled(col)].astype(str).str.strip()
        t = r.type.lower()
        if len(vals) == 0:
            valid = 0
        elif t.startswith("date"):
            valid = int(
                pd.to_datetime(vals, errors="coerce", utc=True, format="mixed")
                .notna()
                .sum()
            )
        elif "entier" in t:
            valid = int(vals.map(lambda v: bool(_INT_RE.match(v))).sum())
        elif "bool" in t:
            valid = int(vals.str.lower().isin(_BOOL).sum())
        else:
            valid = len(vals)
        rows.append(
            {
                "champ": r.cle,
                "libelle": r.libelle,
                "type_attendu": r.type,
                "valeurs_renseignees": len(vals),
                "valeurs_conformes": valid,
                "taux_conformite": (
                    round(100 * valid / len(vals), 1) if len(vals) else float("nan")
                ),
            }
        )
    return pd.DataFrame(rows)
