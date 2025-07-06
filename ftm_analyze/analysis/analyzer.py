import logging
from itertools import chain
from typing import Generator

import juditha
from followthemoney import model
from followthemoney.proxy import EntityProxy
from followthemoney.types import registry
from followthemoney.util import make_entity_id
from normality import collapse_spaces

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
from ftm_analyze.settings import Settings

log = logging.getLogger(__name__)
settings = Settings()


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
        self.texts: list[str] = []

    def feed(self, entity):
        if not entity.schema.is_a(ANALYZABLE):
            return
        # HACK: Tables should be mapped, don't try to tag them here.
        if entity.schema.is_a("Table"):
            return

        self.texts = [collapse_spaces(t) for t in entity.get_type_values(registry.text)]
        for text in text_chunks(self.texts):
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

            resolved = False
            if label and self.resolve_mentions:
                # convert mentions in actual entities if their names are known
                lookup = juditha.lookup(label)
                if lookup is not None:
                    proxy = self.make_entity(key, values, lookup.schema_, countries)
                    mention_ids.add(proxy.id)
                    yield proxy
                    resolved = True

                    # annotate text mention
                    if self.annotate:
                        self.texts = self.annotate_texts(label, lookup)

            if not resolved:
                # otherwise create Mention entities
                schema = self.MENTIONS.get(prop)
                if schema is not None and self.entity.schema.is_a(DOCUMENT):
                    mention = self.make_mention(prop, key, values, schema, countries)
                    mention_ids.add(mention.id)
                    yield mention

            self.entity.add(prop, label, cleaned=True, quiet=True)

        self.entity.set("indexText", self.texts)

        if len(results):
            log.debug(
                "Extracted %d prop values, %d mentions [%s]: %s",
                len(results),
                len(mention_ids),
                self.entity.schema.name,
                self.entity.id,
            )

            yield self.entity

    def make_mention(self, prop, key, values, schema, countries) -> EntityProxy:
        mention = model.make_entity("Mention")
        mention.make_id("mention", self.entity.id, prop, key)
        mention.add("resolved", make_entity_id(key))
        mention.add("document", self.entity.id)
        mention.add("name", values)
        mention.add("detectedSchema", schema)
        mention.add("contextCountry", countries)
        return mention

    def make_entity(self, key, values, schema, countries) -> EntityProxy:
        proxy = model.make_entity(schema)
        proxy.id = make_entity_id(key)
        proxy.add("proof", self.entity.id)
        proxy.add("name", values)
        proxy.add("country", countries)
        return proxy

    def annotate_texts(self, name: str, result: juditha.store.Result) -> list[str]:
        """
        Annotate full text according to
        https://www.elastic.co/docs/reference/elasticsearch/plugins/mapper-annotated-text-usage
        """
        names = "&".join(n.replace(" ", "+") for n in result.names)
        if result.schema_:
            repl = f"[{name}]({names}&{result.schema_})"
        else:
            repl = f"[{name}]({names})"
        return [t.replace(name, repl) for t in self.texts]
