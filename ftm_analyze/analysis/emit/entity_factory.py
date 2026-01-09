"""Entity factory for creating FTM entities from resolved mentions."""

from typing import Generator

from anystore.logging import get_logger
from followthemoney import model
from followthemoney.util import make_entity_id
from ftmq.util import EntityProxy, make_entity
from normality import slugify
from rigour.names import normalize_name

from ftm_analyze.analysis.resolve.mention import Mention

log = get_logger(__name__)

# Map NER tags to Mention detected schemas
NER_TO_SCHEMA: dict[str, str] = {
    "PER": "Person",
    "ORG": "Organization",
}

# Map NER tags to FTM property names (for ID generation compatibility)
NER_TO_PROP_NAME: dict[str, str] = {
    "PER": "peopleMentioned",
    "ORG": "companiesMentioned",
    "LOC": "locationMentioned",
}


def clean_name_for_tag(name: str, tag: str) -> str | None:
    """Clean a name based on its NER tag."""
    from rigour.names import (
        remove_obj_prefixes,
        remove_org_prefixes,
        remove_person_prefixes,
    )

    cleaned = normalize_name(name)
    if not cleaned:
        return None

    if tag == "PER":
        return remove_person_prefixes(cleaned)
    if tag == "ORG":
        return remove_org_prefixes(cleaned)
    return remove_obj_prefixes(cleaned)


class EntityFactory:
    """Factory for creating FTM entities from resolved mentions.

    Handles the conversion of Mention objects into appropriate FTM entities:
    - Resolved entities (Person, Organization, etc.) when schema is known
    - Mention entities for unresolved but valid mentions
    - BankAccount entities for IBANs
    """

    def create_from_mention(
        self,
        mention: Mention,
        countries: set[str] | None = None,
    ) -> Generator[EntityProxy, None, None]:
        """Create FTM entity(ies) from a resolved mention.

        Args:
            mention: The resolved mention
            countries: Context countries to add to entities

        Yields:
            FTM EntityProxy objects
        """
        countries = countries or set()

        # Skip rejected mentions
        if mention.is_rejected:
            log.debug("Skipping rejected mention", key=mention.key)
            return

        # If we have a resolved schema, create a real entity
        if mention.resolved_schema:
            entity = self._create_resolved_entity(mention, countries)
            if entity:
                yield entity
            return

        # Otherwise create a Mention entity
        entity = self._create_mention_entity(mention, countries)
        if entity:
            yield entity

    def _create_resolved_entity(
        self,
        mention: Mention,
        countries: set[str],
    ) -> EntityProxy | None:
        """Create a resolved entity (Person, Organization, etc.)."""
        if not mention.resolved_schema:
            return None

        # Get all names, cleaned for the tag
        names = self._get_cleaned_names(mention)
        if not names:
            return None

        entity_id = mention.resolved_entity_id or make_entity_id(mention.key)

        entity = make_entity(
            {
                "id": entity_id,
                "schema": mention.resolved_schema,
                "properties": {
                    "name": list(names),
                    "proof": [mention.entity_id],
                },
            }
        )

        # Add countries (except for Address entities)
        if not entity.schema.is_a("Address") and countries:
            entity.add("country", countries)

        log.debug(
            "Created resolved entity",
            schema=mention.resolved_schema,
            caption=mention.caption,
        )
        return entity

    def _create_mention_entity(
        self,
        mention: Mention,
        countries: set[str],
    ) -> EntityProxy | None:
        """Create a Mention entity for unresolved mentions."""
        # Only create mentions for PER and ORG
        detected_schema = NER_TO_SCHEMA.get(mention.ner_tag)
        if not detected_schema:
            return None

        # Get all names, cleaned for the tag
        names = self._get_cleaned_names(mention)
        if not names:
            return None

        entity = model.make_entity("Mention")
        # Use prop name for ID generation (for backward compatibility)
        prop_name = NER_TO_PROP_NAME.get(mention.ner_tag, mention.tag)
        entity.make_id("mention", mention.entity_id, prop_name, mention.key)
        entity.add("resolved", make_entity_id(mention.key))
        entity.add("document", mention.entity_id)
        entity.add("name", list(names))
        entity.add("detectedSchema", detected_schema)
        entity.add("contextCountry", countries)

        log.debug(
            "Created mention entity", schema=detected_schema, caption=mention.caption
        )
        return entity

    def _get_cleaned_names(self, mention: Mention) -> set[str]:
        """Get all names from a mention, cleaned and deduplicated."""
        names: set[str] = set()

        # Add caption
        if mention.canonical_value:
            names.add(mention.canonical_value)
        else:
            names.add(mention.caption)

        # Add original and resolved values
        for value in mention.values:
            cleaned = clean_name_for_tag(value, mention.ner_tag)
            if cleaned:
                names.add(cleaned)

        if mention.resolved_values:
            for value in mention.resolved_values:
                cleaned = clean_name_for_tag(value, mention.ner_tag)
                if cleaned:
                    names.add(cleaned)

        return names

    def create_bank_account(
        self,
        iban: str,
        country: str,
        proof_entity_id: str,
    ) -> EntityProxy:
        """Create a BankAccount entity from an IBAN.

        Args:
            iban: The IBAN value
            country: Country code from the IBAN
            proof_entity_id: ID of the source entity

        Returns:
            BankAccount entity
        """
        bank_account = model.make_entity("BankAccount")
        bank_account.id = slugify(f"iban {iban}")
        bank_account.add("proof", proof_entity_id)
        bank_account.add("accountNumber", iban)
        bank_account.add("iban", iban)
        bank_account.add("country", country)

        log.debug("Created bank account", iban=iban)
        return bank_account
