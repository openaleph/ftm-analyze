import logging
from itertools import chain
from typing import Generator

from followthemoney import model
from followthemoney.proxy import EntityProxy
from followthemoney.types import registry
from followthemoney.util import make_entity_id

from ftm_analyze.analysis.aggregate import TagAggregator, TagAggregatorFasttext
from ftm_analyze.analysis.extract import extract_entities
from ftm_analyze.analysis.language import detect_languages
from ftm_analyze.analysis.patterns import extract_patterns
from ftm_analyze.analysis.util import (
    ANALYZABLE,
    DOCUMENT,
    TAG_COMPANY,
    TAG_PERSON,
    text_chunks,
)

log = logging.getLogger(__name__)


class Analyzer(object):
    MENTIONS = {TAG_COMPANY: "Organization", TAG_PERSON: "Person"}

    def __init__(self, entity: EntityProxy):
        self.entity = model.make_entity(entity.schema)
        self.entity.id = entity.id
        self.aggregator_entities = TagAggregatorFasttext()
        self.aggregator_patterns = TagAggregator()

    def feed(self, entity):
        if not entity.schema.is_a(ANALYZABLE):
            return
        # HACK: Tables should be mapped, don't try to tag them here.
        if entity.schema.is_a("Table"):
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
        for key, prop, values in results:
            label = values[0]
            if prop.type == registry.name:
                label = registry.name.pick(values)

            schema = self.MENTIONS.get(prop)
            if schema is not None and self.entity.schema.is_a(DOCUMENT):
                mention = model.make_entity("Mention")
                mention.make_id("mention", self.entity.id, prop, key)
                mention_ids.add(mention.id)
                mention.add("resolved", make_entity_id(key))
                mention.add("document", self.entity.id)
                mention.add("name", values)
                mention.add("detectedSchema", schema)
                mention.add("contextCountry", countries)
                yield mention

            self.entity.add(prop, label, cleaned=True, quiet=True)

        if len(results):
            log.debug(
                "Extracted %d prop values, %d mentions [%s]: %s",
                len(results),
                len(mention_ids),
                self.entity.schema.name,
                self.entity.id,
            )

            yield self.entity
