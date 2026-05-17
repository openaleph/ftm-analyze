# Settings

Configuration is handled by [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) in [`ftm_analyze.settings`](https://github.com/dataresearchcenter/ftm-analyze/blob/main/ftm_analyze/settings.py). Every option below can be set via an environment variable or via a `.env` file in the working directory, using the prefix `FTM_ANALYZE_` (e.g. `FTM_ANALYZE_NER_ENGINE=flair`).

Print the currently resolved settings with:

```bash
ftm-analyze --settings
```

## Pipeline toggles

These flags control which optional resolution stages run. They default to `false` so a vanilla install behaves like the original `ingest-file` analyzer; opt-in stages light up as soon as the corresponding flag is on.

### `resolve_mentions`

| Env | `FTM_ANALYZE_RESOLVE_MENTIONS` |
| --- | --- |
| Type | `bool` |
| Default | `false` |

Resolve known mentions to real entities via `juditha.lookup`. When the lookup returns a hit above its score threshold the analyzer emits the resolved entity (Person, Organization, …) instead of a `Mention` entity. See [NER](../ner.md) for how to populate the juditha index.

### `refine_mentions`

| Env | `FTM_ANALYZE_REFINE_MENTIONS` |
| --- | --- |
| Type | `bool` |
| Default | `false` |

Refine NER tags using extra rigour heuristics plus a `juditha.lookup` pass, so spaCy's PER/ORG/LOC decisions can be corrected before downstream resolution.

### `refine_locations`

| Env | `FTM_ANALYZE_REFINE_LOCATIONS` |
| --- | --- |
| Type | `bool` |
| Default | `false` |

Canonicalize location mentions against `geonames_tagger`. When enabled, a `LOC` mention whose surface form fuzzy-matches a geonames entry is rewritten to the canonical place name.

### `validate_names`

| Env | `FTM_ANALYZE_VALIDATE_NAMES` |
| --- | --- |
| Type | `bool` |
| Default | `false` |

Drop mentions that `juditha` cannot validate. Effectively a stricter version of `resolve_mentions` – kept around for callers that want to filter without rewriting. Skipped when `resolve_mentions` is also enabled to avoid a duplicate lookup.

### `annotate`

| Env | `FTM_ANALYZE_ANNOTATE` |
| --- | --- |
| Type | `bool` |
| Default | `false` |

Rewrite text properties with per-word ZWJ annotation markers consumed by `openaleph-search`. See [annotate](../annotate.md) and [`annotations.md`](https://github.com/dataresearchcenter/ftm-analyze/blob/main/annotations.md) for the format spec.

### `overwrite_lang`

| Env | `FTM_ANALYZE_OVERWRITE_LANG` |
| --- | --- |
| Type | `bool` |
| Default | `false` |

Drop any pre-existing `detectedLanguage` values before running language detection, so the property always reflects the analyzer's own decision.

## NER backend

### `ner_engine`

| Env | `FTM_ANALYZE_NER_ENGINE` |
| --- | --- |
| Type | `"spacy" \| "flair" \| "bert" \| "gliner"` |
| Default | `"spacy"` |

Selects the named-entity recognition engine. Non-spaCy backends require their respective extras (`pip install ftm-analyze[ner-flair]`, `[ner-gliner]`, `[ner-transformers]`).

### `ner_default_lang`

| Env | `FTM_ANALYZE_NER_DEFAULT_LANG` |
| --- | --- |
| Type | `str` (ISO 639-3) |
| Default | `"eng"` |

Fallback language used by the spaCy backend when an entity carries no detected/declared language.

### `ner_type_model_path`

| Env | `FTM_ANALYZE_NER_TYPE_MODEL_PATH` |
| --- | --- |
| Type | `Path` |
| Default | `./models/model_type_prediction.ftz` |

Path to the fastText classifier used for confidence-based filtering of NER results.

### `ner_type_model_confidence`

| Env | `FTM_ANALYZE_NER_TYPE_MODEL_CONFIDENCE` |
| --- | --- |
| Type | `float` |
| Default | `0.85` |

Minimum classifier confidence for an extracted name to survive filtering. Lower values let more mentions through.

### `lid_model_path`

| Env | `FTM_ANALYZE_LID_MODEL_PATH` |
| --- | --- |
| Type | `Path` |
| Default | `./models/lid.176.ftz` |

Path to the fastText language-identification model used by the language detector.

### `translation_chunk_size`

| Env | `FTM_ANALYZE_TRANSLATION_CHUNK_SIZE` |
| --- | --- |
| Type | `int` |
| Default | `512` |

Character size of the substrings text is split into for language detection.

## Spacy models

The spaCy backend picks a model per detected language. Override individual languages with `FTM_ANALYZE_SPACY_MODELS_<ALPHA3>` (the lookup is nested through pydantic-settings).

| Env | Default |
| --- | --- |
| `FTM_ANALYZE_SPACY_MODELS_ENG` | `en_core_web_sm` |
| `FTM_ANALYZE_SPACY_MODELS_DEU` | `de_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_FRA` | `fr_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_SPA` | `es_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_RUS` | `ru_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_POR` | `pt_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_RON` | `ro_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_MKD` | `mk_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_ELL` | `el_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_POL` | `pl_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_ITA` | `it_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_LIT` | `lt_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_NLD` | `nl_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_NOB` | `nb_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_NOR` | `nb_core_news_sm` |
| `FTM_ANALYZE_SPACY_MODELS_DAN` | `da_core_news_sm` |

## Flair models

Same nesting convention as the spaCy mapping, via `FTM_ANALYZE_FLAIR_MODELS_<ALPHA3>`. Only languages with a maintained Flair NER model are listed; others fall back to whatever flair's defaults are.

| Env | Default |
| --- | --- |
| `FTM_ANALYZE_FLAIR_MODELS_ENG` | `ner` |
| `FTM_ANALYZE_FLAIR_MODELS_DEU` | `de-ner` |
| `FTM_ANALYZE_FLAIR_MODELS_FRA` | `fr-ner` |
| `FTM_ANALYZE_FLAIR_MODELS_SPA` | `es-ner-large` |
| `FTM_ANALYZE_FLAIR_MODELS_NLD` | `nl-ner` |

## BERT / GLiNER

### `bert_model`

| Env | `FTM_ANALYZE_BERT_MODEL` |
| --- | --- |
| Type | `str` |
| Default | `"dslim/bert-base-NER"` |

HuggingFace model id used when `ner_engine="bert"`.

### `gliner_model`

| Env | `FTM_ANALYZE_GLINER_MODEL` |
| --- | --- |
| Type | `str` |
| Default | `"urchade/gliner_small-v2.1"` |

Model id used when `ner_engine="gliner"`.

### `gliner_threshold`

| Env | `FTM_ANALYZE_GLINER_THRESHOLD` |
| --- | --- |
| Type | `float` (0–1) |
| Default | `0.5` |

GLiNER confidence threshold below which predictions are discarded.

## Model cache locations

### `flair_cache_root`

| Env | `FTM_ANALYZE_FLAIR_CACHE_ROOT` or `FLAIR_CACHE_ROOT` |
| --- | --- |
| Type | `Path \| None` |
| Default | `None` |

Override the Flair model cache directory. Useful when mounting an external volume in containers.

### `hf_home`

| Env | `FTM_ANALYZE_HF_HOME` or `HF_HOME` |
| --- | --- |
| Type | `Path \| None` |
| Default | `None` |

HuggingFace cache directory used by the BERT and GLiNER backends.
