# Analyze Pipeline

## Detected languages

ftm-analyze uses the [fastText](https://fasttext.cc/) text classification library with a [pre-trained model](https://fasttext.cc/docs/en/language-identification.html) to detect the language of the document if it is not specified explicitly.

## Named-entity recognition (NER)

ftm-analyze uses the [SpaCy](https://spacy.io/) natural-language processing (NLP) framework and a number of [pre-trained models](https://spacy.io/) for different languages to extract names of people, organizations, and countries from the text previously extracted from the Word document.

## Extract patterns

In addition to NLP techniques, ftm-analyze also uses [simple regular expressions](https://github.com/dataresearchcenter/ftm-analyze/blob/main/ftm_analyze/analysis/patterns.py) to extract phone numbers, IBAN bank account numbers, and email addresses from documents.

## Write fragments

!!! info
    Under the hood, ftm-analyze uses [followthemoney-store](https://github.com/alephdata/followthemoney-store) to store entity data. [followthemoney-store](https://github.com/alephdata/followthemoney-store) stores entity data as "fragments". Every fragment stores a subset of the properties. [Read more about fragments](https://followthemoney.tech/docs/fragments/)

Any extracted entities or patterns are then stored in a separate entity fragment. Assuming that the Word document uploaded mentions a person named "John Doe", the entity fragment written to the FollowTheMoney Store might look like this:

<table>
  <tr>
    <th>id</th>
    <th>origin</th>
    <th>fragment</th>
    <th>data</th>
  </tr>
  <tr>
    <td>97e1f...</td>
    <td>analyze</td>
    <td>default</td>
    <td>
```json
{
  "schema": "Pages",
  "properties": {
    "peopleMentioned": ["John Doe"],
    "detectedLanguage": ["eng"]
  }
}
```
    </td>
  </tr>
</table>

Additionally, ftm-analyze will also create separate entities for mentions of people and organizations. While this creates some redundancy, it allows OpenAleph to take them into account during cross-referencing. For example, another entity fragment will be written because "John Doe" was recognized as a name of a person:

<table>
  <tr>
    <th>id</th>
    <th>origin</th>
    <th>fragment</th>
    <th>data</th>
  </tr>
  <tr>
    <td>310a4...</td>
    <td>analyze</td>
    <td>default</td>
    <td>
```json
{
  "schema": "Mention",
  "properties": {
    "name": ["John Doe"],
    "document": ["97e1f..."], // ID of the `Pages` entity
    "resolved": ["356aa..."],
    "detectedSchema": ["Person"]
  }
}
```
    </td>
  </tr>
</table>

## Dispatch index task

At the end of the `analyze` task, ftm-analyze dispatches an `index` task. This pushes a task object to the index queue for OpenAleph that includes a payload with the IDs of any entities written in the previous step.


---

> Thanks to [Till Prochaska](https://github.com/tillprochaska) who initially wrote up the pipeline for the original Aleph Documentation
