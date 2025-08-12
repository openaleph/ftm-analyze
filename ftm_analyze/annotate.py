"""
Annotate entities for use with
https://www.elastic.co/docs/reference/elasticsearch/plugins/mapper-annotated-text-usage
"""

import re
from functools import cache
from typing import Literal, Self
from urllib.parse import quote_plus as qs

from anystore.types import StrGenerator
from followthemoney import E, EntityProxy, Property, Schema, model, registry
from ftmq.util import make_fingerprints
from normality import collapse_spaces
from pydantic import BaseModel
from rigour.names import Name, normalize_name, tag_org_name, tag_person_name

from ftm_analyze.analysis.util import (
    TAG_COMPANY,
    TAG_EMAIL,
    TAG_IBAN,
    TAG_LOCATION,
    TAG_NAME,
    TAG_PERSON,
    TAG_PHONE,
)

ANNOTATED = "__annotated__"
MENTION_PROPS = {
    TAG_NAME.name,
    TAG_PERSON.name,
    TAG_COMPANY.name,
    TAG_EMAIL.name,
    TAG_PHONE.name,
    TAG_IBAN.name,
    TAG_LOCATION.name,
}
PER = "Person"
ORG = "Organization"
LEG = "LegalEntity"
NAMED = {TAG_COMPANY.name, TAG_PERSON.name, TAG_NAME.name}
SKIP_CHARS = "()[]"
PATTERN_RE = r"(?<!\[)\b{value}\b(?![^\[\]]*\])"


def clean_text(text: str) -> str:
    """Clean the text before annotation: Remove [...](...) patterns"""
    for c in SKIP_CHARS:
        text = text.replace(c, " ")
    return collapse_spaces(text) or ""


def get_symbols(*names: str, schema: Literal["PER", "ORG", None]) -> set[str]:
    symbols: set[str] = set()
    if schema == "PER":
        taggers = [tag_person_name]
    elif schema == "ORG":
        taggers = [tag_org_name]
    else:
        taggers = [tag_person_name, tag_org_name]
    for name in names:
        n = Name(name)
        for tagger in taggers:
            for symbol in tagger(n, normalize_name).symbols:
                symbols.add(str(symbol.id))
    return symbols


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
        if not self.is_name:
            return set()
        schemata = self._schemata or {model[LEG]}
        return make_fingerprints(*self._names, schemata=schemata)

    @property
    def symbols(self) -> set[str]:
        return get_symbols(*self._names, schema=self._schema)

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
    def _schema(self) -> Literal["ORG", "PER", None]:
        if TAG_PERSON.name in self._props:
            return "PER"
        if TAG_COMPANY.name in self._props:
            return "ORG"

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
        for symbol in self.symbols:
            parts.add(f"q_{symbol}")
        return "&".join(sorted(parts))

    @property
    def repl(self) -> str | None:
        query = self.get_query()
        if query:
            return f"[{self.value}]({query})"

    def annotate(self, text: str) -> str:
        repl = self.repl
        if repl:
            pat = PATTERN_RE.format(value=re.escape(self.value))
            return re.sub(pat, repl, text)
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
        if not a.props & MENTION_PROPS:
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
