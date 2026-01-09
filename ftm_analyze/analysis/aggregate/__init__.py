"""Aggregation module for extraction results."""

from ftm_analyze.analysis.aggregate.aggregator import AggregatedResult, Aggregator
from ftm_analyze.analysis.aggregate.confidence import ConfidenceScorer

__all__ = [
    "Aggregator",
    "AggregatedResult",
    "ConfidenceScorer",
]
