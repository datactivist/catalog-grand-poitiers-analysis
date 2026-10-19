"""Outils de traitement de texte (français) : normalisation, mots porteurs de sens, proxy FALC."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import numpy as np

from .config import GENERIC_WORDS, STOPWORDS

try:  # optionnel
    from wordfreq import zipf_frequency

    HAS_WORDFREQ = True
except Exception:  # pragma: no cover
    HAS_WORDFREQ = False

LETTER_RE = re.compile(r"[^\W\d_]+", re.UNICODE)  # lettres uniquement
WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)  # lettres + chiffres
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+|www\.\S+")
_HTML = re.compile(r"<[^>]+>")
_MARKUP_DETECT = re.compile(
    r"<[a-zA-Z/][^>]*>|(^|\n)\s*#{1,6}\s|\*\*|\]\(|(^|\n)\s*[-*+]\s"
)
_ACRONYM = re.compile(r"\b[A-ZÀ-ÝÉ]{2,}[A-ZÀ-ÝÉ0-9]*\b")


# --------------------------------------------------------------------------- #
# Normalisation de base
# --------------------------------------------------------------------------- #
def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def clean_str(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    s = str(value)
    return "" if s.lower() == "<na>" else s.strip()


def basic_key(text: str) -> str:
    """Clé de comparaison de textes : minuscules, sans accents, sans ponctuation, espaces réduits."""
    t = strip_accents(clean_str(text).lower())
    t = re.sub(r"[^\w\s]|_", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def stem(token: str) -> str:
    """Racinisation très légère : minuscules, sans accents, sans 's'/'x' final du pluriel."""
    k = strip_accents(token.lower())
    if len(k) > 3 and k.endswith(("s", "x")) and not k.endswith("ss"):
        k = k[:-1]
    return k


def norm_key(label: str) -> str:
    """Normalisation SIMPLE d'un mot-clé / thématique (casse, accents, ponctuation, séparateurs, pluriel).
    'Élections', 'election', 'ÉLECTION' → 'election' ; 'pont neuf' / 'PontNeuf' / 'pont-neuf' → 'pontneuf'.
    """
    k = strip_accents(clean_str(label).lower())
    k = re.sub(r"[^\w\s]|_", " ", k)
    return "".join(stem(t) for t in k.split())


def split_multi(value, sep: str = ";") -> list[str]:
    s = clean_str(value)
    if not s:
        return []
    return [p.strip() for p in s.split(sep) if p.strip()]


# --------------------------------------------------------------------------- #
# Mots porteurs de sens
# --------------------------------------------------------------------------- #
def is_meaningful(token: str) -> bool:
    k = strip_accents(token.lower())
    return len(k) >= 3 and k not in STOPWORDS and k not in GENERIC_WORDS


def word_analysis(text: str) -> dict:
    """Décompose un texte en mots porteurs de sens / mots sans valeur (lettres uniquement)."""
    toks = LETTER_RE.findall(clean_str(text))
    meaningful = [t for t in toks if is_meaningful(t)]
    noise = [t for t in toks if not is_meaningful(t)]
    n = len(toks)
    return {
        "n_words": n,
        "meaningful": meaningful,
        "noise": noise,
        "ratio": (len(meaningful) / n) if n else np.nan,
    }


def meaningful_stems(text: str) -> set[str]:
    return {stem(t) for t in LETTER_RE.findall(clean_str(text)) if is_meaningful(t)}


def all_stems(text: str) -> set[str]:
    """Racines de tous les mots (chiffres inclus) hors mots vides - pour la complémentarité des mots-clés."""
    return {
        stem(t)
        for t in WORD_RE.findall(clean_str(text))
        if strip_accents(t.lower()) not in STOPWORDS
    }


# --------------------------------------------------------------------------- #
# Nettoyage Markdown / HTML et phrases
# --------------------------------------------------------------------------- #
def has_markup(text: str) -> bool:
    return bool(_MARKUP_DETECT.search(text or ""))


def clean_markdown(text: str) -> str:
    t = _MD_LINK.sub(r"\1", text or "")
    t = _URL.sub(" ", t)
    t = _HTML.sub(" ", t)
    t = re.sub(r"(^|\n)\s*([-+•]|\d+\.)\s+", r"\1", t)
    t = re.sub(r"[*`#>|]", " ", t)
    return t


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text or "")
    return [p.strip() for p in parts if re.search(r"\w", p)]


def count_sentences(text: str) -> int:
    return len(split_sentences(clean_markdown(text)))


# --------------------------------------------------------------------------- #
# Proxy FALC
# --------------------------------------------------------------------------- #
_VOWELS = "aeiouyàâäéèêëîïôöùûü"


@lru_cache(maxsize=50000)
def count_syllables_fr(word: str) -> int:
    """Estimation du nombre de syllabes (groupes de voyelles, e muet final ignoré)."""
    w = word.lower()
    if len(w) > 3:
        if w.endswith("es"):
            w = w[:-2]
        elif w.endswith("e"):
            w = w[:-1]
    return max(1, len(re.findall(f"[{_VOWELS}]+", w)))


@lru_cache(maxsize=50000)
def _zipf(word: str) -> float:
    return zipf_frequency(word, "fr") if HAS_WORDFREQ else float("nan")


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def falc_metrics(text: str, params: dict) -> dict | None:
    """Indicateurs de lisibilité inspirés des règles FALC. Retourne None si pas de texte exploitable."""
    raw = clean_str(text)
    cleaned = clean_markdown(raw)
    words_all = WORD_RE.findall(cleaned)
    words = [w for w in words_all if not w.isdigit()]
    if not words:
        return None
    sents = split_sentences(cleaned)
    per_sent = [len(WORD_RE.findall(s)) for s in sents] or [len(words_all)]
    asl = float(np.mean(per_sent))
    pct_long_sent = float(
        np.mean([n > params["falc_long_sentence_words"] for n in per_sent])
    )
    syl = [count_syllables_fr(w) for w in words]
    asw = float(np.mean(syl))
    pct_long_words = float(
        np.mean([s >= params["falc_long_word_syllables"] for s in syl])
    )

    letters = [c for c in cleaned if c.isalpha()]
    upper_share = (sum(c.isupper() for c in letters) / len(letters)) if letters else 0
    n_acr = 0 if upper_share > 0.6 else len(_ACRONYM.findall(cleaned))
    acr_100 = 100 * n_acr / len(words)
    n_paren = cleaned.count("(")
    n_urls = len(_URL.findall(raw))
    markup = has_markup(raw)
    flesch = 207 - 1.015 * asl - 73.6 * asw  # adaptation française (Kandel & Moles)

    rare = np.nan
    if HAS_WORDFREQ:
        cand = [w for w in words if len(w) >= 3 and not (w.isupper() and len(w) <= 6)]
        if cand:
            rare = float(
                np.mean([_zipf(w.lower()) < params["falc_rare_zipf"] for w in cand])
            )

    target = params["falc_target_sentence_words"]
    subs = [
        _clip01(1 - (asl - target) / target),  # longueur moyenne des phrases
        _clip01(1 - pct_long_sent / 0.5),  # part de phrases longues
        _clip01(1 - max(0.0, pct_long_words - 0.10) / 0.25),  # mots longs
        _clip01(1 - acr_100 / 5),  # sigles
        _clip01(
            1 - min(1.0, 0.15 * (n_paren + n_urls) + (0.25 if markup else 0))
        ),  # bruit (parenthèses, liens, balisage)
        _clip01(flesch / 60),  # Flesch FR
    ]
    if not np.isnan(rare):
        subs.append(_clip01(1 - max(0.0, rare - 0.15) / 0.35))
    return {
        "falc_nb_phrases": len(per_sent),
        "falc_mots_par_phrase": round(asl, 1),
        "falc_pct_phrases_longues": round(100 * pct_long_sent, 1),
        "falc_syllabes_par_mot": round(asw, 2),
        "falc_pct_mots_longs": round(100 * pct_long_words, 1),
        "falc_sigles_pour_100_mots": round(acr_100, 1),
        "falc_nb_parentheses": n_paren,
        "falc_nb_urls": n_urls,
        "falc_balisage": bool(markup),
        "falc_pct_mots_rares": (round(100 * rare, 1) if not np.isnan(rare) else np.nan),
        "falc_flesch_fr": round(flesch, 1),
        "falc_score": round(100 * float(np.mean(subs)), 1),
    }


FALC_EMPTY = {
    "falc_nb_phrases": np.nan,
    "falc_mots_par_phrase": np.nan,
    "falc_pct_phrases_longues": np.nan,
    "falc_syllabes_par_mot": np.nan,
    "falc_pct_mots_longs": np.nan,
    "falc_sigles_pour_100_mots": np.nan,
    "falc_nb_parentheses": np.nan,
    "falc_nb_urls": np.nan,
    "falc_balisage": np.nan,
    "falc_pct_mots_rares": np.nan,
    "falc_flesch_fr": np.nan,
    "falc_score": np.nan,
}
