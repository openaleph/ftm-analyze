"""
Annotate names for use with
https://www.elastic.co/docs/reference/elasticsearch/plugins/mapper-annotated-text-usage
"""

import re
from typing import Self

from anystore.types import StrGenerator
from followthemoney import E, EntityProxy, Property, Schema, model, registry
from normality import collapse_spaces
from pydantic import BaseModel

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

ANNOTATED = "__annotated__"
MENTION_PROPS = {
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
SKIP_CHARS = "()[]"
PATTERN_RE = r"(?<!\[)(?:\b|:|\+){value}\b(?![^\[\]]*\])"
HTML_TAG_RE = r"<[^>]*>"


def clean_text(text: str) -> str:
    """Clean the text before annotation: Remove [...](...) patterns and strip html tags"""
    for c in SKIP_CHARS:
        text = text.replace(c, " ")
    text = re.sub(HTML_TAG_RE, " ", text)
    return collapse_spaces(text) or ""


class Annotation(BaseModel):
    """lorem ipsum [Mrs. Jane Doe](LEG&PER&Q1682564) dolor sit"""

    value: str
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
    def _props(self) -> set[str]:
        props = {MENTION_PROPS[p] for p in self.props if p in MENTION_PROPS}
        if self.is_name:
            props.add(MENTION_PROPS[TAG_NAME.name])
        return props

    @property
    def _schema(self) -> Schema | None:
        if self.is_name:
            if TAG_PERSON.name in self.props:
                return model[PER]
            if TAG_COMPANY.name in self.props:
                return model[ORG]
            return model[LEG]

    def get_query(self) -> str:
        return "&".join(sorted(self._props | self.symbols))

    @property
    def repl(self) -> str | None:
        query = self.get_query()
        if query:
            return f"[{self.value}]({query})"

    def annotate(self, text: str) -> str:
        repl = self.repl
        if repl:
            try:
                pat = PATTERN_RE.format(value=re.escape(self.value))
                return re.sub(pat, repl, text)
            except Exception:
                pass
        return text

    def update(self, a: Self) -> None:
        if self.value != a.value:
            raise ValueError(f"Invalid value from update annotation: `{a.value}`")
        self.names.update(a.names)
        self.props.update(a.props)

    @classmethod
    def from_entity(cls, value: str, e: EntityProxy) -> Self:
        if not e.schema.is_a("LegalEntity"):
            raise ValueError(f"Invalid schema: `{e.schema}` (not a LegalEntity)")
        props = {TAG_NAME.name}
        if e.schema.is_a(ORG):
            props.add(TAG_COMPANY.name)
        if e.schema.is_a(PER):
            props.add(TAG_PERSON.name)
        return cls(
            value=value,
            names=set(e.get_type_values(registry.name, matchable=True)),
            props=props,
        )


class Annotator:
    def __init__(self, entity: EntityProxy) -> None:
        self.entity = entity
        self.annotations: dict[str, Annotation] = {}

    def add(self, a: Annotation) -> None:
        if not a.props & set(MENTION_PROPS):
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
        for a in self.annotations.values():
            text = a.annotate(text)
        return text

    def get_texts(self) -> StrGenerator:
        for text in self.entity.get_type_values(registry.text):
            text = clean_text(text)
            annotated = self.annotate_text(text)
            if annotated:
                yield annotated


def annotate_entity(e: E) -> E:
    if not e.schema.is_a("Analyzable"):
        return e
    annotator = Annotator(e)
    schema = model["Analyzable"]
    for prop in schema.properties:
        for value in e.get(prop):
            annotator.add_tag(prop, value)
    for text in annotator.get_texts():
        e.add("indexText", f"{ANNOTATED} {text}")
    return e
