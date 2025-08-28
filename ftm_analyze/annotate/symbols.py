from followthemoney.schema import Schema

from ftm_analyze.annotate.tagger import ORG_TAGGER, get_name_symbols

ORG_SYMBOLS = {
    # e.g. SYM_TECH, ORG_LLC
    s: f"{s.category.name[:3]}_{s.id}"
    for symbols in ORG_TAGGER._symbols
    for s in symbols
    if s.category.name in ("SYMBOL", "ORG_CLASS")
}


def get_symbol_annotations(schema: Schema, *names: str) -> set[str]:
    symbols: set[str] = set()
    for symbol in get_name_symbols(schema, *names):
        if symbol in ORG_SYMBOLS:
            symbols.add(ORG_SYMBOLS[symbol])
        elif symbol.category.name == "NAME":
            symbols.add(f"Q{symbol.id}")
    return symbols
