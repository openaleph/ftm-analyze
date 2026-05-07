"""
Annotate entity mentions as per-word ZWJ markers in indexText.

See ``annotations.md`` for the full spec and rationale. Short version:

    Jane‍__PER__‍__doejane__ Doe‍__PER__‍__doejane__

Each surface word of an annotated span carries the annotation markers, joined
by ZWJ (U+200D) characters. ``openaleph-search`` tokenizes this back into
same-position terms via a ``pattern_capture`` filter so proximity queries like
``"crime __PER__"~5`` work while phrase queries on surface text are unaffected.
"""

import re
from typing import Self

from followthemoney import E, EntityProxy, Property, Schema, model, registry
from normality import collapse_spaces, slugify
from pydantic import BaseModel
from rigour.names import normalize_name, pick_name

from ftm_analyze.analysis.util import (
    TAG_COMPANY,
    TAG_EMAIL,
    TAG_IBAN,
    TAG_LOCATION,
    TAG_NAME,
    TAG_PERSON,
    TAG_PHONE,
)
from ftm_analyze.annotate.symbols import get_symbol_annotations

ZWJ = "‍"
MENTION_TYPES = {
    TAG_NAME.name: "LEG",
    TAG_PERSON.name: "PER",
    TAG_COMPANY.name: "ORG",
    TAG_EMAIL.name: "EMAIL",
    TAG_PHONE.name: "PHONE",
    TAG_IBAN.name: "IBAN",
    TAG_LOCATION.name: "LOC",
}
PER = "Person"
ORG = "Organization"
LEG = "LegalEntity"
NAMED = {TAG_COMPANY.name, TAG_PERSON.name, TAG_NAME.name}
HTML_TAG_RE = r"<[^>]*>"


def clean_text(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(HTML_TAG_RE, " ", text)
    return collapse_spaces(text) or ""


def _entity_id(value: str) -> str | None:
    normalized = normalize_name(value)
    if not normalized:
        return None
    slug = slugify(normalized, sep="")
    return slug or None


class Annotation(BaseModel):
    """A single annotated surface form and its markers.

    Emits ZWJ-joined per-word markers on ``annotate``:

        Jane‍__PER__‍__doejane__ Doe‍__PER__‍__doejane__
    """

    value: str
    canonical: str | None = None
    names: set[str] = set()
    props: set[str] = set()

    @property
    def is_name(self) -> bool:
        return bool(NAMED & self.props)

    @property
    def symbols(self) -> set[str]:
        if self._schema:
            return get_symbol_annotations(self._schema, *self._names)
        return set()

    @property
    def _names(self) -> set[str]:
        if self.is_name:
            return set([self.value, *self.names])
        return set()

    @property
    def _type_codes(self) -> set[str]:
        codes = {MENTION_TYPES[p] for p in self.props if p in MENTION_TYPES}
        if self.is_name:
            codes.add(MENTION_TYPES[TAG_NAME.name])
        return codes

    @property
    def entity_id(self) -> str | None:
        if not self.is_name:
            return None
        return _entity_id(self.canonical or self.value)

    @property
    def _schema(self) -> Schema | None:
        if self.is_name:
            if TAG_PERSON.name in self.props:
                return model[PER]
            if TAG_COMPANY.name in self.props:
                return model[ORG]
            return model[LEG]

    @property
    def tokens(self) -> list[str]:
        """Marker codes (unwrapped) in stable order for per-word decoration."""
        codes: list[str] = sorted(self._type_codes)
        eid = self.entity_id
        if eid:
            codes.append(eid)
        codes.extend(sorted(self.symbols))
        return codes

    @property
    def suffix(self) -> str:
        codes = self.tokens
        if not codes:
            return ""
        return ZWJ + ZWJ.join(f"__{c}__" for c in codes)

    def annotate(self, text: str) -> str:
        suffix = self.suffix
        if not suffix or not self.value.strip():
            return text
        surface_words = self.value.split()
        replacement = " ".join(w + suffix for w in surface_words)
        # Skip surface words that are already followed by a ZWJ marker so
        # overlapping annotations (e.g. "Jane" and "Jane Doe") and repeated
        # passes stay idempotent.
        pattern = rf"(?<!{ZWJ}){re.escape(self.value)}(?!{ZWJ})"
        try:
            return re.sub(pattern, replacement, text)
        except Exception:
            return text

    def update(self, a: Self) -> None:
        if self.value != a.value:
            raise ValueError(f"Invalid value from update annotation: `{a.value}`")
        self.names.update(a.names)
        self.props.update(a.props)
        if self.canonical is None and a.canonical is not None:
            self.canonical = a.canonical

    @classmethod
    def from_entity(cls, value: str, e: EntityProxy) -> Self:
        if not e.schema.is_a("LegalEntity"):
            raise ValueError(f"Invalid schema: `{e.schema}` (not a LegalEntity)")
        props = {TAG_NAME.name}
        if e.schema.is_a(ORG):
            props.add(TAG_COMPANY.name)
        if e.schema.is_a(PER):
            props.add(TAG_PERSON.name)
        names = set(e.get_type_values(registry.name, matchable=True))
        canonical = e.caption or pick_name(list(names)) or value
        return cls(
            value=value,
            canonical=canonical,
            names=names,
            props=props,
        )


class Annotator:
    def __init__(self, entity: EntityProxy) -> None:
        self.entity = entity
        self.annotations: dict[str, Annotation] = {}

    def add(self, a: Annotation) -> None:
        if not a.props & set(MENTION_TYPES):
            # skip non mentions
            return
        if a.value in self.annotations:
            self.annotations[a.value].update(a)
        else:
            self.annotations[a.value] = a

    def add_tag(self, prop: Property | str, value: str) -> None:
        if isinstance(prop, Property):
            prop = prop.name
        a = Annotation(props={prop}, value=value)
        self.add(a)

    def add_mention(self, value: str, e: EntityProxy) -> None:
        a = Annotation.from_entity(value, e)
        self.add(a)

    def annotate_text(self, text: str) -> str:
        # Decorate longer surface forms first so "Jane Doe" is matched before
        # "Jane" alone; the lookaround in Annotation.annotate then leaves the
        # already-tagged words untouched on subsequent passes.
        for a in sorted(
            self.annotations.values(), key=lambda a: len(a.value), reverse=True
        ):
            text = a.annotate(text)
        return text

    def patch_entity(self, target: EntityProxy) -> None:
        """Replace each text-typed property on ``target`` with the annotated
        version of its values read from ``self.entity``. Writes per-property
        so bodyText stays bodyText, summary stays summary, etc."""
        for prop in self.entity.iterprops():
            if prop.type != registry.text:
                continue
            annotated: list[str] = []
            for value in self.entity.get(prop):
                cleaned = clean_text(value)
                patched = self.annotate_text(cleaned)
                if patched:
                    annotated.append(patched)
            if annotated:
                target.set(prop, annotated, cleaned=True, quiet=True)


def annotate_entity(e: E) -> E:
    if not e.schema.is_a("Analyzable"):
        return e
    annotator = Annotator(e)
    schema = model["Analyzable"]
    for prop in schema.properties:
        for value in e.get(prop):
            annotator.add_tag(prop, value)
    annotator.patch_entity(e)
    return e
