"""Core analysis engine that uses Claude to identify cultural signals and score them."""

from __future__ import annotations

import datetime as dt
import json

import anthropic
import structlog

from culturalintel.config import settings
from culturalintel.monitors.base import RawPost
from culturalintel.models import Signal, Prediction, get_session

logger = structlog.get_logger()

SIGNAL_EXTRACTION_PROMPT = """\
You are a cultural intelligence analyst. Analyse the following batch of social media posts \
from the "{vertical}" vertical and identify emerging cultural signals.

A "signal" is a topic, trend, phrase, behaviour, or sentiment shift that is gaining momentum \
and may become culturally significant before it hits the mainstream.

For each signal you identify, provide:
1. **topic**: A concise name for the signal (max 10 words)
2. **description**: What it is and why it matters (2-3 sentences)
3. **growth_score**: Predicted growth trajectory (0-100, where 100 = certain to go mainstream)
4. **commercial_score**: Commercial relevance for brands/businesses (0-100)
5. **sentiment**: Overall sentiment (-1.0 = very negative, 0 = neutral, 1.0 = very positive)
6. **evidence**: Key quotes or data points from the posts supporting this signal
7. **audience_size**: Estimated current audience (small/medium/large/massive)

Posts data:
{posts_data}

Respond ONLY with a JSON array of signal objects. If no meaningful signals are found, return [].
"""

BATCH_SIZE = 50  # posts per Claude API call


class AnalysisEngine:
    """Analyse collected posts using Claude to extract and score cultural signals."""

    def __init__(self, vertical: str) -> None:
        self.vertical = vertical
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def analyse_posts(self, posts: list[RawPost]) -> list[Signal]:
        """Analyse a batch of posts and return scored signals."""
        if not posts:
            return []

        all_signals: list[Signal] = []

        # Process in batches to stay within context limits
        for i in range(0, len(posts), BATCH_SIZE):
            batch = posts[i : i + BATCH_SIZE]
            try:
                signals = self._extract_signals(batch)
                all_signals.extend(signals)
            except Exception as e:
                logger.error("analysis.batch_error", batch_index=i, error=str(e))

        # Deduplicate signals by topic similarity
        deduped = self._deduplicate_signals(all_signals)

        # Persist signals and create predictions
        self._persist(deduped)

        logger.info(
            "analysis.complete",
            vertical=self.vertical,
            posts_analysed=len(posts),
            signals_found=len(deduped),
        )
        return deduped

    def _extract_signals(self, posts: list[RawPost]) -> list[Signal]:
        """Call Claude to extract signals from a batch of posts."""
        posts_data = self._format_posts(posts)

        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": SIGNAL_EXTRACTION_PROMPT.format(
                        vertical=self.vertical,
                        posts_data=posts_data,
                    ),
                }
            ],
        )

        response_text = message.content[0].text
        return self._parse_signals(response_text, posts)

    def _format_posts(self, posts: list[RawPost]) -> str:
        """Format posts into a structured text block for Claude."""
        lines = []
        for i, post in enumerate(posts, 1):
            engagement_str = ", ".join(f"{k}: {v}" for k, v in post.engagement.items())
            lines.append(
                f"[Post {i}] Source: {post.source} | Author: {post.author} | "
                f"Engagement: {engagement_str}\n{post.content[:500]}\n"
            )
        return "\n---\n".join(lines)

    def _parse_signals(self, response_text: str, source_posts: list[RawPost]) -> list[Signal]:
        """Parse Claude's JSON response into Signal objects."""
        # Extract JSON from response (handle markdown code blocks)
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.error("analysis.parse_error", response=response_text[:200])
            return []

        signals = []
        for item in data:
            signal = Signal(
                vertical=self.vertical,
                source=self._dominant_source(source_posts),
                topic=item.get("topic", "Unknown Signal"),
                description=item.get("description", ""),
                post_count=len(source_posts),
                engagement_score=self._compute_engagement(source_posts),
                sentiment_score=float(item.get("sentiment", 0)),
                growth_score=float(item.get("growth_score", 0)),
                commercial_score=float(item.get("commercial_score", 0)),
                raw_data=json.dumps(item.get("evidence", [])),
            )
            signals.append(signal)

        return signals

    def _deduplicate_signals(self, signals: list[Signal]) -> list[Signal]:
        """Simple deduplication by topic similarity."""
        seen_topics: dict[str, Signal] = {}
        for signal in signals:
            key = signal.topic.lower().strip()
            if key in seen_topics:
                existing = seen_topics[key]
                existing.post_count += signal.post_count
                existing.engagement_score = max(existing.engagement_score, signal.engagement_score)
                existing.growth_score = max(existing.growth_score, signal.growth_score)
            else:
                seen_topics[key] = signal
        return list(seen_topics.values())

    def _persist(self, signals: list[Signal]) -> None:
        """Save signals and create predictions for tracking."""
        session = get_session()
        try:
            for signal in signals:
                session.add(signal)
                session.flush()

                # Create predictions for the learning loop
                for pred_type in ("growth", "commercial"):
                    predicted_value = (
                        signal.growth_score if pred_type == "growth" else signal.commercial_score
                    )
                    prediction = Prediction(
                        signal_id=signal.id,
                        vertical=self.vertical,
                        prediction_type=pred_type,
                        predicted_value=predicted_value,
                    )
                    session.add(prediction)

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("analysis.persist_error", error=str(e))
        finally:
            session.close()

    @staticmethod
    def _dominant_source(posts: list[RawPost]) -> str:
        """Return the most common source in the batch."""
        from collections import Counter

        sources = Counter(p.source for p in posts)
        return sources.most_common(1)[0][0] if sources else "unknown"

    @staticmethod
    def _compute_engagement(posts: list[RawPost]) -> float:
        """Compute a normalized engagement score for the batch."""
        total = 0
        for post in posts:
            total += sum(v for v in post.engagement.values() if isinstance(v, (int, float)))
        return total / max(len(posts), 1)
