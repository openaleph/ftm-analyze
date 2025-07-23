# Named Entity and Pattern Extraction

ftm-analyze tries to extract names of people, companies, and countries as well as phone numbers, email addresses and IBANs. This article explains the different steps ftm-analyze performs to extract named entities and patterns and the NLP (Natural Language Processing) technologies ftm-analyze uses.

## Preprocessing

As part of the [ingest pipeline](https://openaleph.org/docs/lib/ingest-file), `ingest-file` extracts text from the files you upload. Before running any entity or pattern extraction, ftm-analyze preprocesses text:

* Whitespace and line-breaks are collapsed.
* Very long text is split into multiple chunks with each chunk containing approximately the amount of text that fits on a single page. In most cases, the entities that are emitted in previous steps of the ingest pipeline shouldn’t contain text that is much longer, so this is mostly there to handle edge cases.

## Language identification

ftm-analyze uses the [fastText LID](https://fasttext.cc/docs/en/language-identification.html) (Language Identification) model which can recognize 176 languages. On one hand, Language identifcations is used to enrich the metadata for files to allow users to filter based on the language of files. On the other hand, it is used as context for subsequent steps, for example in order to select the correct language-specific model for entity extraction.

## Entity extraction

In order to extract named entities (names of people, companies, and countries) from files, ftm-analyze uses spaCy with [language-specific models](https://spacy.io/models). For example, it uses the `en_core_web_sm` model for English language text, and the `es_core_news_sm` model for Spanish language text.

Running text through the spaCy models yields a number of labelled named entities. For example, the sentence …

***"Swiss tobacco giant Philip Morris International (PMI) obtained a stake in a company that won a disputed license to make and market cigarettes in Egypt, one of the world’s most desirable tobacco markets."***

… would result in the following labelled entities:

| Text | Label |
| --- | --- |
| Swiss | NORP |
| Philipp Morris International | ORG |
| PMI | ORG |
| Egypt | GPE |
| one | CARDINAL |

The set of labels returned varies depending on the language-specific model that is used. For example, the `en_core_web_sm` model uses the label `PER` to annotate names of people whereas `es_core_web_sm` uses `PERSON`. Some models also annotate additional entities such as dates or cardinals, but ftm-analyze discards anythings that’s not related to a person, company, or country.

### People

In order to extract names of people, ftm-analyze uses named entities returned by the spaCy model labelled as `PER` or `PERSON` as candidates.

For each of these named entities it normalizes the text by stripping out common prefixes (e.g. removing "Mr." from "Mr. Sherlock Holmes") or removing possessive suffixes ("’s" in "John’s").

The main reason for extracting names of people from files is to find other references to the same people. For this reason, ftm-analyze also discards very short or very long names, as these are usually not as useful in order to achieve this goal or are often false positives.

### Companies

In order to extract companies, ftm-analyze uses named entities returned by the spaCy model labelled as `ORG` as candidates.

Very short or very long names are discarded for the same reasons that people with very short or long names are discarded.

### Countries

In order to extract countries, ftm-analyze uses named entities returned by the spaCy model labelled as `GPE` or `LOC`. These named entities could be countries, but also cities or other administrative areas.

It then uses the [`countrytagger`](https://pypi.org/project/countrytagger/) library to map the extracted entity to a country. Under the hood, `countrytagger` uses the [GeoNames database](https://www.geonames.org/) which includes a wide range of place names from around the world in various languages along with the country the are part of.

This way, ftm-analyze can extract countries even if the name of the country isn’t mentioned literally. For example, if a file mentions "Berlin", ftm-analyze would extract "Germany" as the country.

### Filtering

The default spaCy models are trained on generic web content. Depending on the contents of the files you upload to ftm-analyze, the precision of the named entities returned by these models may vary.

To predict whether a named enttiy returned by a spaCy model likely is a false positive, ftm-analyze uses a custom [fastText classifier model](https://github.com/alephdata/followthemoney-typepredict). This model is trained on structured data (for proper names of people and companies) as well as random text samples from documents (for text snippets that are not names of people or companies).

(The model was initially developed for a slightly different purpose and predicts multiple labels for a given text, but ftm-analyze currently only uses the fact whether `trash` is one of the predicted labels.)

## Pattern extraction

ftm-analyze also extracts phone numbers, email addresses, and IBANs from files using regular expressions. This is a simple approach and definitely not bullet-proof, but it does handle quite a few cases. The extracted data is normalized:

* Phone numbers are formatted in E.164 format (e.g. `+491234567890`).
* IBANS are stripped of separators and whitespace (e.g. `GR1601101050000010547023795`)
* Email addresses are lower-cased and domain names are normalized.

## Indexing

ftm-analyze stores the extracted data in FollowTheMoney properties like `companiesMentioned`, `detectedLanguage`, or `phoneMentioned` (see the [`Analyzable`](https://followthemoney.tech/explorer/schemata/Analyzable/) schema for details). This means that you can use them in search queries as any other property. For example, the following query would return all files that mention the phone number `+491234567890`:

```
properties.phoneMentioned:"+491234567890
```

ftm-analyze also stores each extracted person or company as a [Mention](https://followthemoney.tech/explorer/schemata/Mention/) entity in order to simplify queries for [cross-referencing](/developers/explanation/cross-referencing).

## Limitations and known issues

### Extracting entities in (semi-)structured data

The default spaCy models ftm-analyze uses are trained on generic web content. They tend to show lower recall for (semi-)structured data such as listings from database websites. If you’re handling (semi-)structured files, we recommend that you manually parse the relevant data from these documents.

### Viewing extracted data in the UI

[OpenAleph](https://openaleph.org) currently doesn’t display all extracted data in the UI. The "Mentions" tab for a file will only list names of people and companies, email addresses, phone numbers, IBANs, and addresses if there is at least one other occurrence of the mention in another dataset or investigation the current user has access to.

For example, if you upload a PDF document to OpenAleph that mentions the company name "ACME, Inc.", it will only be displayed in the "Mentions" tab if searching for "ACME, Inc." in OpenAleph would return at least one result.


---

> Thanks to [Till Prochaska](https://github.com/tillprochaska) who initially wrote up this documentation for the original Aleph Documentation
