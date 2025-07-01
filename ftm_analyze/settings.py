from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class NerModels(BaseSettings):
    """
    Easily overwrite specific language model for specific languages via:

    `FTM_ANALYZE_NER_MODELS_DEU=de_core_news_lg`
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

    lid_model_path: Path = Path("./models/lid.176.ftz")
    """Local path to lid model"""

    ner_models: NerModels = NerModels()
    """Spacy models"""

    resolve_mentions: bool = True
    """Resolve known mentions via `juditha`"""
