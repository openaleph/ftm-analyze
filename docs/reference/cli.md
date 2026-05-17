# CLI

`ftm-analyze` exposes a [Typer](https://typer.tiangolo.com/) command-line interface. Run `ftm-analyze --help` to see the same content rendered in your terminal.

## `ftm-analyze`

Top-level entry point. Without a subcommand it prints help.

| Option | Description |
| --- | --- |
| `--version / --no-version` | Print the installed version and exit. |
| `--settings / --no-settings` | Print the current [Settings](./settings.md) (resolved from environment variables and `.env`) and exit. |
| `--install-completion` | Install shell completion for the current shell. |
| `--show-completion` | Print the shell completion script. |
| `--help` | Show help and exit. |

### Commands

- [`download-spacy`](#download-spacy) – fetch the spaCy language models referenced by the current settings.
- [`analyze`](#analyze) – analyze a stream of FollowTheMoney entities.
- [`analyze-text`](#analyze-text) – analyze a single text string (debug helper).

---

## `download-spacy`

```bash
ftm-analyze download-spacy
```

Download the spaCy models referenced by [`FTM_ANALYZE_SPACY_MODELS_*`](./settings.md#spacy-models). The download targets are determined from `Settings().spacy_models`, so override the language-to-model mapping via environment variables before running this command if you want non-default models.

| Option | Description |
| --- | --- |
| `--help` | Show help and exit. |

---

## `analyze`

```bash
ftm-analyze analyze [OPTIONS]
```

Analyze a stream of FollowTheMoney entities. Reads entities from `-i` and writes annotated entities + mention fragments to `-o`. Both URIs go through [`anystore`](https://github.com/dataresearchcenter/anystore), so file paths, `s3://`, `http(s)://`, and database URIs (e.g. `postgresql:///ftm`) all work; `-` means stdin / stdout.

| Option | Default | Description |
| --- | --- | --- |
| `-i TEXT` | `-` | Input entities URI (file, http, s3, …). |
| `-o TEXT` | `-` | Output entities URI (file, http, s3, …). |
| `--resolve-mentions / --no-resolve-mentions` | from [`FTM_ANALYZE_RESOLVE_MENTIONS`](./settings.md#resolve_mentions) | Resolve known mentions against `juditha`. |
| `--annotate / --no-annotate` | from [`FTM_ANALYZE_ANNOTATE`](./settings.md#annotate) | Annotate extracted patterns, names, and mentions in text properties (see [annotate](../annotate.md)). |
| `--validate-names / --no-validate-names` | from [`FTM_ANALYZE_VALIDATE_NAMES`](./settings.md#validate_names) | Drop mentions that `juditha` cannot validate against known name tokens. |
| `--refine-mentions / --no-refine-mentions` | from [`FTM_ANALYZE_REFINE_MENTIONS`](./settings.md#refine_mentions) | Refine NER tag for each mention using extra heuristics + `juditha.lookup`. |
| `--refine-locations / --no-refine-locations` | from [`FTM_ANALYZE_REFINE_LOCATIONS`](./settings.md#refine_locations) | Canonicalize location mentions via `geonames_tagger`. |
| `--overwrite-lang / --no-overwrite-lang` | from [`FTM_ANALYZE_OVERWRITE_LANG`](./settings.md#overwrite_lang) | Ignore any pre-existing `language` property and rewrite `detectedLanguage`. |
| `--help` |  | Show help and exit. |

### Example

```bash
ftm-analyze analyze \
    -i s3://data/entities.ftm.json \
    -o postgresql:///ftm \
    --resolve-mentions \
    --annotate
```

---

## `analyze-text`

```bash
ftm-analyze analyze-text [OPTIONS]
```

Analyze a single text string. The input is wrapped in a synthetic `PlainText` entity (`bodyText`), so this is mainly a debugging shortcut – use [`analyze`](#analyze) for real ingestion runs.

| Option | Default | Description |
| --- | --- | --- |
| `-i TEXT` | `-` | Input text URI (file, http, s3, … – or `-` for stdin). |
| `-o TEXT` | `-` | Output entities URI. |
| `--resolve-mentions / --no-resolve-mentions` | from settings | Resolve known mentions against `juditha`. |
| `--annotate / --no-annotate` | from settings | Annotate extracted patterns, names, and mentions. |
| `--validate-names / --no-validate-names` | from settings | Drop mentions that `juditha` cannot validate. |
| `--refine-mentions / --no-refine-mentions` | from settings | Refine NER tag for each mention. |
| `--refine-locations / --no-refine-locations` | from settings | Canonicalize location mentions. |
| `--help` |  | Show help and exit. |

### Example

```bash
echo "Angela Merkel met Emmanuel Macron in Paris." | ftm-analyze analyze-text
```
