import logging
from typing import Generator

import juditha
from followthemoney import Property, model
from followthemoney.proxy import EntityProxy
from followthemoney.types import registry
from followthemoney.util import make_entity_id
from ftmq.util import make_entity
from juditha.model import NER_TAG, SCHEMA_NER
from normality import slugify
from pydantic import BaseModel, ConfigDict, computed_field
from rigour.names import normalize_name, pick_name

from ftm_analyze.analysis.aggregate import TagAggregator, TagAggregatorFasttext
from ftm_analyze.analysis.extract import (
    extract_ner_bert,
    extract_ner_flair,
    extract_ner_spacy,
)
from ftm_analyze.analysis.language import detect_languages
from ftm_analyze.analysis.patterns import extract_patterns, get_iban_country
from ftm_analyze.analysis.refine import (
    PROPS_NER_TAGS,
    TYPE_PROPS,
    classify_mention,
    classify_name_rigour,
    clean_name,
    refine_location,
)
from ftm_analyze.analysis.util import (
    ANALYZABLE,
    TAG_COMPANY,
    TAG_IBAN,
    TAG_NAME,
    TAG_PERSON,
    text_chunks,
)
from ftm_analyze.annotate.annotator import ANNOTATED, Annotator
from ftm_analyze.settings import Settings

log = logging.getLogger(__name__)
settings = Settings()

MENTIONS = {TAG_COMPANY: "Organization", TAG_PERSON: "Person"}


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
    is_valid: bool = True

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
        refine_mentions: bool | None = settings.refine_mentions,
        validate_names: bool | None = settings.validate_names,
        resolve_mentions: bool | None = settings.resolve_mentions,
    ) -> None:
        # 1. basic NER resolution based on builtin rigour heuristic
        refined_ner = classify_name_rigour(self.caption)
        if refined_ner != "OTHER":
            self.ner_tag = refined_ner
        self.resolved_values = set(
            [clean_name(v, self.ner_tag, normalize_name) for v in self.original_values]
        )

        # 2. use juditha NER classify model to refine
        if refine_mentions:
            self.ner_tag = classify_mention(self.caption, self.ner_tag)
            self.resolved_values = set(
                [
                    clean_name(v, self.ner_tag, normalize_name)
                    for v in self.original_values
                ]
            )
        # 2b. geonames_tagger
        if self.ner_tag == "LOC":
            location = refine_location(self.caption)
            if location is not None:
                self.canonized_value = location.name

        # 3. skip this mention if it is not valid according to juditha
        if validate_names:
            self.is_valid = any(
                juditha.validate_name(n, self.ner_tag) for n in self.resolved_values
            )

        # 4. resolve to actual entity via juditha
        if resolve_mentions:
            for name in self.resolved_values:
                result = juditha.lookup(name)
                if result is not None:
                    self.canonized_value = result.caption
                    self.schema_name = result.common_schema
                    self.ner_tag = SCHEMA_NER.get(result.common_schema, "OTHER")
                    self.resolved_values = set(
                        [
                            clean_name(v, self.ner_tag, normalize_name)
                            for v in self.original_values
                        ]
                    )
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
        schema = MENTIONS.get(self.prop)
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
        validate_names: bool | None = settings.validate_names,
        refine_mentions: bool | None = settings.refine_mentions,
    ):
        self.entity = model.make_entity(entity.schema)
        self.entity.id = entity.id
        self.aggregator_entities = TagAggregatorFasttext()
        self.aggregator_patterns = TagAggregator()
        self.validate_names = validate_names
        self.refine_mentions = refine_mentions
        self.resolve_mentions = resolve_mentions
        self.annotate = annotate
        self.annotator = Annotator(entity)
        if settings.ner_engine == "bert":
            self.ner_extract = extract_ner_bert
        elif settings.ner_engine == "flair":
            self.ner_extract = extract_ner_flair
        else:
            self.ner_extract = extract_ner_spacy

    def feed(self, entity):
        if not entity.schema.is_a(ANALYZABLE):
            return
        texts = entity.get_type_values(registry.text)
        for text in text_chunks(texts):
            detect_languages(self.entity, text)
            for prop, tag in self.ner_extract(self.entity, text):
                self.aggregator_entities.add(prop, tag)
            for prop, tag in extract_patterns(self.entity, text):
                self.aggregator_patterns.add(prop, tag)

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
            mention = Mention(
                key=key,
                entity_id=self.entity.id,
                prop=prop,
                original_values=set(values),
                ner_tag=PROPS_NER_TAGS.get(prop, "OTHER"),
            )
            mention.resolve(
                refine_mentions=self.refine_mentions,
                validate_names=self.validate_names,
                resolve_mentions=self.resolve_mentions,
            )
            if not mention.is_valid:
                continue

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
            for text in self.annotator.get_texts():
                self.entity.add("indexText", f"{ANNOTATED} {text}")

        if results:
            log.debug(
                "Extracted %d prop values, %d mentions, %d entities [%s]: %s",
                results,
                len(mention_ids),
                len(entity_ids),
                self.entity.schema.name,
                self.entity.id,
            )

            yield self.entity

    def make_bankaccount(self, value: str, country: str) -> EntityProxy:
        bank_account = model.make_entity("BankAccount")
        bank_account.id = slugify(f"iban {value}")
        bank_account.add("proof", self.entity.id)
        bank_account.add("accountNumber", value)
        bank_account.add("iban", value)
        bank_account.add("country", country)
        return bank_account
