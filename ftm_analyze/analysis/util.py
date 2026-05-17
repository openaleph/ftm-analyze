from typing import Literal, TypeAlias

from followthemoney import model
from normality import collapse_spaces

ANALYZABLE = model["Analyzable"]
DOCUMENT = model["Document"]
TAG_NAME = ANALYZABLE.properties["namesMentioned"]
TAG_PERSON = ANALYZABLE.properties["peopleMentioned"]
TAG_COMPANY = ANALYZABLE.properties["companiesMentioned"]
TAG_LANGUAGE = ANALYZABLE.properties["detectedLanguage"]
TAG_COUNTRY = ANALYZABLE.properties["detectedCountry"]
TAG_EMAIL = ANALYZABLE.properties["emailMentioned"]
TAG_PHONE = ANALYZABLE.properties["phoneMentioned"]
TAG_IBAN = ANALYZABLE.properties["ibanMentioned"]
TAG_LOCATION = ANALYZABLE.properties["locationMentioned"]

# Used to be `juditha.model.NER_TAG`; juditha dropped this in its 4.x cleanup.
NER_TAG: TypeAlias = Literal["PER", "ORG", "LOC", "OTHER"]

# Map FTM common-schema names to our coarse NER tag. Used to project
# `juditha.lookup` results (which carry a `common_schema`) back onto the
# four-way NER tag space the analyzer uses.
SCHEMA_NER: dict[str, NER_TAG] = {
    "LegalEntity": "OTHER",
    "PublicBody": "ORG",
    "Company": "ORG",
    "Organization": "ORG",
    "Person": "PER",
    "Address": "LOC",
}


def text_chunks(texts, sep=" ", max_chunk=25000):
    """Pre-chew text snippets for NLP and pattern matching."""
    for text in texts:
        text = collapse_spaces(text)
        if text is None or len(text) < 5:
            continue
        # Crudest text splitting code in documented human history.
        # Most of the time, a single page of text is going to be
        # 3000-4000 characters, so this really only kicks in if
        # something weird is happening in the first place.
        for idx in range(0, len(text), max_chunk):
            yield text[idx : idx + max_chunk]
