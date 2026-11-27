# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules

1. Don’t assume. Don’t hide confusion. Surface tradeoffs.
2. Minimum code that solves the problem. Nothing speculative.
3. Touch only what you must. Clean up only your own mess.
4. Define success criteria. Loop until verified.

## Editing conventions

- **Preserve existing inline comments.** When editing a file, do not remove inline comments or docstrings that are already there. If you rewrite the surrounding code, carry the comment over and adapt it to the new context. The default behavior of stripping comments you consider redundant does not apply to this repo – the author keeps them intentionally.

## Documentation conventions

Docs live under `docs/` and are built with [zensical](https://zensical.org/) (the project was migrated off mkdocs, so mkdocs-typer2 / mkdocstrings auto-rendering directives no longer execute – hand-write reference content instead).

- **No em dash.** Never write `—` (U+2014). Use the en dash `–` (U+2013) when a dash is needed, or rewrite the sentence with a comma / parenthesis / colon. This applies to markdown, code comments, commit messages, and chat replies.
- **One paragraph, one line.** In markdown, do not hard-wrap paragraphs. Each paragraph must be a single line; let the renderer handle wrapping. Lists, code blocks, and tables follow their normal line-per-item shape.

## Build and Development Commands

```bash
# Install dependencies (poetry required)
make install          # CPU-only torch (all extras except gpu); make install-gpu for the CUDA flavor

# Run tests
make test             # pytest with coverage
poetry run pytest -v tests/test_analyze.py::test_analyze_ner_extract  # single test

# Linting and formatting
make lint             # flake8
make pre-commit       # run all pre-commit hooks (black, isort, flake8, codespell, etc.)

# Type checking
make typecheck        # mypy --strict

# Download spacy models (required before running)
poetry run ftm-analyze download-spacy

# Build package
make build            # or: poetry build
```

## Architecture Overview

`ftm-analyze` processes [FollowTheMoney](https://followthemoney.tech) entities to extract structured information. It's part of the OpenAleph ingestion pipeline.

### Entry Points

- `cli.py`: Typer CLI with `analyze` and `analyze-text` commands
- `tasks.py`: Procrastinate task integration for OpenAleph queue processing
- `logic.py`: Core `analyze_entity()` / `analyze_entities()` functions

### Module Structure

```
ftm_analyze/analysis/
├── analyzer.py           # Analyzer orchestrator (feed/flush), Mention model, lookup_mentions (juditha)
├── extract/              # Extraction layer, each engine a `handle()` yielding `Span`s
│   ├── base.py           # Span, test_name, shared NER helpers
│   ├── spacy.py          # spaCy (default NER)
│   ├── flair.py          # Flair
│   ├── bert.py           # BERT
│   ├── gliner.py         # GLiNER
│   └── juditha.py        # Known names via the juditha Aho-Corasick automaton
├── aggregate.py          # merge_spans, NameAggregator (merge by position, dedupe, opt-in fastText filter), TagAggregator
├── refine.py             # clean_name, is_rigour_org, NER tag <-> property maps
├── patterns.py           # Pattern extraction (emails, phones, IBANs)
├── ft_type_model.py      # Opt-in fastText type model
├── language.py           # Language detection via fastText
├── country.py            # Location-to-country resolution
└── util.py               # Shared utilities and constants
```

### Pipeline Flow

```
Input Entity
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Analyzer.feed() (per text chunk)                            │
│   ├── Language Detection                                    │
│   ├── NER Extraction (spacy/flair/bert/gliner) with offsets │
│   ├── Known Names (juditha automaton) [opt] with offsets    │
│   └── Pattern Extraction (emails, phones, IBANs)            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ NameAggregator                                              │
│   ├── Merge by position (known names win over               │
│   │   overlapping NER results)                              │
│   └── Deduplication (by normalized key)                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Mention.resolve() (NER tag kept, legal form -> ORG)         │
│   └── lookup_mentions() [opt] - link PER/ORG/LOC, same type,│
│       one batch per type, known names skipped               │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Mention.to_entity() / Analyzer.flush()                      │
│   ├── Known / resolved names as entities (Person, ...)      │
│   ├── Mention entities (unresolved PER/ORG)                 │
│   └── BankAccount entities (from IBANs)                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Output: Entity fragments + Annotated source entity
```

**Filtering**: there is no separate noise filter by default (the fastText type model filter is opt-in via `FTM_ANALYZE_NER_TYPE_MODEL_CONFIDENCE`, known names skip it). A name needs a letter and at most 100 chars (`test_name`), GLiNER applies its own confidence threshold, and the NER model's label is trusted: the only re-classification is a legal form in the name (rigour `ORG_CLASS` symbols, e.g. GmbH, e.V.) making it an organization.

**Known names vs. lookup**: the automaton (`FTM_ANALYZE_EXTRACT_KNOWN_NAMES`) finds exact, multi-token known names (single tokens only for places) with their schema, also where NER missed them. The lookup (`FTM_ANALYZE_RESOLVE_MENTIONS`) is fuzzy and covers what the automaton can't: single-word names, spelling variants, inflections, OCR noise. So it only runs on mentions without a schema; known names keep the caption of their surface form, not juditha's canonical caption.

### Key Types

- `Span`: A name found in a text, with its character offsets (and the schema of a known name)
- `Mention`: One aggregated name (NER tag, values, schema of a known name, resolution state), emits its entity via `to_entity()`
- `EntityProxy`: FTM entity output

### Configuration

Settings via environment variables with `FTM_ANALYZE_` prefix (see `settings.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `FTM_ANALYZE_NER_ENGINE` | `spacy` | NER engine: spacy, flair, bert, gliner |
| `FTM_ANALYZE_RESOLVE_MENTIONS` | `false` | Link mentions (PER/ORG/LOC) to known entities via a batched, fuzzy juditha lookup (`lookup_mentions`), skipping known names from the automaton |
| `FTM_ANALYZE_EXTRACT_KNOWN_NAMES` | `false` | Extract known names via the juditha Aho-Corasick automaton (local store, or a `juditha serve` gRPC server via `JUDITHA_URI=grpc://…`), emitted as entities (not Mentions) |
| `FTM_ANALYZE_NER_TYPE_MODEL_CONFIDENCE` | not set | Opt-in fastText type model filter for NER results (model at `FTM_ANALYZE_NER_TYPE_MODEL_PATH`, not in the Docker images) |
| `FTM_ANALYZE_ANNOTATE` | `false` | Rewrite text properties with ZWJ per-word entity markers (see Annotate Module) |

Spacy model overrides: `FTM_ANALYZE_SPACY_MODELS_DEU=de_core_news_lg`
GLiNER settings: `FTM_ANALYZE_GLINER_MODEL`, `FTM_ANALYZE_GLINER_THRESHOLD`

### External Dependencies

- **juditha**: Entity lookup/resolution service, ML classifier
- **rigour**: Name normalization and entity type classification heuristics
- **schwifty**: IBAN validation and parsing
- **countrytagger**: Location-to-country mapping

### Annotate Module

`ftm_analyze/annotate/` produces the ZWJ per-word annotation format consumed by
`openaleph-search` (see `docs/annotate.md` for the authoritative
spec). Each surface word of an annotated span carries ZWJ-joined (`‍`)
markers so annotation tokens and surface words land at the same Lucene position
(via a `pattern_capture` filter on the search side), keeping phrase queries
intact while enabling proximity queries like `"crime __PER__"~5`.

Example output:

```
Jane‍__LEG__‍__PER__‍__janedoe__ Doe‍__LEG__‍__PER__‍__janedoe__
```

**Key behaviors:**

- **In-place replacement.** `Annotator.patch_entity(target)` walks the text-typed
  properties on the annotator's source entity (e.g. `bodyText`, `summary`) and
  writes the annotated version back onto the *same named property* on `target`.
  The analyzer calls `self.annotator.patch_entity(self.entity)` at the end of
  `flush()`; there is no separate `indexText` output anymore.
- **Marker codes.** Type codes reuse the existing short tags (`PER`, `ORG`, `LEG`,
  `EMAIL`, `PHONE`, `IBAN`, `LOC`) wrapped in `__…__`. Each `is_name` annotation
  also emits an entity id derived from `rigour.names.normalize_name(canonical)`
  + `normality.slugify(sep="")`, where `canonical` prefers the resolved entity's
  caption over the raw surface form.
- **Rigour symbols.** `ORG_CLASS` symbols are promoted to bare type-like markers
  with the `ORG_` prefix stripped (`__LLC__`, `__CORP__`, `__GMBH__`); rigour
  maps e.g. `GmbH` to the generic `LLC` class. `SYMBOL`-category codes keep the
  `SYM_` prefix (`__SYM_EXPORT__`). `NAME`-category `Q…` symbols are no longer
  emitted.
- **Pattern mentions** (emails, phones, IBANs) carry the type marker only, no
  entity id.
- **Idempotent.** `Annotation.annotate` uses ZWJ lookarounds so repeated passes
  and overlapping surface forms (`"Jane Doe"` vs `"Jane"`) don't re-decorate
  already-tagged words. `Annotator.annotate_text` applies longer surface forms
  first so the lookaround-guard works correctly.
- **Cross-script.** Surface forms split on whitespace, so Cyrillic/Arabic/etc.
  spans decorate per word without needing script-aware tokenization.

### Test Fixtures

Tests use FTM JSON fixtures in `tests/fixtures/`. The `documents` fixture loads `documents.ftm.json` containing test entities.

### Logging

Uses `structlog` via `anystore.logging.get_logger()`. Log calls use structured kwargs:
```python
log.debug("Extraction accepted", tag=tag, value=value, source=source)
```
