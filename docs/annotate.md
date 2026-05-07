# Annotation

!!! warning
    This is an experimental feature and is likely to change or break fast

After extracting patterns, names and mentions from an Entity's text fields,
`ftm-analyze` can rewrite those text properties in place with per-word
annotation markers. The format is consumed by
[`openaleph-search`](https://github.com/openaleph/openaleph-search) so that
proximity queries can combine free-text and entity-type predicates such as
`"crime __PER__"~5`.

The full search-side spec (Lucene token positions, `pattern_capture` filter,
query syntax) lives in [`annotations.md`](https://github.com/dataresearchcenter/ftm-analyze/blob/main/annotations.md)
at the repo root. This page documents what the *analyzer* emits.

## Format

Each surface word that belongs to an annotated span carries the annotation
markers, joined by Zero-Width Joiner characters (`‍`, written `‍` below).
Markers use the `__CODE__` syntax and are repeated at every surface word of the
span, not just the first or last.

Example `bodyText` of an entity:

```
Serious crime involving Jane Doe at Acme GmbH. Contact: jane@doe.org
```

After annotation, the same property is rewritten in place to:

```
Serious crime involving Jane‍__LEG__‍__PER__‍__janedoe__ Doe‍__LEG__‍__PER__‍__janedoe__ at Acme‍__LEG__‍__ORG__‍__acmegmbh__‍__LLC__ GmbH‍__LEG__‍__ORG__‍__acmegmbh__‍__LLC__. Contact: jane@doe.org‍__EMAIL__
```

Plain text without annotations passes through unchanged. Repeated passes are
idempotent – the regex used for replacement has ZWJ lookarounds that skip
already-decorated words.

## Marker codes

| Code | Source | Notes |
|------|--------|-------|
| `__PER__` | Person mention | `peopleMentioned` |
| `__ORG__` | Organization mention | `companiesMentioned` |
| `__LEG__` | Any legal entity | Always added alongside `__PER__` / `__ORG__` and for bare `namesMentioned` |
| `__EMAIL__` | Pattern extraction | `emailMentioned` |
| `__PHONE__` | Pattern extraction | `phoneMentioned` |
| `__IBAN__` | Pattern extraction | `ibanMentioned` |
| `__LOC__` | Location mention | `locationMentioned` |
| `__<entityid>__` | Slugified canonical name | Only for name annotations (`__janedoe__`, `__acmegmbh__`) |
| `__LLC__`, … | `rigour` `ORG_CLASS` symbols | Org-class symbols are emitted as bare codes (the `ORG_` prefix is stripped). `rigour` maps e.g. `GmbH`, `Ltd`, `Inc` to the generic `LLC` class. |
| `__SYM_EXPORT__`, `__SYM_TECH__`, `__SYM_CORP__`, … | `rigour` `SYMBOL` symbols | Keep the `SYM_` prefix |

`NAME`-category `Q…` symbols from `rigour` are no longer emitted.

### Entity IDs

Each name annotation adds a slug derived from the resolved entity's caption (or
the surface form when no resolution happened):

```python
slugify(normalize_name(canonical), sep="")
```

So `Mrs. Jane Doe` → `__mrsjanedoe__`, `Acme GmbH` → `__acmegmbh__`. The same
ID is repeated on every surface word of the span so phrase queries on the
surface text and proximity queries on the ID both work.

### Pattern mentions

Emails, phones, and IBANs carry only the type marker – no entity ID:

```
jane@doe.org‍__EMAIL__
```

## In-place rewriting

The annotator does **not** produce a separate `indexText` field anymore. There
is no `__annotated__` prefix.

Instead, `Annotator.patch_entity(target)` walks every `text`-typed property on
the source entity (e.g. `bodyText`, `summary`) and writes the annotated value
back onto the *same named property* on the target. Each property is rewritten
independently – `bodyText` stays `bodyText`, `summary` stays `summary`.

The analyzer calls `self.annotator.patch_entity(self.entity)` at the end of
`flush()`, so downstream consumers see the original property names with their
contents annotated.

## Cross-script

Surface forms split on whitespace, so non-Latin scripts decorate per word
without script-aware tokenization:

```
Владимир‍__LEG__‍__PER__‍__vladimirputin__ Путин‍__LEG__‍__PER__‍__vladimirputin__
```

## Overlapping surface forms

Longer surface forms are decorated first. If both `Jane Doe` and `Jane` are
known mentions, the two-word form is matched first, and the lookaround guard
then prevents the standalone `Jane` rule from re-tagging the already-decorated
word. The standalone form still applies wherever `Jane` appears on its own.

## Enable

Annotation is opt-in.

To enable, set the env var `FTM_ANALYZE_ANNOTATE=1` or pass `--annotate` to the
`analyze` / `analyze-text` CLI commands (see [reference](./reference/cli.md)).
