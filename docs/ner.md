# Named Entity Recognition

!!! info
    Entity extraction builds on top off how `ingest-file` originally extracted mentioned Entities. [Read more](./extraction.md)

Originally `ingest-file` filtered the entities returned by `spaCy` with a custom schema prediction model trained on existing _FollowTheMoney_ data. Based on that, [`Mention`](https://followthemoney.tech/explorer/schemata/Mention/)-Entities are created. These mentions are resolved into actual _Entities_ (e.g. Company, Person) during [cross-referencing](https://openaleph.org/docs/user-guide/103/cross-reference/) datasets.

This creates a problem for "smaller" [OpenAleph](https://openaleph.org) instances: If there is not enough data to cross-reference with, these `Mention` entities would never resolved. As well when using the analysis standalone.

`ftm-analyze` introduces an improvement to this problem: Extracted names can be compared against [juditha](https://github.com/dataresearchcenter/juditha), and if they are known, the _resolved entities_ are returned instead of _mentions_.

[juditha](https://github.com/dataresearchcenter/juditha) allows a fast lookup (based on [tantivy](https://github.com/quickwit-oss/tantivy/)) against a set of known names (from _FollowTheMoney_ data). The index can be populated by [reference datasets](https://dataresearchcenter.org/library) such as company registries, sanctions lists, or PEPs.

## Set up juditha

[documentation](https://github.com/dataresearchcenter/juditha/)

Configure the juditha store uri:

    export JUDITHA_URI=/path/to/store.db

For example, to load all [PEPs by OpenSanctions](https://www.opensanctions.org/datasets/peps/):

    juditha load-dataset -i https://data.opensanctions.org/datasets/latest/peps/index.json
    juditha build

When using `ftm-analyze` now, it will turn known person names into actual `Person` entities (instead of _mentions_) if they are within this PEPs list (including fuzzy matching).

### juditha server

Instead of opening the store in every `ftm-analyze` worker, juditha can serve it (read-only) over gRPC. Point `JUDITHA_URI` at the server and all juditha-backed features (`resolve_mentions`, `validate_names`, `refine_mentions`, `extract_known_names`) run against it, no other configuration needed:

    juditha serve  # next to the store, binds localhost:50051 by default, see --host / --port
    export JUDITHA_URI=grpc://juditha-host:50051

If the server is unreachable, the analysis fails (instead of silently skipping juditha).

## Extract known names

NER only finds what its model recognizes, and the fastText confidence filter drops extracted names it is unsure about (e.g. "Bundesamt für Verfassungsschutz"), even if they are in the juditha index. With `extract_known_names` enabled, `ftm-analyze` additionally scans every text in one pass for all names juditha knows, using the Aho-Corasick automaton that `juditha build` writes into the store (`automaton.txt`).

    export FTM_ANALYZE_EXTRACT_KNOWN_NAMES=true

or per run:

    ftm-analyze analyze -i entities.ftm.json --extract-known-names

How it behaves:

- Matching is case and accent insensitive and aligned to token boundaries. Only multi-token names of at least 8 normalized characters are in the automaton (single-token names are too noisy), see `JUDITHA_MIN_TOKEN_LENGTH`.
- It runs in addition to the configured NER engine, on the same schemata plus `Table` (NER skips `Table`, `Folder`, `Package`, `Workbook`). A name found by both is deduplicated.
- For a `Table`, each (non-numeric) cell is matched on its own, so a name split across two cells is not found. With a juditha server this means one request per distinct cell value.
- Hits skip the fastText confidence filter, as they are exact matches of known names.
- Hits are emitted as entities with the schema juditha knows for the name (e.g. `Person`, `Company`, `PublicBody`, or `LegalEntity` if the sources disagree) instead of `Mention` entities, the same way `resolve_mentions` does it. The entity carries the source document as `proof`. The rigour heuristics and `validate_names` don't override or drop them. If `resolve_mentions` is enabled as well, the juditha lookup still runs for them to pick up the canonical name.
- Where the automaton lives depends on `JUDITHA_URI`. With a local store path, each worker process loads it lazily on the first extraction and keeps it for its lifetime, which for large juditha stores costs memory per worker and some startup time on the first document. With a [juditha server](#juditha-server) (`grpc://…`), extraction runs on the server, which holds the automaton once for all workers.
- If the juditha store has no automaton (`juditha build` has not run), nothing is extracted and no error is raised.
