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
