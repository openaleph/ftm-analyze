import re

import schwifty
from banal import ensure_list

from ftm_analyze.analysis.util import TAG_COUNTRY, TAG_EMAIL, TAG_IBAN, TAG_PHONE

EMAIL_REGEX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_REGEX = re.compile(r"(\+?[\d\-\(\)\/\s]{5,}\d{2})", re.IGNORECASE)
IBAN_REGEX = re.compile(
    r"\b([a-zA-Z]{2} ?[0-9]{2} ?[a-zA-Z0-9]{4} ?[0-9]{7} ?([a-zA-Z0-9]?){0,16})\b",
    re.IGNORECASE,
)

REGEX_TYPES = {
    EMAIL_REGEX: TAG_EMAIL,
    PHONE_REGEX: TAG_PHONE,
    IBAN_REGEX: TAG_IBAN,
}


def get_iban_country(value: str) -> str | None:
    try:
        iban = schwifty.IBAN(value, allow_invalid=True)
        if iban.is_valid:
            return iban.country_code
    except Exception:
        pass


def extract_patterns(entity, text):
    for pattern, prop in REGEX_TYPES.items():
        for match in pattern.finditer(text):
            match_text = match.group(0)
            value = prop.type.clean(match_text, proxy=entity)
            if value is None:
                continue
            yield (prop, value)
            for country in ensure_list(prop.type.country_hint(value)):
                yield (TAG_COUNTRY, country)
