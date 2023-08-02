import logging
from itertools import chain
from typing import Generator

import juditha
from followthemoney import model
from followthemoney.proxy import EntityProxy
from followthemoney.types import registry
from followthemoney.util import make_entity_id
from rigour.names import pick_name

from ftm_analyze.analysis.aggregate import TagAggregator, TagAggregatorFasttext
from ftm_analyze.analysis.extract import extract_entities
from ftm_analyze.analysis.language import detect_languages
from ftm_analyze.analysis.patterns import extract_patterns
from ftm_analyze.analysis.util import (
    ANALYZABLE,
    DOCUMENT,
    TAG_COMPANY,
    TAG_IBAN,
    TAG_PERSON,
    text_chunks,
)
from ftm_analyze.annotate import ANNOTATED, NAMED, Annotator
from ftm_analyze.settings import Settings

log = logging.getLogger(__name__)
settings = Settings()


STOP_EXTENDS = (
    "Thing",
    "Value",
)


class Analyzer(object):
    MENTIONS = {TAG_COMPANY: "Organization", TAG_PERSON: "Person"}

    def __init__(
        self,
        entity: EntityProxy,
        resolve_mentions: bool | None = settings.resolve_mentions,
        annotate: bool | None = settings.annotate,
    ):
        self.entity = model.make_entity(entity.schema)
        self.entity.id = entity.id
        self.aggregator_entities = TagAggregatorFasttext()
        self.aggregator_patterns = TagAggregator()
        self.resolve_mentions = resolve_mentions
        self.annotate = annotate
        self.annotator = Annotator(entity)

    def feed(self, entity):
        if not entity.schema.is_a(ANALYZABLE):
            return
        texts = entity.get_type_values(registry.text)
        for text in text_chunks(texts):
            detect_languages(self.entity, text)
            for prop, tag in extract_entities(self.entity, text):
                self.aggregator_entities.add(prop, tag)
            for prop, tag in extract_patterns(self.entity, text):
                self.aggregator_patterns.add(prop, tag)

    def flush(self) -> Generator[EntityProxy, None, None]:
        countries = set()
        results = list(
            chain(
                self.aggregator_entities.results(), self.aggregator_patterns.results()
            )
        )

        for key, prop, _ in results:
            if prop.type == registry.country:
                countries.add(key)

        mention_ids = set()
        entity_ids = set()

        for key, prop, values in results:
            label = values[0]
            if prop.type == registry.name:
                label = pick_name(values)

            resolved = False
            proxy = None
            if values and self.resolve_mentions and prop.name in NAMED:
                # convert mentions in actual entities if their names are known
                for value in values:
                    lookup = juditha.lookup(value)
                    if lookup is not None:
                        proxy = self.make_entity(key, values, lookup, countries)
                        entity_ids.add(proxy.id)
                        yield proxy
                        resolved = True

                        break

            elif prop == TAG_IBAN:
                for value in values:
                    iban_proxy = self.make_bankaccount(value, countries)
                    entity_ids.add(iban_proxy.id)
                    yield iban_proxy

            # annotate mentions
            if self.annotate and proxy is not None:
                for value in values:
                    self.annotator.add_mention(value, proxy)

            if not resolved:
                # otherwise create Mention entities
                schema = self.MENTIONS.get(prop)
                if schema is not None and self.entity.schema.is_a(DOCUMENT):
                    mention = self.make_mention(prop, key, values, schema, countries)
                    mention_ids.add(mention.id)
                    yield mention

                # annotate named mentions
                if self.annotate:
                    for value in values:
                        self.annotator.add_tag(prop, value)

            self.entity.add(prop, label, cleaned=True, quiet=True)

        if self.annotate:
            for text in self.annotator.get_texts():
                self.entity.add("indexText", f"{ANNOTATED} {text}")

        if len(results):
            log.debug(
                "Extracted %d prop values, %d mentions, %d entities [%s]: %s",
                len(results),
                len(mention_ids),
                len(entity_ids),
                self.entity.schema.name,
                self.entity.id,
            )

            yield self.entity

    def make_mention(
        self, prop, key, values, schema, countries: set[str] | None = None
    ) -> EntityProxy:
        mention = model.make_entity("Mention")
        mention.make_id("mention", self.entity.id, prop, key)
        mention.add("resolved", make_entity_id(key))
        mention.add("document", self.entity.id)
        mention.add("name", values)
        mention.add("detectedSchema", schema)
        mention.add("contextCountry", countries)
        return mention

    def make_entity(
        self, key, values, result, countries: set[str] | None = None
    ) -> EntityProxy:
        proxy = model.make_entity(result.common_schema)
        proxy.id = make_entity_id(key)
        proxy.add("proof", self.entity.id)
        proxy.add("name", values)
        proxy.add("name", result.caption)
        proxy.add("country", countries)
        return proxy

    def make_bankaccount(
        self, value: str, countries: set[str] | None = None
    ) -> EntityProxy:
        bank_account = model.make_entity("BankAccount")
        bank_account.make_id("iban", self.entity.id, value)
        bank_account.add("proof", self.entity.id)
        bank_account.add("iban", value)
        bank_account.add("country", countries)
        return bank_account
