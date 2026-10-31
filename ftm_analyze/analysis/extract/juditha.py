from typing import Generator, TypeAlias

import juditha
from anystore.logging import get_logger
from followthemoney import Property

from ftm_analyze.analysis.refine import TYPE_PROPS
from ftm_analyze.analysis.util import SCHEMA_NER

log = get_logger(__name__)

KnownNames: TypeAlias = Generator[tuple[Property, str, str], None, None]


def handle(text: str) -> KnownNames:
    """Extract known names via the juditha Aho-Corasick automaton, yields
    (prop, value, schema). The schema is kept (unlike NER results) so that
    known names can be emitted as their actual entities instead of mentions."""
    for mention in juditha.get_store().extract(text):
        prop = TYPE_PROPS[SCHEMA_NER.get(mention.schema_, "OTHER")]
        log.debug(f"Juditha: [{prop}] {mention.text}", schema=mention.schema_)
        yield prop, mention.text, mention.schema_
