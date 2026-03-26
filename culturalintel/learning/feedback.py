"""Feedback loop: evaluate past predictions against actual outcomes to improve accuracy."""

from __future__ import annotations

import datetime as dt
import json

import anthropic
import structlog

from culturalintel.config import settings
from culturalintel.models import Signal, Prediction, get_session

logger = structlog.get_logger()

EVALUATION_PROMPT = """\
You are evaluating the accuracy of cultural signal predictions. For each prediction below, \
assess how accurate it was based on the current state of the signal.

Score each prediction from 0.0 (completely wrong) to 1.0 (perfectly accurate).
Also provide a brief reason for the score.

Predictions to evaluate:
{predictions_data}

Current signal states:
{signals_data}

Respond with a JSON array of objects: [{{"prediction_id": int, "accuracy_score": float, \
"actual_value": float, "reason": str}}]
"""


class FeedbackLoop:
    """Evaluate past predictions and feed accuracy data back into the system."""

    def __init__(self, vertical: str) -> None:
        self.vertical = vertical
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def evaluate_predictions(self, lookback_days: int = 14) -> list[dict]:
        """Evaluate predictions made in the last N days against current signal state."""
        session = get_session()
        try:
            cutoff = dt.datetime.utcnow() - dt.timedelta(days=lookback_days)

            # Get unevaluated predictions
            predictions = (
                session.query(Prediction)
                .filter(
                    Prediction.vertical == self.vertical,
                    Prediction.predicted_at >= cutoff,
                    Prediction.evaluated_at.is_(None),
                )
                .all()
            )

            if not predictions:
                logger.info("feedback.no_predictions", vertical=self.vertical)
                return []

            # Get corresponding signals
            signal_ids = {p.signal_id for p in predictions}
            signals = session.query(Signal).filter(Signal.id.in_(signal_ids)).all()
            signal_map = {s.id: s for s in signals}

            # Ask Claude to evaluate
            results = self._evaluate_with_claude(predictions, signal_map)

            # Update predictions with results
            for result in results:
                pred_id = result.get("prediction_id")
                pred = next((p for p in predictions if p.id == pred_id), None)
                if pred:
                    pred.accuracy_score = result.get("accuracy_score", 0.0)
                    pred.actual_value = result.get("actual_value", 0.0)
                    pred.evaluated_at = dt.datetime.utcnow()

            session.commit()

            logger.info(
                "feedback.evaluated",
                vertical=self.vertical,
                predictions_evaluated=len(results),
                avg_accuracy=sum(r.get("accuracy_score", 0) for r in results) / max(len(results), 1),
            )
            return results

        except Exception as e:
            session.rollback()
            logger.error("feedback.error", error=str(e))
            return []
        finally:
            session.close()

    def get_accuracy_summary(self) -> dict:
        """Get overall accuracy statistics for this vertical."""
        session = get_session()
        try:
            evaluated = (
                session.query(Prediction)
                .filter(
                    Prediction.vertical == self.vertical,
                    Prediction.evaluated_at.isnot(None),
                )
                .all()
            )

            if not evaluated:
                return {"total": 0, "avg_accuracy": 0.0}

            scores = [p.accuracy_score for p in evaluated if p.accuracy_score is not None]
            return {
                "total": len(evaluated),
                "avg_accuracy": sum(scores) / len(scores) if scores else 0.0,
                "by_type": self._accuracy_by_type(evaluated),
            }
        finally:
            session.close()

    def _evaluate_with_claude(
        self, predictions: list[Prediction], signal_map: dict[int, Signal]
    ) -> list[dict]:
        """Use Claude to evaluate prediction accuracy."""
        predictions_data = []
        for p in predictions:
            signal = signal_map.get(p.signal_id)
            predictions_data.append(
                f"Prediction #{p.id}: Type={p.prediction_type}, "
                f"Predicted={p.predicted_value:.1f}, "
                f"Signal='{signal.topic if signal else 'unknown'}'"
            )

        signals_data = []
        for s in signal_map.values():
            signals_data.append(
                f"Signal '{s.topic}': Status={s.status}, "
                f"Engagement={s.engagement_score:.1f}, "
                f"Posts={s.post_count}, Last seen={s.last_seen}"
            )

        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=4000,
            temperature=0.2,
            messages=[
                {
                    "role": "user",
                    "content": EVALUATION_PROMPT.format(
                        predictions_data="\n".join(predictions_data),
                        signals_data="\n".join(signals_data),
                    ),
                }
            ],
        )

        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error("feedback.parse_error", response=text[:200])
            return []

    @staticmethod
    def _accuracy_by_type(predictions: list[Prediction]) -> dict[str, float]:
        """Calculate average accuracy grouped by prediction type."""
        by_type: dict[str, list[float]] = {}
        for p in predictions:
            if p.accuracy_score is not None:
                by_type.setdefault(p.prediction_type, []).append(p.accuracy_score)
        return {k: sum(v) / len(v) for k, v in by_type.items()}
