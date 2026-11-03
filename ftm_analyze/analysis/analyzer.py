import logging
import textwrap
from typing import Generator

import juditha
from followthemoney import Property, model
from followthemoney.proxy import EntityProxy
from followthemoney.types import registry
from followthemoney.util import make_entity_id
from ftmq.util import make_entity
from normality import slugify
from pydantic import BaseModel, ConfigDict, computed_field
from rigour.names import normalize_name, pick_name

from ftm_analyze.analysis.aggregate import NameAggregator, TagAggregator
from ftm_analyze.analysis.country import location_country
from ftm_analyze.analysis.extract import (
    extract_bert,
    extract_flair,
    extract_gliner,
    extract_juditha,
    extract_spacy,
)
from ftm_analyze.analysis.language import detect_languages
from ftm_analyze.analysis.patterns import extract_patterns, get_iban_country
from ftm_analyze.analysis.refine import (
    PROPS_NER_TAGS,
    TYPE_PROPS,
    clean_name,
    is_rigour_org,
    refine_location,
)
from ftm_analyze.analysis.util import (  # is_numeric,
    ANALYZABLE,
    NER_TAG,
    SCHEMA_NER,
    TAG_COMPANY,
    TAG_COUNTRY,
    TAG_IBAN,
    TAG_NAME,
    TAG_PERSON,
    text_chunks,
)
from ftm_analyze.annotate.annotator import Annotator
from ftm_analyze.settings import Settings

log = logging.getLogger(__name__)
settings = Settings()

MENTIONS = {TAG_COMPANY: "Organization", TAG_PERSON: "Person"}
SKIP_NER = ("Folder", "Package", "Table", "Workbook")


def should_ner(e: EntityProxy) -> bool:
    return e.schema.is_a("Analyzable") and e.schema.name not in SKIP_NER


