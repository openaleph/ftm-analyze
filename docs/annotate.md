# Annotation

!!! warning
    This is an experimental feature and is likely to change or break fast

After extracting patterns, names and mentions from an Entities text fields, `ftm-analyze` can store annotations in the `indexText` field for the extracted tokens following the specification from the _markdown-like_ syntax of the [Elasticsearch annotated text plugin](https://www.elastic.co/docs/reference/elasticsearch/plugins/mapper-annotated-text-usage).

Example `bodyText` of an entity:

```
Tenetur totam ea adipisci. jane@doe.org Dolores.
```

During _analysis_, the email address will be detected and extracted as a pattern. Then, the resulting `indexText` of this Entity will contain the annotation for the [`emailMentioned`](https://followthemoney.tech/explorer/schemata/Analyzable/#emailMentioned) property.

```
Tenetur totam ea adipisci. [jane@doe.org](p_emailMentioned) Dolores.
```

To know that this `indexText` is annotated, a `__annotated__` prefix is added.

## Parsing

Applications can parse the annotated text knowing these conventions:

- Schema annotation: `c_<schema>` (it will include parent schemata)
    - Example: `[Jane Doe](s_Person&s_LegalEntity)`
- Fingerprints annotation (via [rigour.names](http://rigour.followthemoney.tech/names/)): `f_<value>`
    - Example: `[Jane Doe](f_doe+jane)`
- Pattern annotation ([available properties](https://followthemoney.tech/explorer/schemata/Analyzable/)): `p_<prop>`
    - Example: `[Jane Doe](p_namesMentioned)`

If extracted as a mentioned `Person`, Mrs. Jane Doe would actually look like this:

```
[Mrs. Jane Doe](f_doe+jane&f_mrs+jane+doe&s_Person&s_LegalEntity&p_namesMentioned&p_peopleMentioned)
```

## Disable

Annotating into `indexText` is the default behaviour.

To disable this feature, set env var `FTM_ANALYZE_ANNOTATE=0` or use the command-line flag (see [reference](./reference/cli.md))
