"""Pattern-based extraction for emails, phones, and IBANs."""

import re

import schwifty
from banal import ensure_list

from ftm_analyze.analysis.extract.base import (
    TAG_EMAIL,
    TAG_IBAN,
    TAG_PHONE,
    ExtractionContext,
    ExtractionResult,
    ExtractionResults,
)
from ftm_analyze.analysis.util import TAG_EMAIL as PROP_EMAIL
from ftm_analyze.analysis.util import TAG_IBAN as PROP_IBAN
from ftm_analyze.analysis.util import TAG_PHONE as PROP_PHONE

EMAIL_REGEX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_REGEX = re.compile(r"(\+?[\d\-\(\)\/\s]{5,}\d{2})", re.IGNORECASE)
IBAN_REGEX = re.compile(
    r"\b([a-zA-Z]{2} ?[0-9]{2} ?[a-zA-Z0-9]{4} ?[0-9]{7} ?([a-zA-Z0-9]?){0,16})\b",
    re.IGNORECASE,
)

# Map regex to (tag, ftm_property)
PATTERN_MAP = [
    (EMAIL_REGEX, TAG_EMAIL, PROP_EMAIL),
    (PHONE_REGEX, TAG_PHONE, PROP_PHONE),
    (IBAN_REGEX, TAG_IBAN, PROP_IBAN),
]


def get_iban_country(value: str) -> str | None:
    """Extract country code from IBAN."""
    try:
        iban = schwifty.IBAN(value, allow_invalid=True)
        if iban.is_valid:
            return iban.country_code
    except Exception:
        pass
    return None


class PatternExtractor:
    """Extract emails, phone numbers, and IBANs from text."""

    name = "pattern"

    def extract(self, context: ExtractionContext) -> ExtractionResults:
        """Extract pattern-based entities from text."""
        for pattern, tag, prop in PATTERN_MAP:
            for match in pattern.finditer(context.text):
                match_text = match.group(0)
                value = prop.type.clean(match_text, proxy=context.entity)
                if value is None:
                    continue

                yield ExtractionResult(
                    value=value,
                    tag=tag,
                    source=self.name,
                )

                # Extract countries from patterns (e.g., IBAN country)
                for country in ensure_list(prop.type.country_hint(value)):
                    if country:
                        yield ExtractionResult(
                            value=country,
                            tag="COUNTRY",
                            source=self.name,
                            metadata={"from_pattern": tag, "original_value": value},
                        )
