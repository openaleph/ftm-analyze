import fasttext
from anystore.functools import weakref_cache as cache
from anystore.logging import get_logger

from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()

THRESHOLD = 0.6


@cache
def get_lid_model():
    return fasttext.load_model(str(settings.lid_model_path))


def detect_languages(entity, text, k=1):
    """Given a list of lines, return a list of (line, lang)"""
    if entity.has("language", quiet=True) or entity.has("detectedLanguage"):
        # Don't detect if a language is hard-coded.
        return
    entity.pop("detectedLanguage")
    langs = get_lid_model().predict(text, k=k)
    for lang, score in zip(*langs):
        if score <= THRESHOLD:
            continue
        # fasttext labels are prefixed, with '__label__' by default
        lang = lang.replace("__label__", "")
        log.debug("Detected (%s chars): %s -> %.3f", len(text), lang, score)
        entity.add("detectedLanguage", lang)
