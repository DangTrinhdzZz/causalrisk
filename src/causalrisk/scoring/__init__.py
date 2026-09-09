"""Gold-aware scoring namespace; inference code must never import this package."""

from causalrisk.scoring.core import ScoreSummary, score_frozen_run

__all__ = ["ScoreSummary", "score_frozen_run"]
