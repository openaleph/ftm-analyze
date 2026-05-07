from followthemoney.schema import Schema

from ftm_analyze.annotate.tagger import ORG_TAGGER, get_name_symbols

ORG_SYMBOLS: dict = {}
# e.g. LLC, CORP (ORG_CLASS) and SYM_TECH, SYM_EXPORT (SYMBOL)
for _symbols in ORG_TAGGER._symbols:
    for _s in _symbols:
        if _s.category.name == "ORG_CLASS":
            ORG_SYMBOLS[_s] = str(_s.id)
        elif _s.category.name == "SYMBOL":
            ORG_SYMBOLS[_s] = f"SYM_{_s.id}"


def get_symbol_annotations(schema: Schema, *names: str) -> set[str]:
    symbols: set[str] = set()
    for symbol in get_name_symbols(schema, *names):
        if symbol in ORG_SYMBOLS:
            symbols.add(ORG_SYMBOLS[symbol])
    return symbols
