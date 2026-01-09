"""Resolution stages for the pipeline."""

from ftm_analyze.analysis.resolve.stages.geonames import GeonamesStage
from ftm_analyze.analysis.resolve.stages.juditha import (
    JudithaClassifierStage,
    JudithaLookupStage,
    JudithaValidatorStage,
)
from ftm_analyze.analysis.resolve.stages.rigour import RigourStage

__all__ = [
    "RigourStage",
    "JudithaClassifierStage",
    "JudithaValidatorStage",
    "JudithaLookupStage",
    "GeonamesStage",
]