class Mention(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str
    entity_id: str
    prop: Property
    original_values: set[str]
    resolved_values: set[str] = set()
    canonized_value: str | None = None
    schema_name: str | None = None
    ner_tag: NER_TAG = "OTHER"

    @property
    def resolved_prop(self) -> Property:
        return TYPE_PROPS.get(self.ner_tag, TAG_NAME)

    @computed_field
    @property
    def caption(self) -> str:
        if self.canonized_value:
            return self.canonized_value
        if self.resolved_values:
            caption = pick_name(list(self.resolved_values))
        else:
            caption = pick_name(list(self.original_values))
        if caption is None:
            raise ValueError("No caption as of empty values")
        return caption

    @computed_field
    @property
    def names(self) -> set[str]:
        names: set[str] = set()
        names.add(self.caption)
        names.update(self.original_values)
        names.update(self.resolved_values)
        names = {clean_name(n, self.ner_tag, normalize_name) for n in names}
        return {n for n in names if n}

    @computed_field
    @property
    def annotate_values(self) -> set[str]:
        values = self.original_values
        values = {clean_name(v, self.ner_tag) for v in values}
        return {v for v in values if v}

    def resolve(
        self,
        resolve_mentions: bool | None = settings.resolve_mentions,
        refine_locations: bool | None = settings.refine_locations,
    ) -> None:
        # the NER tag is kept (the model saw the context), only a legal form in
        # the name (rigour org class symbols, e.g. GmbH, e.V.) makes it an
        # organization. Known names (from the juditha automaton) already carry
        # their schema, so they skip this.
        if self.schema_name is None and is_rigour_org(self.caption):
            self.ner_tag = "ORG"
        self.resolved_values = set(
            [clean_name(v, self.ner_tag, normalize_name) for v in self.original_values]
        )

        # 1. geonames_tagger
        if refine_locations and self.ner_tag == "LOC":
            location = refine_location(self.caption)
            if location is not None:
                self.canonized_value = location.name

        # 2. juditha lookup: links persons and organizations to known entities
        # of the same type, one pass over the resolved values, the first hit
        # becomes the resolved entity
        if resolve_mentions and self.ner_tag in ("PER", "ORG"):
            schemata = tuple(s for s, tag in SCHEMA_NER.items() if tag == self.ner_tag)
            for name in self.resolved_values:
                result = juditha.lookup(name, schemata=schemata)
                if result is None:
                    continue
                self.canonized_value = result.caption
                self.schema_name = result.common_schema
                return

    def to_entity(self) -> EntityProxy | None:
        if self.schema_name:
            return make_entity(
                {
                    "id": make_entity_id(self.key),
                    "schema": self.schema_name,
                    "caption": self.caption,
                    "properties": {"name": list(self.names), "proof": [self.entity_id]},
                }
            )
        schema = MENTIONS.get(self.resolved_prop)
        if schema:
            mention = model.make_entity("Mention")
            mention.make_id("mention", self.entity_id, self.prop.name, self.key)
            mention.add("resolved", make_entity_id(self.key))
            mention.add("document", self.entity_id)
            mention.add("name", self.names)
            mention.add("detectedSchema", schema)
            return mention


class Analyzer:
    def __init__(
        self,
        entity: EntityProxy,
        resolve_mentions: bool | None = settings.resolve_mentions,
        annotate: bool | None = settings.annotate,
        refine_locations: bool | None = settings.refine_locations,
        extract_known_names: bool | None = settings.extract_known_names,
    ):
        self.entity = model.make_entity(entity.schema)
        self.entity.id = entity.id
        if entity.get("language", quiet=True):
            self.entity.set("language", entity.get("language"))
        if entity.get("detectedLanguage", quiet=True):
            self.entity.set("detectedLanguage", entity.get("detectedLanguage"))
        self.aggregator_entities = NameAggregator()
        self.aggregator_patterns = TagAggregator()
        self.refine_locations = refine_locations
        self.resolve_mentions = resolve_mentions
        self.annotate = annotate
        self.annotator = Annotator(entity)
        # known names are exact matches, so (unlike NER) they are extracted from
        # Table cells as well
        self.extract_known_names = bool(extract_known_names) and (
            should_ner(entity) or entity.schema.is_a("Table")
        )
        self.ner_extract = None
        if should_ner(entity):
            if settings.ner_engine == "bert":
                self.ner_extract = extract_bert
            elif settings.ner_engine == "flair":
                self.ner_extract = extract_flair
            elif settings.ner_engine == "gliner":
                self.ner_extract = extract_gliner
            else:
                self.ner_extract = extract_spacy

    def feed(self, entity, overwrite_lang=False):
        if not entity.schema.is_a(ANALYZABLE):
            return
        texts = entity.get_type_values(registry.text)
        # overwrite_lang to completely delete all detectedLanguage values?
        if overwrite_lang and entity.has("detectedLanguage", quiet=True):
            self.entity.pop("detectedLanguage")
        values = texts
        # FIXME table handling
        # if entity.schema.is_a("Table"):
        # case for Tables: "texts" is an endless list of cell values, need
        # to sort out numbers, concat to chunk larger
        # values = {t for t in texts if not is_numeric(t)}
        # texts = [" ".join(values)]

        for text in text_chunks(texts):
            for subsection in textwrap.wrap(text, settings.translation_chunk_size):
                detect_languages(self.entity, subsection)
            if self.ner_extract:
                spans = list(self.ner_extract(self.entity, text))
                if self.extract_known_names:
                    # known names of the same text, merged with the NER results
                    # by position
                    spans.extend(extract_juditha(text))
                self.aggregator_entities.add_spans(spans)
            for prop, tag in extract_patterns(self.entity, text):
                self.aggregator_patterns.add(prop, tag)

        if self.extract_known_names and not self.ner_extract:
            # match per text value: for Tables per cell, as names would match
            # across the (unordered) cells concatenated above
            for text in text_chunks(values):
                self.aggregator_entities.add_spans(extract_juditha(text))

    def flush(self) -> Generator[EntityProxy, None, None]:
        countries = set()
        mention_ids = set()
        entity_ids = set()
        results = 0

        if self.entity.id is None:
            raise ValueError("Entity has no ID!")

        # patterns
        for _, prop, values in self.aggregator_patterns.results():
            if prop.type == registry.country:
                countries.update(values)
            elif prop == TAG_IBAN:
                for value in values:
                    country = get_iban_country(value)
                    if country is not None:
                        iban_proxy = self.make_bankaccount(value, country)
                        entity_ids.add(iban_proxy.id)
                        yield iban_proxy
            self.entity.add(prop, values, cleaned=True, quiet=True)
            results += 1
            if self.annotate:
                for value in values:
                    self.annotator.add_tag(prop, value)

        # NER mentions
        for key, prop, values in self.aggregator_entities.results():
            if not key:
                continue
            mention = Mention(
                key=key,
                entity_id=self.entity.id,
                prop=prop,
                original_values=set(values),
                ner_tag=PROPS_NER_TAGS.get(prop, "OTHER"),
                schema_name=self.aggregator_entities.get_schema(key, prop),
            )
            mention.resolve(
                resolve_mentions=self.resolve_mentions,
                refine_locations=self.refine_locations,
            )
            if mention.ner_tag == "LOC":
                for value in values:
                    self.entity.add(
                        TAG_COUNTRY, location_country(value), cleaned=True, quiet=True
                    )

            entity = mention.to_entity()
            if entity is not None:
                if entity.schema.is_a("Mention"):
                    mention_ids.add(entity.id)
                    entity.add("contextCountry", countries)
                else:
                    entity_ids.add(entity.id)
                    if not entity.schema.is_a("Address"):
                        entity.add("country", countries)
                yield entity

            # annotate mentions
            if self.annotate:
                if entity is not None and entity.schema.is_a("LegalEntity"):
                    for value in mention.annotate_values:
                        self.annotator.add_mention(value, entity)
                else:
                    for value in values:
                        self.annotator.add_tag(mention.resolved_prop, value)

            self.entity.add(
                mention.resolved_prop, mention.resolved_values, cleaned=True, quiet=True
            )
            self.entity.add("country", countries)
            results += 1

        if self.annotate:
            self.annotator.patch_entity(self.entity)

        if results:
            log.debug(
                "Extracted %d prop values, %d mentions, %d entities [%s]: %s",
                results,
                len(mention_ids),
                len(entity_ids),
                self.entity.schema.name,
                self.entity.id,
            )

        # always get the base entity, it might has detectedLanguage patched
        yield self.entity

    def make_bankaccount(self, value: str, country: str) -> EntityProxy:
        bank_account = model.make_entity("BankAccount")
        bank_account.id = slugify(f"iban {value}")
        bank_account.add("proof", self.entity.id)
        bank_account.add("accountNumber", value)
        bank_account.add("iban", value)
        bank_account.add("country", country)
        return bank_account
