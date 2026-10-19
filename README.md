# Qualité du catalogue open data : tableau de bord

Tableau de bord Streamlit + Plotly qui dresse l'état des lieux des métadonnées d'un catalogue Data Fair
(export CSV).

## Lancer

```bash
pip install -r requirements.txt
streamlit run app.py
```

Les fichiers par défaut sont dans `data/`. On peut aussi charger un autre export depuis la barre latérale.

## Structure

```
app.py                 interface (onglets, filtres, exports)
quality/
  config.py            charte graphique, seuils, pondérations, lexiques, dictionnaire des indicateurs, règles FALC
  loader.py            lecture des CSV, complétude, conformité aux types, infobulles issues du schéma
  textkit.py           normalisation, mots porteurs de sens, proxy FALC
  metrics.py           indicateurs par jeu, score, alertes, avant/après normalisation, vue globale
  charts.py            graphiques Plotly
  exports.py           les deux CSV
data/                  catalogue + schéma de métadonnées
```

Le moteur (`quality/`) ne dépend pas de Streamlit : on peut produire les CSV sans interface.

```python
import datetime
from quality import loader, metrics, exports, config as cfg
df = loader.load_catalogue("data/catalogue-opendata.csv")
schema = loader.load_schema("data/schema-metadonnees.csv")
m = metrics.apply_scores(metrics.compute_dataset_metrics(df, cfg.DEFAULT_PARAMS, datetime.date.today()), cfg.DEFAULT_WEIGHTS)
open("vue_globale.csv", "wb").write(exports.to_csv_bytes(exports.global_view(metrics.compute_global(m, df, schema, cfg.DEFAULT_PARAMS))))
open("vue_par_jeu.csv", "wb").write(exports.to_csv_bytes(exports.dataset_view(m)))
```

## Choix de conception

- **Pas de pré-traitement correctif.** Les vues principales montrent les données brutes. Les normalisations
  (mots-clés, thématiques, licences, couverture spatiale) servent uniquement à mesurer le gain possible (« avant / après »).
- **Colonnes absentes = vides.** `owner`, `id`, `page` n'existent pas dans l'export actuel : elles sont créées vides et
  comptées comme non renseignées ; les indicateurs fonctionneront dès qu'elles seront exportées.
- **Seuils et pondérations** : tout est réglable dans la barre latérale (valeurs par défaut dans `quality/config.py`).
- **Exports** : CSV UTF-8 avec BOM, au choix « Excel FR » (`;` et virgule décimale) ou standard.
- **Infobulles ⓘ** : descriptions tirées du fichier de schéma de métadonnées.
- **Clés de lecture** : chaque graphique est suivi d'une phrase calculée automatiquement sur les données affichées.

## Limites

Voir l'onglet « Méthodologie » : pas de vérification réelle de conformité aux schémas, couverture spatiale en texte
seulement, FALC = proxy automatique (pas une labellisation), indicateurs de sens fondés sur des listes de mots.
