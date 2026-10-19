"""Configuration centrale : charte graphique, seuils, pondérations, lexiques.

Tout ce qui est "réglable" par le client est ici (ou exposé dans la barre latérale
de l'application avec ces valeurs par défaut).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOGUE = ROOT / "data" / "src" / "catalogue-opendata.csv"
DEFAULT_SCHEMA = ROOT / "data" / "src" / "schema-metadonnees.csv"

# --------------------------------------------------------------------------- #
# Charte graphique
# #28256A est la couleur de thème déclarée par data.grandpoitiers.fr ; les autres
# teintes en sont dérivées (à ajuster ici si une charte officielle est fournie).
# --------------------------------------------------------------------------- #
PALETTE = {
    "primary": "#28256A",
    "primary_mid": "#5A52C7",
    "primary_light": "#8E88E8",
    "primary_soft": "#B9B6F2",
    "bg_soft": "#F1F0FA",
    "accent": "#E5446D",
    "warning": "#F4A340",
    "good": "#2BA58B",
    "bad": "#D64550",
    "text": "#1B1A3A",
    "muted": "#6B6A8A",
    "grid": "#E4E2F4",
}
COLORWAY = [
    PALETTE["primary"],
    PALETTE["primary_mid"],
    PALETTE["accent"],
    PALETTE["warning"],
    PALETTE["good"],
    PALETTE["primary_light"],
    PALETTE["primary_soft"],
    PALETTE["muted"],
]
# Échelle séquentielle indigo (heatmaps)
SEQUENTIAL = ["#F1F0FA", "#B9B6F2", "#5A52C7", "#28256A"]

# --------------------------------------------------------------------------- #
# Champs
# --------------------------------------------------------------------------- #
# Champs pris en compte dans le taux de complétude et le score (modifiable dans l'UI).
# `owner` n'existe pas dans l'export actuel : il est créé vide et donc compté comme "non rempli".
ANALYSED_FIELDS = [
    "title",
    "summary",
    "description",
    "keywords",
    "topics",
    "license",
    "conformsTo",
    "origin",
    "owner",
    "creator",
    "frequency",
    "spatial",
    "temporalStart",
    "temporalEnd",
    "modified",
    "dataUpdatedAt",
]
# Colonnes attendues : créées vides si absentes de l'export (pour que tous les
# indicateurs fonctionnent dès qu'une colonne apparaît dans un futur export).
EXPECTED_COLUMNS = [
    "id",
    "page",
    "title",
    "summary",
    "description",
    "keywords",
    "topics",
    "license",
    "conformsTo",
    "conformsToVersion",
    "conformsToUrl",
    "origin",
    "creator",
    "owner",
    "frequency",
    "spatial",
    "temporalStart",
    "temporalEnd",
    "modified",
    "metadataScore",
    "nbChildren",
    "createdAt",
    "updatedAt",
    "dataUpdatedAt",
    "finalizedAt",
    "portalModified",
]
# Colonnes virtuelles (absentes de l'export, créées vides)
VIRTUAL_COLUMNS_NOTE = "colonne absente de l'export : traitée comme vide"

# --------------------------------------------------------------------------- #
# Seuils par défaut (tous modifiables dans la barre latérale)
# --------------------------------------------------------------------------- #
DEFAULT_PARAMS = dict(
    # Titre
    title_min_chars=20,  # X : en dessous, titre "trop court"
    title_max_chars=100,  # au-delà, titre "trop long"
    title_min_meaningful=2,  # nb mini de mots porteurs de sens
    title_target_ratio=0.40,  # part de mots porteurs de sens visée dans un titre
    # Description / résumé
    desc_min_words=30,  # Y : en dessous, description "trop courte"
    desc_target_words=60,  # longueur considérée comme pleinement satisfaisante
    desc_target_ratio=0.40,  # part de mots porteurs de sens visée
    summary_max_sentences=2,  # règle issue du schéma ("une à deux phrases maximum")
    near_dup_threshold=0.85,  # similarité (Jaccard) à partir de laquelle 2 descriptions sont "quasi identiques"
    # Mots-clés / thématiques
    kw_min=3,
    kw_max=10,
    kw_comp_low=20,  # % de vocabulaire nouveau en dessous duquel les mots-clés sont jugés trop redondants
    kw_comp_high=80,  # % au-delà duquel on ne peut plus distinguer un synonyme utile d'un mot hors sujet
    topics_max=3,
    # FALC (proxy textuel)
    falc_target_sentence_words=15,
    falc_long_sentence_words=20,
    falc_long_word_syllables=4,
    falc_rare_zipf=3.0,  # mot "rare" si fréquence Zipf < seuil (nécessite wordfreq)
    # Fraîcheur
    due_tolerance=1.25,  # tolérance multiplicative sur l'intervalle attendu
    due_grace_days=3,  # + jours de grâce
    # Complétude
    completeness_fields=tuple(ANALYSED_FIELDS),
)

# Pondérations du score global (normalisées automatiquement)
DEFAULT_WEIGHTS = {
    "score_completude": 25,
    "score_titre": 15,
    "score_description": 15,
    "score_falc": 10,
    "score_mots_cles_themes": 15,
    "score_fraicheur": 20,
    "score_schema": 0,  # 1,4 % de jeux concernés : à activer si le client le souhaite
}
SCORE_LABELS = {
    "score_completude": "Complétude",
    "score_titre": "Titre",
    "score_description": "Résumé & description",
    "score_falc": "Lisibilité FALC (proxy)",
    "score_mots_cles_themes": "Mots-clés & thématiques",
    "score_fraicheur": "Fraîcheur",
    "score_schema": "Conformité schéma déclarée",
}
SCORE_HELP = {
    "score_completude": "Part des champs retenus (barre latérale) qui sont renseignés.",
    "score_titre": "Longueur, nombre de mots porteurs de sens, absence de séparateurs techniques, unicité.",
    "score_description": "Longueur, densité de sens, unicité, couverture du titre, qualité du résumé (≤ 2 phrases, apporte de l'information).",
    "score_falc": "Proxy automatique de lisibilité inspiré des règles FALC (voir onglet Méthodologie). 0 si aucun texte.",
    "score_mots_cles_themes": "Nombre de mots-clés dans la plage cible, variantes internes, apport de vocabulaire nouveau par rapport aux autres métadonnées, thématique renseignée.",
    "score_fraicheur": "Dernière mise à jour des données comparée à la fréquence déclarée (ou à l'ancienneté si non évaluable).",
    "score_schema": "100 si un schéma est déclaré avec version et URL, 50 s'il est déclaré incomplet, 0 sinon.",
}
QUALITY_LEVELS = [
    (80, "A – Très bon"),
    (65, "B – Bon"),
    (50, "C – À améliorer"),
    (0, "D – Prioritaire"),
]
LEVEL_COLORS = {
    "A – Très bon": PALETTE["good"],
    "B – Bon": PALETTE["primary_mid"],
    "C – À améliorer": PALETTE["warning"],
    "D – Prioritaire": PALETTE["bad"],
}

# Métadonnées par rapport auxquelles on mesure l'apport de vocabulaire des mots-clés : libellé -> colonne
KW_REFERENCE_FIELDS = {
    "titre": "title",
    "résumé": "summary",
    "description": "description",
    "thématiques": "topics",
    "couverture spatiale": "spatial",
}

# Documentation Data Fair (liens vérifiés) : clé -> (libellé, URL)
DATAFAIR_DOCS = {
    "accueil": ("Documentation Data Fair (Koumoul)", "https://docs.koumoul.com/"),
    "contributeur": (
        "Parcours contributeur",
        "https://docs.koumoul.com/pages/contributeur",
    ),
    "admin_jeux": (
        "Administration des jeux de données",
        "https://data-fair.github.io/3/functional-presentation/dataset-management/",
    ),
}

# --------------------------------------------------------------------------- #
# Lexiques (comparés sans accents ni casse)
# --------------------------------------------------------------------------- #
STOPWORDS = set("""
a au aux avec ce ces cet cette ci comme dans de des du elle elles en entre est et etre eux il ils je la le les
leur leurs lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses si son sur
ta te tes toi ton tu un une vos votre vous y d l s n c j m t lors ainsi alors aussi donc or ni car sont sera ete
etait ont avoir fait faire peut peuvent plus moins tres tout tous toute toutes autre autres chaque dont deja encore
sans sous vers chez selon apres avant depuis pendant cela ceci celui celle ceux celles ici
""".split())

# Mots "creux" dans un titre ou une description : ils occupent de la place sans dire de quoi on parle.
GENERIC_WORDS = set("""
jeu jeux donnee donnees dataset datasets base bases liste listes fichier fichiers table tables tableau tableaux
ensemble information informations relatif relatifs relative relatives concernant present presente presentent
contient contiennent comprend comprennent regroupe regroupent permet permettent propose proposent disponible
disponibles voici suivant suivante suivants partir open data opendata
""".split())

GENERIC_KEYWORDS = {
    "donnees",
    "data",
    "opendata",
    "open data",
    "jeu de donnees",
    "dataset",
    "open data",
}

# --------------------------------------------------------------------------- #
# Fréquences (vocabulaire Dublin Core / DCAT utilisé par Data Fair)
# libellé FR, intervalle attendu en jours (None = non évaluable)
# --------------------------------------------------------------------------- #
FREQUENCIES = {
    "continuous": ("En continu", 1),  # évalué comme quotidien
    "daily": ("Quotidienne", 1),
    "semiweekly": ("2 fois par semaine", 4),
    "threeTimesAWeek": ("3 fois par semaine", 3),
    "weekly": ("Hebdomadaire", 7),
    "threeTimesAMonth": ("3 fois par mois", 10),
    "biweekly": ("Toutes les 2 semaines", 14),
    "semimonthly": ("2 fois par mois", 15),
    "monthly": ("Mensuelle", 31),
    "bimonthly": ("Tous les 2 mois", 62),
    "quarterly": ("Trimestrielle", 92),
    "threeTimesAYear": ("3 fois par an", 122),
    "semiannual": ("Semestrielle", 183),
    "annual": ("Annuelle", 366),
    "biennial": ("Tous les 2 ans", 731),
    "triennial": ("Tous les 3 ans", 1096),
    "irregular": ("Irrégulière", None),
}
FREQUENCY_ORDER = [v[0] for v in FREQUENCIES.values()]

# Provenance : une origine est "interne" si elle contient "grand poitiers" ou si elle est EXACTEMENT
# l'un de ces libellés (comparaison sans accents ni casse). On évite volontairement "contient poitiers"
# pour ne pas classer comme interne "Université de Poitiers" ou "CHU de Poitiers".
INTERNAL_ORIGIN_SUBSTRINGS = ["grand poitiers"]
INTERNAL_ORIGIN_EXACT = [
    "poitiers",
    "ville de poitiers",
    "commune de poitiers",
    "mairie de poitiers",
    "cu de poitiers",
]
INTERNAL_URL_DOMAINS = ["grandpoitiers", "poitiers.fr"]

# Référentiel FALC (Facile à Lire et à Comprendre)
# Source vérifiée : « L'information pour tous - Règles européennes pour une information facile à lire et à comprendre »
# (Unapei / Inclusion Europe, édition 2009, 48 p.), lu en entier. Structure réelle du guide : 5 sections PAR TYPE DE SUPPORT
# (1. règles générales : 20 règles ; 2. informations écrites : 42 règles ; 3. électroniques : 30 ; 4. vidéo ; 5. audio).
# Pour un texte, le guide demande d'appliquer les sections 1 et 2. Références notées « §1 r.14 » = section 1, règle 14.
# statut : "mesuree" | "mesurable" (dans le guide, non implémentée) | "non_automatisable"
# coherence (règles mesurées seulement) : "ok" (l'indicateur correspond à la règle) | "partiel" (proxy ou couverture partielle)
#                                         | "hors_guide" (la mesure ne correspond à aucune règle du guide)
FALC_RULES = [
    # (famille, règle (reformulée), référence guide, statut, indicateur(s), cohérence, remarque)
    (
        "Phrases",
        "Faire des phrases courtes ; une seule idée par phrase",
        "§1 r.14 ; §2 r.19",
        "mesuree",
        "falc_mots_par_phrase, falc_pct_phrases_longues",
        "ok",
        "Le guide ne chiffre aucun seuil : les 15 et 20 mots utilisés ici sont un choix du projet.",
    ),
    (
        "Mots",
        "Utiliser des mots que les gens connaissent bien ; éviter les mots difficiles",
        "§1 r.6-7 ; §2 r.11",
        "mesuree",
        "falc_pct_mots_rares, falc_pct_mots_longs, falc_flesch_fr",
        "partiel",
        "Le guide parle de mots connus, pas de longueur de mot ni d'indice de lisibilité. La fréquence du mot (wordfreq) s'en rapproche ; "
        "la longueur en syllabes et l'indice de Flesch sont des proxys ajoutés par le projet.",
    ),
    (
        "Mots",
        "Éviter les initiales (sigles) ; les expliquer si nécessaire",
        "§1 r.12",
        "mesuree",
        "falc_sigles_pour_100_mots",
        "ok",
        "Les abréviations (« par ex. », « etc. », §2 r.16) ne sont pas mesurées.",
    ),
    (
        "Ponctuation",
        "Utiliser une ponctuation simple",
        "§2 r.14",
        "mesuree",
        "falc_nb_parentheses",
        "partiel",
        "L'exemple du guide écarte parenthèses, barre oblique et point-virgule ; seules les parenthèses sont comptées.",
    ),
    (
        "Liens",
        "Éviter les liens difficiles à lire ; les cacher derrière un mot facile",
        "§3 r.25",
        "mesuree",
        "falc_nb_urls",
        "ok",
        "Règle écrite pour les pages web (section « informations électroniques »).",
    ),
    (
        "Mise en forme",
        "Pas de balisage Markdown/HTML dans le texte",
        "-",
        "mesuree",
        "falc_balisage",
        "hors_guide",
        "Aucune règle du guide : c'est un artefact technique du portail ajouté par le projet.",
    ),
    (
        "Titres",
        "Titres clairs et faciles à comprendre, qui expliquent ce qui va suivre",
        "§2 r.20",
        "mesuree",
        "score_titre (mots porteurs de sens, titre technique…) - hors score FALC",
        "partiel",
        "Rapproche notre indicateur de titre d'une règle du guide, mais aucune règle ne parle de « mots porteurs de sens ».",
    ),
    (
        "Phrases",
        "Faire des phrases positives plutôt que négatives",
        "§1 r.16",
        "mesurable",
        "à créer : « ne … pas », « aucun », « sans »",
        None,
        "",
    ),
    (
        "Phrases",
        "Faire des phrases actives plutôt que passives",
        "§1 r.17",
        "mesurable",
        "à créer (approximatif : être + participe passé)",
        None,
        "",
    ),
    (
        "Phrases",
        "S'adresser directement au lecteur (« vous »)",
        "§1 r.15",
        "mesurable",
        "à créer",
        None,
        "À discuter : peu naturel dans une description de jeu de données.",
    ),
    (
        "Mots",
        "Éviter pourcentages et grands nombres",
        "§1 r.13",
        "mesurable",
        "à créer : « % » et nombres à plus de 3 chiffres",
        None,
        "",
    ),
    (
        "Ponctuation",
        "Éviter les caractères spéciaux (\\, &, <, §, #) et les abréviations",
        "§2 r.15-16",
        "mesurable",
        "à créer",
        None,
        "",
    ),
    (
        "Phrases",
        "Listes à puces ou numérotées plutôt que des énumérations avec virgules",
        "§2 r.27",
        "mesurable",
        "à créer : virgules par phrase / présence de puces",
        None,
        "",
    ),
    (
        "Mots",
        "Pas de mots entiers en majuscules",
        "§2 r.7",
        "mesurable",
        "à créer",
        None,
        "Entre en tension avec la règle sur les sigles (les sigles s'écrivent en majuscules).",
    ),
    (
        "Nombres",
        "Chiffres romains interdits ; nombres écrits en chiffres ; dates écrites en entier (« Mardi 13 octobre 2008 »)",
        "§2 r.41-42",
        "mesurable",
        "à créer",
        None,
        "",
    ),
    (
        "Mots",
        "Utiliser le même mot pour la même chose dans tout le document",
        "§1 r.9",
        "non_automatisable",
        "relecture humaine",
        None,
        "",
    ),
    (
        "Mots",
        "Éviter métaphores et mots de langue étrangère peu connus",
        "§1 r.10-11",
        "non_automatisable",
        "relecture humaine",
        None,
        "",
    ),
    (
        "Mots",
        "Expliquer les mots difficiles lorsqu'on doit les utiliser",
        "§1 r.7 ; §2 r.11",
        "non_automatisable",
        "relecture humaine",
        None,
        "",
    ),
    (
        "Organisation",
        "Donner toutes les informations nécessaires : pour qui on écrit et de quoi on parle",
        "§2 r.21",
        "non_automatisable",
        "relecture humaine",
        None,
        "L'indicateur « information nouvelle du résumé » n'en est qu'un indice lointain.",
    ),
    (
        "Organisation",
        "Ne donner que les informations nécessaires ; informations importantes faciles à trouver",
        "§2 r.22-23",
        "non_automatisable",
        "relecture humaine",
        None,
        "",
    ),
    (
        "Organisation",
        "Donner des exemples de la vie de tous les jours",
        "§1 r.8",
        "non_automatisable",
        "relecture humaine",
        None,
        "",
    ),
    (
        "Illustrations",
        "Accompagner le texte d'images (photos, dessins, symboles) claires et cohérentes",
        "§2 r.35-40",
        "non_automatisable",
        "champ `image` absent de l'export",
        None,
        "",
    ),
    (
        "Mise en page",
        "Police claire sans empattement (Arial/Tahoma ≥ 14), pas d'italique, pas de colonnes, texte aligné à gauche, "
        "pas de fond gênant…",
        "§2 r.1-10, 26-33",
        "non_automatisable",
        "dépend du portail, pas des métadonnées",
        None,
        "",
    ),
    (
        "Validation",
        "Impliquer des personnes handicapées intellectuelles : choisir le sujet et vérifier que le texte est facile à lire",
        "§1 « Avant de commencer » n°5",
        "non_automatisable",
        "seul un test utilisateur peut l'attester",
        None,
        "",
    ),
]
FALC_STATUS_LABELS = {
    "mesuree": "✅ Mesurée",
    "mesurable": "🟡 Mesurable, non implémentée",
    "non_automatisable": "- Non automatisable",
}
FALC_COHERENCE_LABELS = {
    "ok": "✅ Cohérent avec le guide",
    "partiel": "⚠️ Partiel / proxy",
    "hors_guide": "❌ Absent du guide",
    None: "-",
}

# Éléments de notre score FALC qui ne proviennent PAS du guide (à valider ou à retirer avec le client)
FALC_NOT_FROM_GUIDE = [
    "Les seuils chiffrés : 15 mots par phrase visés, 20 mots pour une phrase « longue », 4 syllabes pour un mot « long », Zipf < 3 pour un mot « rare ».",
    "La longueur des mots (syllabes estimées) : le guide ne dit rien sur la longueur d'un mot.",
    "L'indice de Flesch adapté au français : outil de lisibilité externe, absent du guide.",
    "La détection du balisage Markdown/HTML : artefact du portail, aucune règle correspondante.",
    "La pondération qui agrège ces sous-notes en un score de 0 à 100 : construction du projet.",
]

SCORE_FORMULA = {
    "score_completude": "Part (en %) des champs retenus dans la barre latérale qui sont renseignés pour ce jeu.",
    "score_titre": "100 × [25 % longueur dans la plage (X – max caractères) + 45 % mots porteurs de sens (au moins 2, et au moins 40 % des mots) "
    "+ 15 % absence de séparateurs techniques (_, extension, slug) + 15 % titre unique]. 0 si titre absent.",
    "score_description": "100 × [30 % longueur (pleine à 60 mots) + 15 % densité de mots porteurs de sens (pleine à 40 %) + 15 % unicité (ni doublon, "
    "ni identique au résumé) + 10 % reprise des mots du titre + 30 % qualité du résumé]. "
    "Qualité du résumé = présent (40 %) + au plus N phrases (30 %) + apporte des mots absents du titre (30 %).",
    "score_falc": "Moyenne de 6 sous-notes (7 avec wordfreq) : longueur des phrases, part de phrases longues, part de mots longs, sigles, bruit "
    "(parenthèses/liens/balisage), indice de Flesch FR, mots rares. 0 si aucun texte. Proxy : une partie des sous-notes ne vient pas du guide FALC (voir Méthodologie).",
    "score_mots_cles_themes": "60 % mots-clés + 40 % thématiques. Mots-clés = 50 % nombre dans la plage + 25 % absence de variantes internes "
    "+ 25 % complémentarité (pleine si 20 à 80 % du vocabulaire des mots-clés est absent des autres métadonnées ; "
    "croît de 0 à 20 % ; décroît de 100 % à 50 % entre 80 et 100 %). 0 si aucun mot-clé. "
    "Thématiques = 100 si 1 à N thématiques, dégressif au-delà, 0 si aucune.",
    "score_fraicheur": "Si la fréquence est évaluable : 100 tant que le jeu est à jour, puis décroît jusqu'à 0 à 3 × le seuil de retard. "
    "Sinon, selon l'ancienneté : 100 jusqu'à 6 mois, 75 à 1 an, 40 à 2 ans, 0 à 3 ans. 0 si la date est inconnue.",
    "score_schema": "100 si un schéma est déclaré avec version et URL, 50 s'il est déclaré de façon incomplète, 0 sinon.",
}

# Règles de classification affichées dans la méthodologie (ordre d'application)
PROVENANCE_RULES = [
    ("Non renseignée", "Le champ `origin` est vide."),
    (
        "data.gouv.fr (URL)",
        "La valeur est une URL (http, https ou www) dont le domaine contient data.gouv.fr. Testé AVANT les autres URL : "
        "un jeu de Grand Poitiers republié sur data.gouv.fr est classé ici.",
    ),
    (
        "Interne (Grand Poitiers / Ville de Poitiers)",
        "URL dont le domaine contient grandpoitiers ou poitiers.fr ; OU texte contenant « Grand Poitiers » ; "
        "OU texte égal à « Poitiers », « Ville de Poitiers », « Commune de Poitiers », « Mairie de Poitiers ».",
    ),
    (
        "Autre source web (URL)",
        "Toute autre URL (INSEE, data.education.gouv.fr, Hub'Eau…).",
    ),
    (
        "Autre organisme (nom cité)",
        "Tout autre texte : INSEE, Vitalis, Cerema, une autre commune de l'agglomération (Migné-Auxances, Montamisé)…",
    ),
]
SPATIAL_RULES = [
    ("Non renseigné", "Libellé vide."),
    (
        "Grand Poitiers (intercommunal)",
        "Le libellé contient « Grand Poitiers », « CU », « communauté urbaine » ou « agglo ».",
    ),
    (
        "Ville de Poitiers",
        "Le libellé est exactement « Poitiers », « Ville de Poitiers » ou « Commune de Poitiers ».",
    ),
    (
        "Autre commune / territoire",
        "Tout autre libellé (Migné-Auxances, Montamisé, Seuil du Poitou…).",
    ),
]
LICENCE_RULES = [
    ("Non renseignée", "Licence vide."),
    (
        "Licence Ouverte (Etalab)",
        "Le libellé contient « licence ouverte », « open licence » ou « etalab ».",
    ),
    ("ODbL", "Le libellé contient « ODbL » ou « Open Database »."),
    ("Creative Commons", "Le libellé contient « Creative Commons » ou « CC-BY »."),
    ("Autre licence", "Tout autre libellé."),
]
LICENCE_VERSION_RULE = "La version est considérée « précisée » si le libellé contient au moins un chiffre (ex. « version 2.0 », « v2.0 »)."

# Utilité, pour ce tableau de bord, des champs du schéma absents de l'export
MISSING_FIELD_USE = {
    "id": "Identifiant stable ; remplace le numéro de ligne dans les exports.",
    "page": "Lien cliquable vers la fiche du jeu sur le portail.",
    "slug": "Identifiant lisible : permet de repérer les titres/URL techniques.",
    "owner": "Indicateur « jeux par type de propriétaire ».",
    "image": "Règle FALC « pictogramme / illustration ».",
    "bbox": "Couverture spatiale géographique réelle (aujourd'hui : libellé texte seulement).",
    "fileFormat": "Répartition des jeux par format de fichier.",
    "count": "Volume (nombre de lignes) : poids de provenance par volume.",
    "storageSize": "Volume (taille) : poids de provenance par volume.",
    "nbColumns": "Complexité du jeu.",
    "nbUsedInVirtual": "Réutilisation : poids de provenance par usage.",
    "nbApplications": "Réutilisation : poids de provenance par usage.",
    "status": "Distinguer jeux publiés / brouillons.",
    "visibility": "Distinguer jeux publics / privés.",
    "published": "Distinguer jeux publiés / non publiés.",
    "primaryKey": "Qualité de structuration des données.",
    "relatedDatasets": "Cohérence du maillage entre jeux.",
}

# --------------------------------------------------------------------------- #
# Dictionnaire des indicateurs (onglet Méthodologie)
# (clé, groupe, libellé, description)
# --------------------------------------------------------------------------- #
METRIC_DICT = [
    (
        "dataset_id / titre / page",
        "Identification",
        "Identification du jeu",
        "`id` Data Fair si l'export le contient, sinon « ligne-NNNN » (numéro de ligne) ; titre ; lien vers le portail (colonne omise si `page` est vide).",
    ),
    # --- Scores
    (
        "score_global",
        "Score",
        "Score global (0-100)",
        "Moyenne pondérée des 7 scores par dimension (poids modifiables). Un champ absent donne 0 à la dimension concernée.",
    ),
    (
        "niveau_qualite",
        "Score",
        "Niveau de qualité",
        "Déduit du score global : A ≥ 80, B ≥ 65, C ≥ 50, D < 50.",
    ),
    (
        "score_completude / score_titre / score_description / score_falc / score_mots_cles_themes / score_fraicheur / score_schema",
        "Score",
        "Scores par dimension (0-100)",
        "Détail du calcul de chacun dans le tableau « Pondération » ci-dessus.",
    ),
    (
        "nb_alertes / alertes",
        "Score",
        "Alertes",
        "Défauts détectés sur le jeu, selon les seuils de la barre latérale. `alertes` les liste séparés par « | ».",
    ),
    # --- Complétude
    (
        "completude_pct",
        "Complétude",
        "Taux de complétude",
        "Part des champs retenus (barre latérale) qui sont renseignés pour ce jeu.",
    ),
    (
        "nb_champs_vides / champs_vides",
        "Complétude",
        "Champs vides",
        "Nombre et liste des champs retenus non renseignés.",
    ),
    (
        "rempli_<champ>",
        "Complétude",
        "Champ renseigné",
        "1 si le champ est renseigné, 0 sinon (une colonne par champ retenu).",
    ),
    # --- Titre
    (
        "titre_nb_caracteres",
        "Titre",
        "Longueur (caractères)",
        "Nombre de caractères du titre.",
    ),
    (
        "titre_nb_mots",
        "Titre",
        "Nombre de mots",
        "Mots du titre, chiffres compris (« Élections 2021 » = 2 mots).",
    ),
    (
        "titre_nb_mots_porteurs / titre_ratio_porteurs",
        "Titre",
        "Mots porteurs de sens",
        "Nombre et part des mots du titre qui ne sont ni mots vides ni mots creux (voir « Vocabulaire »). Les chiffres ne comptent pas comme mots porteurs.",
    ),
    (
        "titre_mots_non_porteurs",
        "Titre",
        "Mots sans valeur",
        "Liste des mots du titre qui ne portent pas de sens.",
    ),
    (
        "titre_trop_court / titre_trop_long",
        "Titre",
        "Seuils de longueur",
        "Moins de X caractères / plus du maximum configuré.",
    ),
    (
        "titre_peu_informatif",
        "Titre",
        "Titre peu informatif",
        "Moins de N mots porteurs de sens (N configurable, 2 par défaut).",
    ),
    (
        "titre_technique",
        "Titre",
        "Titre technique",
        "Contient un underscore (_), une extension de fichier (.csv, .xlsx, .json…), les mots test/brouillon/copie, ou ressemble à un slug (sans espace, avec tirets, > 15 caractères).",
    ),
    (
        "titre_majuscules",
        "Titre",
        "Titre en capitales",
        "Plus de 60 % des lettres sont des majuscules, pour un titre de plus de 8 lettres.",
    ),
    (
        "titre_doublon",
        "Titre",
        "Titre en doublon",
        "Un autre jeu a le même titre (après suppression des accents, de la casse et de la ponctuation).",
    ),
    # --- Résumé & description
    (
        "resume_nb_mots / resume_nb_phrases",
        "Résumé",
        "Longueur du résumé",
        "Mots et phrases du résumé.",
    ),
    (
        "resume_trop_long",
        "Résumé",
        "Résumé trop long",
        "Plus de N phrases (le schéma demande « une à deux phrases maximum »).",
    ),
    (
        "resume_nouveaute_vs_titre",
        "Résumé",
        "Information nouvelle du résumé",
        "Part des mots porteurs du résumé qui ne sont pas dans le titre. Proche de 0 : le résumé ne fait que répéter le titre.",
    ),
    (
        "desc_nb_mots",
        "Description",
        "Longueur de la description",
        "Mots de la description, une fois le balisage Markdown/HTML et les liens retirés ; chiffres compris.",
    ),
    (
        "desc_courte",
        "Description",
        "Description courte",
        "Description présente mais de moins de Y mots. Une description absente n'est pas comptée ici (voir `desc_nb_mots` = 0).",
    ),
    (
        "desc_nb_mots_porteurs / desc_ratio_porteurs",
        "Description",
        "Densité de sens",
        "Nombre et part des mots de la description qui portent du sens.",
    ),
    (
        "desc_doublon",
        "Description",
        "Description en doublon exact",
        "Même texte (après normalisation) que celui d'un autre jeu.",
    ),
    (
        "desc_quasi_doublon",
        "Description",
        "Description dupliquée ou quasi identique",
        "Doublon exact OU similarité ≥ 85 % (Jaccard sur les racines de mots porteurs, descriptions d'au moins 8 mots) avec un autre jeu.",
    ),
    (
        "desc_identique_resume",
        "Description",
        "Description = résumé",
        "La description recopie le résumé : elle n'ajoute rien.",
    ),
    (
        "desc_couverture_titre",
        "Description",
        "Reprise du titre",
        "Part des mots porteurs du titre qui réapparaissent (racines) dans la description. Faible : la description ne parle pas du sujet du titre.",
    ),
    # --- FALC
    (
        "falc_nb_phrases / falc_mots_par_phrase",
        "FALC",
        "Phrases",
        "Nombre de phrases et nombre moyen de mots par phrase. Phrases séparées par . ! ? … et par les retours à la ligne.",
    ),
    (
        "falc_pct_phrases_longues",
        "FALC",
        "Phrases longues",
        "Part des phrases de plus de N mots (20 par défaut).",
    ),
    (
        "falc_syllabes_par_mot / falc_pct_mots_longs",
        "FALC",
        "Mots longs",
        "Syllabes estimées par mot (comptage de groupes de voyelles) ; part des mots d'au moins 4 syllabes.",
    ),
    (
        "falc_sigles_pour_100_mots",
        "FALC",
        "Sigles",
        "Mots en capitales de 2 lettres ou plus (IPS, RGAA…) pour 100 mots. Non compté si le texte est presque entièrement en capitales.",
    ),
    (
        "falc_nb_parentheses / falc_nb_urls / falc_balisage",
        "FALC",
        "Bruit",
        "Parenthèses ouvrantes, liens bruts (http…), présence de balisage Markdown/HTML dans le texte d'origine.",
    ),
    (
        "falc_pct_mots_rares",
        "FALC",
        "Mots rares",
        "Part des mots (3 lettres ou plus) de fréquence Zipf < 3,0 en français (moins d'1 occurrence par million de mots). Nécessite `wordfreq`, sinon vide.",
    ),
    (
        "falc_flesch_fr",
        "FALC",
        "Indice de Flesch (français)",
        "207 − 1,015 × mots par phrase − 73,6 × syllabes par mot (Kandel & Moles). Plus c'est haut, plus c'est facile : > 60 aisé, 30-50 difficile.",
    ),
    (
        "falc_score / falc_source",
        "FALC",
        "Score FALC (proxy)",
        "Moyenne des sous-notes ci-dessus. Calculé sur la description, à défaut le résumé (`falc_source`).",
    ),
    # --- Mots-clés / thématiques
    (
        "kw_nb",
        "Mots-clés",
        "Nombre de mots-clés",
        "Mots-clés séparés par « ; », tels que saisis.",
    ),
    (
        "kw_nb_distincts_brut / kw_nb_distincts_norm",
        "Mots-clés",
        "Mots-clés distincts",
        "Avant et après normalisation simple (casse, accents, ponctuation, espaces, pluriel).",
    ),
    (
        "kw_variantes_internes",
        "Mots-clés",
        "Variantes internes",
        "Écart entre les deux nombres précédents : mots-clés distincts à l'origine qui deviennent identiques après normalisation (ex. élection ; élections).",
    ),
    (
        "kw_nb_redondants / kw_nb_partiels / kw_nb_complementaires",
        "Mots-clés",
        "Complémentarité des mots-clés",
        "Chaque mot-clé est comparé au titre, au résumé, à la description, aux thématiques et à la couverture spatiale (racines des mots, hors mots vides). Redondant : tous ses mots figurent déjà ailleurs. Complémentaire : aucun de ses mots n'apparaît ailleurs. Partiel : entre les deux. Un mot-clé qui ne contient que des mots vides est ignoré.",
    ),
    (
        "kw_vocab_nouveau_pct",
        "Mots-clés",
        "Vocabulaire nouveau",
        "Part des racines de mots des mots-clés (sans doublons de mots vides) qui sont absentes de toutes les autres métadonnées. 0 % : les mots-clés ne disent rien de plus que le reste.",
    ),
    (
        "kw_egaux_thematique",
        "Mots-clés",
        "Mots-clés = thématique",
        "Nombre de mots-clés identiques, après normalisation, à l'une des thématiques du jeu.",
    ),
    (
        "kw_complementarite_score",
        "Mots-clés",
        "Score de complémentarité (0-100)",
        "100 si 20 à 80 % du vocabulaire est nouveau (seuils réglables) ; de 0 à 100 entre 0 et 20 % ; de 100 à 50 entre 80 et 100 %. Ce plateau est un choix du projet : sans référence, on ne sait pas dire si un mot-clé 100 % nouveau est un bon synonyme ou un mot hors sujet.",
    ),
    (
        "kw_generiques",
        "Mots-clés",
        "Mots-clés génériques",
        "Nombre de mots-clés égaux, après normalisation, à : données, data, opendata, open data, jeu de données, dataset.",
    ),
    (
        "kw_hors_plage",
        "Mots-clés",
        "Nombre hors plage",
        "Vrai si le jeu a au moins un mot-clé mais moins que le minimum ou plus que le maximum configurés. Un jeu SANS mot-clé n'est pas compté ici (voir `kw_nb` = 0).",
    ),
    (
        "topics_nb / topics_nb_variantes",
        "Thématiques",
        "Thématiques",
        "Nombre de thématiques (séparées par « ; ») ; variantes de casse/accents au sein du jeu.",
    ),
    # --- Licence / provenance / propriétaire / schéma
    (
        "licence / licence_famille",
        "Licence",
        "Licence",
        "Libellé saisi et famille après regroupement (règles dans « Règles de regroupement »).",
    ),
    (
        "licence_version_precisee",
        "Licence",
        "Version précisée",
        "Vrai si le libellé contient un chiffre. Faux aussi quand la licence est absente.",
    ),
    (
        "origine / provenance_type",
        "Provenance",
        "Provenance",
        "Valeur du champ `origin` et type déduit (règles dans « Règles de regroupement »).",
    ),
    (
        "proprietaire_type / proprietaire_nom",
        "Propriétaire",
        "Propriétaire",
        "Dérivé de `owner` (JSON Data Fair ou texte). Colonne vide dans l'export actuel.",
    ),
    (
        "schema_declare / schema_nom / schema_complet",
        "Schéma",
        "Schéma déclaré",
        "`conformsTo` renseigné ; complet si `conformsToVersion` et `conformsToUrl` le sont aussi.",
    ),
    # --- Spatial / temporel
    (
        "spatial / spatial_type",
        "Spatial",
        "Couverture spatiale",
        "Libellé saisi et type déduit (règles dans « Règles de regroupement »).",
    ),
    (
        "temporel_type",
        "Temporel",
        "Type de couverture temporelle",
        "Période close (début < fin), ponctuelle (début = fin), début seul (en cours), fin seule, incohérente (fin < début), non renseignée.",
    ),
    (
        "temporel_debut / temporel_fin / temporel_duree_jours",
        "Temporel",
        "Période couverte",
        "Dates et durée en jours (période close uniquement).",
    ),
    # --- Mises à jour
    (
        "frequence / frequence_libelle / frequence_jours_attendus",
        "Mises à jour",
        "Fréquence déclarée",
        "Code du champ `frequency`, libellé français, intervalle attendu en jours (voir tableau des fréquences).",
    ),
    (
        "date_maj_donnees / jours_depuis_maj_donnees",
        "Mises à jour",
        "Dernière mise à jour des données",
        "Date `dataUpdatedAt` et nombre de jours écoulés jusqu'à la date de référence.",
    ),
    (
        "jours_depuis_maj_metadonnees",
        "Mises à jour",
        "Dernière modification des métadonnées",
        "Jours écoulés depuis `updatedAt` (modifie aussi quand on corrige une fiche, sans toucher aux données).",
    ),
    (
        "categorie_maj / tranche_anciennete",
        "Mises à jour",
        "Catégories de mise à jour",
        "Année courante / année précédente / avant ; tranches ≤ 1 mois, 1–6 mois, 6–12 mois, 1–2 ans, > 2 ans.",
    ),
    (
        "statut_fraicheur / retard_jours",
        "Mises à jour",
        "Fraîcheur vs fréquence",
        "Seuil de retard = intervalle attendu × tolérance + jours de grâce. À jour ≤ seuil ; en retard ≤ 2 × seuil ; très en retard au-delà. "
        "Non évaluable si la fréquence est absente, « irrégulière » ou inconnue, ou si la date est inconnue. `retard_jours` = dépassement du seuil.",
    ),
    (
        "jamais_mis_a_jour_depuis_creation",
        "Mises à jour",
        "Aucune mise à jour depuis la création",
        "Vrai si la dernière mise à jour des données (`dataUpdatedAt`) date de moins d'un jour après la création du jeu (`createdAt`), ou lui est antérieure : les données n'ont jamais été rechargées depuis la mise en ligne. Faux si une des deux dates est inconnue.",
    ),
    # --- Référence
    (
        "score_natif_data_fair",
        "Référence",
        "metadataScore Data Fair",
        "Score natif de la plateforme, pour comparaison avec le score global de ce tableau de bord.",
    ),
]
