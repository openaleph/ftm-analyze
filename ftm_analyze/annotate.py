"""
Annotate entities for use with
https://www.elastic.co/docs/reference/elasticsearch/plugins/mapper-annotated-text-usage
"""

import re
from functools import cache
from typing import Iterable, Self
from urllib.parse import quote_plus as qs

from anystore.types import StrGenerator
from followthemoney import E, EntityProxy, Property, Schema, model, registry
from followthemoney.compare import _normalize_names
from normality import collapse_spaces
from pydantic import BaseModel

from ftm_analyze.analysis.util import TAG_COMPANY, TAG_NAME, TAG_PERSON

ANNOTATED = "__annotated__"
PER = "Person"
ORG = "Organization"
LEG = "LegalEntity"
NAMED = {TAG_COMPANY.name, TAG_PERSON.name, TAG_NAME.name}


def entity_fingerprints(entity: EntityProxy) -> set[str]:
    """Get the set of entity name fingerprints"""
    # FIXME
    return set(_normalize_names(entity.schema, entity.names))


def make_fingerprints(schemata: set[Schema], names: Iterable[str]) -> set[str]:
    """Mimic `fingerprints.generate`"""
    # FIXME
    fps: set[str] = set()
    for schema in schemata:
        fps.update(set(_normalize_names(schema, names)))
    return fps


def clean_text(text: str) -> str:
    """Clean the text before annotation: Remove [...](...) patterns"""
    return collapse_spaces(re.sub(r"\[(.*)\]\(.*\)", r"\1", text)) or ""


@cache
def get_extend(schema: Schema) -> set[str]:
    schemata: set[str] = {schema.name}
    for s in schema.extends:
        if s.name not in ("Thing", "Value"):
            schemata.update(get_extend(s))
    return schemata


class Annotation(BaseModel):
    """lorem ipsum [Mrs. Jane Doe](f_doe+jane&s_Person&s_LegalEntity&p_namesMentioned&p_peopleMentioned) dolor sit amet"""  # noqa: B950

    value: str
    names: set[str] = set()
    schemata: set[str] = set()
    props: set[str] = set()

    @property
    def is_name(self) -> bool:
        return bool(NAMED & self.props)

    @property
    def fingerprints(self) -> set[str]:
        schemata = self._schemata or {model[LEG]}
        if self.is_name:
            return make_fingerprints(schemata, self._names)
        return set()

    @property
    def _names(self) -> set[str]:
        if self.is_name:
            return set([self.value, *self.names])
        return set()

    @property
    def _props(self) -> set[str]:
        if self.is_name:
            return set([*self.props, TAG_NAME.name])
        return self.props

    @property
    def _schemata(self) -> set[Schema]:
        if self.is_name:
            schemata = {model.get(s) for s in self.schemata}
            schemata = {s for s in schemata if s}
            if not schemata:
                if TAG_PERSON.name in self.props:
                    return {model[s] for s in get_extend(model[PER])}
                if TAG_COMPANY.name in self.props:
                    return {model[s] for s in get_extend(model[ORG])}
            return schemata
        return set()

    def get_query(self) -> str:
        parts: set[str] = set()
        for fp in self.fingerprints:
            parts.add(f"f_{qs(fp)}")
        for prop in self._props:
            parts.add(f"p_{prop}")
        for schema in self._schemata:
            parts.add(f"s_{schema.name}")
        return "&".join(sorted(parts))

    @property
    def repl(self) -> str | None:
        query = self.get_query()
        if query:
            return f"[{self.value}]({query})"

    def annotate(self, text: str) -> str:
        cleaned = clean_text(text)
        if not cleaned:
            return ""
        repl = self.repl
        if repl:
            return cleaned.replace(self.value, repl)
        return text

    def update(self, a: Self) -> None:
        if self.value != a.value:
            raise ValueError(f"Invalid value from update annotation: `{a.value}`")
        self.names.update(a.names)
        self.schemata.update(a.schemata)
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
            names=set(e.names),
            schemata=get_extend(e.schema),
            props=props,
        )


class Annotator:
    def __init__(self, entity: EntityProxy) -> None:
        self.entity = entity
        self.annotations: dict[str, Annotation] = {}

    def add(self, a: Annotation) -> None:
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
