import juditha
from anystore.logging import get_logger

from ftm_analyze.analysis.extract.base import NERs, Span
from ftm_analyze.analysis.refine import TYPE_PROPS
from ftm_analyze.analysis.util import SCHEMA_NER

log = get_logger(__name__)

# single words shorter than this are skipped (same floor as juditha's
# multi-token automaton patterns)
MIN_SINGLE_WORD_LENGTH = 8


def handle(text: str) -> NERs:
    """Extract known names via the juditha Aho-Corasick automaton. The schema
    is kept (unlike NER results) so that known names can be emitted as their
    actual entities instead of mentions."""
    for mention in juditha.get_store().extract(text):
        # a short single word is too ambiguous without context (Berlin is a
        # place and a person name), these are left to NER
        if len(mention.text.split()) < 2 and len(mention.text) < MIN_SINGLE_WORD_LENGTH:
            continue
        prop = TYPE_PROPS[SCHEMA_NER.get(mention.schema_, "OTHER")]
        log.debug(f"Juditha: [{prop}] {mention.text}", schema=mention.schema_)
        yield Span(prop, mention.text, mention.start, mention.end, mention.schema_)
