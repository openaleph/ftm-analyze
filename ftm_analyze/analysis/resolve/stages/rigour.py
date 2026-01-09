"""Rigour-based classification stage using name pattern matching."""

from functools import lru_cache

from anystore.logging import get_logger
from rigour.names import (
    Name,
    normalize_name,
    remove_org_prefixes,
    remove_person_prefixes,
    tag_org_name,
    tag_person_name,
    tokenize_name,
)

from ftm_analyze.analysis.resolve.mention import Mention, NerTag
from ftm_analyze.analysis.resolve.pipeline import ResolutionContext

log = get_logger(__name__)
LRU = 10_000


@lru_cache(LRU)
def is_rigour_person(name: str) -> bool:
    """Test if a name exclusively has person name symbols."""
    name = remove_person_prefixes(name)
    tokens_ = tokenize_name(name)
    tokens = [t for t in tokens_ if len(t) > 2]
    if len(tokens_) > len(tokens):
        return False
    seen = 0
    for token in tokens:
        for symbol in tag_person_name(Name(token), normalize_name).symbols:
            if symbol.category.name == "NAME":
                seen += 1
                break
    return seen == len(tokens)


@lru_cache(LRU)
def is_rigour_org(name: str) -> bool:
    """Test if a name contains org type symbols."""
    for symbol in tag_org_name(Name(name), normalize_name).symbols:
        if symbol.category.name == "ORG_CLASS":
            return True
    return False


class RigourStage:
    """Fast heuristic classification using rigour name patterns.

    This stage classifies mentions based on known name patterns:
    - Person names: Detected via rigour name symbols
    - Organization names: Detected via org class symbols (Ltd, Inc, etc.)
    """

    name = "rigour"

    def process(self, mention: Mention, context: ResolutionContext) -> Mention:
        """Classify mention using rigour heuristics."""
        from rigour.names import remove_obj_prefixes

        # Get the best name value to classify
        values = mention.resolved_values or mention.values
        if not values:
            return mention

        # Use first value for classification (could be improved)
        name = next(iter(values))

        # Check for person pattern
        if is_rigour_person(name):
            log.debug("Rigour classified mention", tag="PER", name=name)
            mention.ner_tag = "PER"
            mention.resolved_values = {remove_person_prefixes(n) for n in values}
            return mention

        # Check for organization pattern
        if is_rigour_org(name):
            log.debug("Rigour classified mention", tag="ORG", name=name)
            mention.ner_tag = "ORG"
            mention.resolved_values = {remove_org_prefixes(n) for n in values}
            return mention

        # Even if not classified, clean the values with generic prefix removal
        # This helps with juditha lookup by removing "the", etc.
        if mention.ner_tag == "ORG":
            mention.resolved_values = {remove_org_prefixes(n) for n in values}
        elif mention.ner_tag == "PER":
            mention.resolved_values = {remove_person_prefixes(n) for n in values}
        else:
            mention.resolved_values = {remove_obj_prefixes(n) for n in values}

        return mention


def classify_name_rigour(name: str) -> NerTag:
    """Classify a name using rigour patterns.

    Returns PER, ORG, or OTHER.
    """
    if is_rigour_person(name):
        return "PER"
    if is_rigour_org(name):
        return "ORG"
    return "OTHER"
