from followthemoney.schema import Schema
from ftmq.util import get_name_symbols
from rigour.names import SymbolCategory


def get_symbol_annotations(schema: Schema, *names: str) -> set[str]:
    """Map rigour name-symbols to the short codes carried by the per-word
    ZWJ annotations (see ``annotations.md``).

    ORG_CLASS symbols are emitted as bare ids (e.g. ``LLC``, ``CORP``);
    SYMBOL-category symbols carry the ``SYM_`` prefix (e.g. ``SYM_EXPORT``).
    rigour 2 dropped the per-tagger ``_symbols`` enumeration that previously
    let us prebuild the lookup table, so we filter at call time.
    """
    annotations: set[str] = set()
    for symbol in get_name_symbols(schema, *names):
        if symbol.category == SymbolCategory.ORG_CLASS:
            annotations.add(str(symbol.id))
        elif symbol.category == SymbolCategory.SYMBOL:
            annotations.add(f"SYM_{symbol.id}")
    return annotations
