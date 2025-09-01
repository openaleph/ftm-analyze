from pathlib import Path
from typing import Literal

from anystore.settings import BaseSettings
from pydantic_settings import BaseSettings as _BaseSettings
from pydantic_settings import SettingsConfigDict


class SpacyNerModels(_BaseSettings):
    """
    Easily overwrite specific language model for specific languages via:

    `FTM_ANALYZE_SPACY_MODELS_DEU=de_core_news_lg`
    """

    eng: str = "en_core_web_sm"
    deu: str = "de_core_news_sm"
    fra: str = "fr_core_news_sm"
    spa: str = "es_core_news_sm"
    rus: str = "ru_core_news_sm"
    por: str = "pt_core_news_sm"
    ron: str = "ro_core_news_sm"
    mkd: str = "mk_core_news_sm"
    ell: str = "el_core_news_sm"
    pol: str = "pl_core_news_sm"
    ita: str = "it_core_news_sm"
    lit: str = "lt_core_news_sm"
    nld: str = "nl_core_news_sm"
    nob: str = "nb_core_news_sm"
    nor: str = "nb_core_news_sm"
    dan: str = "da_core_news_sm"


class FlairNerModels(_BaseSettings):
    """
    Easily overwrite specific language model for specific languages via:

    `FTM_ANALYZE_FLAIR_MODELS_DEU=de_core_news_lg`
    """

    eng: str = "ner"
    deu: str = "de-ner"
    fra: str = "fr-ner"
    spa: str = "es-ner-large"  # FIXME
    # rus: str = "ru_core_news_md"
    # por: str = "pt_core_news_sm"
    # ron: str = "ro_core_news_sm"
    # mkd: str = "mk_core_news_sm"
    # ell: str = "el_core_news_sm"
    # pol: str = "pl_core_news_sm"
    # ita: str = "it_core_news_sm"
    # lit: str = "lt_core_news_sm"
    nld: str = "nl-ner"
    # nob: str = "nb_core_news_sm"
    # nor: str = "nb_core_news_sm"
    # dan: str = "da_core_news_sm"


class Settings(BaseSettings):
    """
    `ftm-analyze` settings management using
    [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

    Note:
        All settings can be set via environment variables or `.env` file,
        prepending `FTM_ANALYZE_` (except for those with another alias)
    """

    model_config = SettingsConfigDict(
        env_prefix="ftm_analyze_",
        env_nested_delimiter="_",
        env_file=".env",
        extra="ignore",
    )

    ner_type_model_path: Path = Path("./models/model_type_prediction.ftz")
    """Local path to ftm type predict model"""

    ner_type_model_confidence: float = 0.85
    """Minimum confidence for ftm type predict model"""

    ner_engine: Literal["spacy", "flair", "bert"] = "spacy"
    """NER engine to use (may need install extra dependencies)"""

    lid_model_path: Path = Path("./models/lid.176.ftz")
    """Local path to lid model"""

    spacy_models: SpacyNerModels = SpacyNerModels()
    """Spacy models"""

    flair_models: FlairNerModels = FlairNerModels()
    """Flair models"""

    bert_model: str = "dslim/bert-base-NER"
    """Model when using BERT transformers"""

    ner_default_lang: str = "eng"
    """Default ner language, 3-letter code"""

    resolve_mentions: bool = False
    """Resolve known mentions via `juditha`"""

    refine_mentions: bool = False
    """Refine schema classification for mentions via `juditha` fasttext model"""

    annotate: bool = False
    """Insert annotations into `indexText` for resolved mentions"""

    validate_names: bool = False
    """Validate NER results against known name tokens via `juditha`"""
