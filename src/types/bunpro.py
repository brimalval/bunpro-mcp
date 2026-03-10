"""Pydantic models describing Bunpro frontend API responses."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class BunproBaseModel(BaseModel):
    """Share configuration between Bunpro-specific models."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=False)


class BunproReviewableMetadata(BunproBaseModel):
    """Common metadata that describes a reviewable item."""

    srs_level: str | None = Field(None, description="SRS stage name or slug")
    available_at: datetime | None = Field(
        None, description="When the review becomes available"
    )
    due_at: datetime | None = Field(None, description="When the review is due")
    completed_at: datetime | None = Field(
        None, description="When the review was completed"
    )
    session_id: str | None = Field(None, description="Optional session identifier")
    stats: dict[str, object] = Field(
        default_factory=dict, description="Additional service-provided counters"
    )


class BunproReviewable(BunproBaseModel):
    """Lightweight view of a single reviewable entry."""

    id: str | int | None = Field(None, description="Opaque ID for the reviewable item")
    slug: str | None = Field(None, description="URL-friendly slug for the item")
    title: str | None = Field(None, description="Human-readable name")
    type: str | None = Field(
        None, description="Type of reviewable (e.g., vocab, grammar)"
    )
    level: str | None = Field(None, description="Level or deck identifier")
    meanings: list[str] = Field(default_factory=list, description="English glosses")
    readings: list[str] = Field(
        default_factory=list, description="Pronunciations (kana/romaji)"
    )
    metadata: dict[str, object] = Field(
        default_factory=dict, description="Catch-all for unknown nested data"
    )
    reviewable_metadata: BunproReviewableMetadata | None = Field(
        None, description="Optional SRS metadata fetched alongside the reviewable."
    )


class BunproDueItem(BunproBaseModel):
    """Minimal review item carried by /user/due and /user/queue."""

    review_id: str | None = Field(None, description="Bunpro review identifier")
    reviewable_id: str | None = Field(
        None, description="Associated reviewable identifier"
    )
    reviewable_slug: str | None = Field(None, description="Reviewable slug")
    reviewable_type: str | None = Field(None, description="Type of reviewable")
    deck_id: str | None = Field(None, description="Deck identifier, when available")
    srs_level: str | None = Field(None, description="Current SRS level label")
    available_at: datetime | None = Field(
        None, description="Time the item first became available"
    )
    due_at: datetime | None = Field(None, description="Time the item is due for review")
    reviewable: BunproReviewable | None = Field(
        None, description="Embedded reviewable metadata"
    )
    payload: dict[str, object] = Field(
        default_factory=dict, description="Any additional payload the API returns"
    )


class BunproDueResponse(BunproBaseModel):
    """Response wrapper for due items."""

    total_due: int | None = Field(None, description="Total number of due items")
    upcoming: list[BunproDueItem] = Field(
        default_factory=list, description="List of current due items"
    )
    meta: dict[str, object] = Field(
        default_factory=dict, description="Auxiliary metadata returned by the API"
    )


class BunproQueueResponse(BunproBaseModel):
    """Response wrapper for the review queue."""

    queue_length: int | None = Field(
        None, description="Total count of items in the queue"
    )
    ready: list[BunproDueItem] = Field(
        default_factory=list, description="Items ready for review"
    )
    future: list[BunproDueItem] = Field(
        default_factory=list, description="Items scheduled for later"
    )
    breakdown: dict[str, object] = Field(
        default_factory=dict, description="Additional queue breakdown data"
    )


class BunproForecastPoint(BunproBaseModel):
    """Forecast point (daily or hourly)."""

    timestamp: datetime | None = Field(
        None, description="UTC timestamp for this forecast point"
    )
    reviews: int | None = Field(None, description="Projected reviews")
    lessons: int | None = Field(None, description="Projected lessons")
    meta: dict[str, object] = Field(
        default_factory=dict, description="Extra forecast metadata"
    )


class BunproSrsLevelBucket(BunproBaseModel):
    """Overview of SRS levels."""

    level: str | None = Field(None, description="SRS level label")
    count: int | None = Field(None, description="Number of items in this level")
    percent: float | None = Field(None, description="Percent share of this bucket")
    meta: dict[str, object] = Field(default_factory=dict)


class BunproReviewActivityPoint(BunproBaseModel):
    """Individual activity point for recent reviews."""

    timestamp: datetime | None = Field(
        None, description="When the activity was recorded"
    )
    reviews: int | None = Field(None, description="Reviews completed")
    lessons: int | None = Field(None, description="Lessons completed")
    streak: int | None = Field(None, description="Streak value if provided")
    meta: dict[str, object] = Field(default_factory=dict)


class BunproUserStatsResponse(BunproBaseModel):
    """Aggregated user statistics."""

    summary: dict[str, object] = Field(
        default_factory=dict, description="Top-level counts and streaks"
    )
    forecasts: list[BunproForecastPoint] = Field(
        default_factory=list, description="Forecast data (daily/hourly)"
    )
    srs_overview: list[BunproSrsLevelBucket] = Field(
        default_factory=list, description="SRS level summary"
    )
    activity: list[BunproReviewActivityPoint] = Field(
        default_factory=list, description="Recent activity timeline"
    )
    meta: dict[str, object] = Field(default_factory=dict)


class BunproVocabDefinition(BunproBaseModel):
    """Vocabulary detail returned by /reviewables/vocab/{slug}."""

    slug: str | None = Field(None, description="Vocabulary slug")
    japanese: list[str] = Field(
        default_factory=list, description="Japanese forms (kanji/kana)"
    )
    english: list[str] = Field(default_factory=list, description="English glosses")
    readings: list[str] = Field(default_factory=list, description="Reading variants")
    level: str | None = Field(None, description="JLPT level or deck")
    audio_url: str | None = Field(None, description="Optional audio asset")
    contexts: list[dict[str, object]] = Field(
        default_factory=list, description="Context sentences"
    )
    meta: dict[str, object] = Field(default_factory=dict)


class BunproVocabResponse(BunproBaseModel):
    """Response wrapper for vocabulary detail."""

    vocab: BunproVocabDefinition | None = Field(
        None, description="Primary vocabulary definition"
    )
    examples: list[dict[str, object]] = Field(
        default_factory=list, description="Example sentences or usages"
    )
    glossary: dict[str, object] = Field(
        default_factory=dict, description="Auxiliary lookup metadata"
    )


class BunproSearchHit(BunproBaseModel):
    """Single hit from /search/v1_1."""

    id: str | int | None = Field(None, description="Match identifier")
    slug: str | None = Field(None, description="Slug of the matched item")
    type: str | None = Field(None, description="Matched reviewable type")
    title: str | None = Field(None, description="Primary display text")
    excerpt: str | None = Field(
        None, description="Short snippet illustrating the match"
    )
    score: float | None = Field(None, description="Match score provided by Bunpro")
    meta: dict[str, object] = Field(default_factory=dict)


class BunproSearchResponse(BunproBaseModel):
    """Search results container."""

    query: str | None = Field(None, description="Original search query")
    results: list[BunproSearchHit] = Field(
        default_factory=list, description="Ordered search hits"
    )
    meta: dict[str, object] = Field(default_factory=dict)


class BunproGrammarPointResponse(BunproBaseModel):
    id: str | int | None = Field(None, description="Grammar point identifier")
    slug: str | None = Field(None, description="Grammar point slug")
    title: str | None = Field(None, description="Grammar point title")
    grammar_point: dict[str, object] | None = Field(
        None, description="Primary grammar point payload"
    )
    examples: list[dict[str, object]] | None = Field(
        None, description="Example sentence payloads"
    )
    meanings: list[dict[str, object]] | None = Field(
        None, description="Meaning/nuance payloads"
    )
    meta: dict[str, object] | None = Field(
        None, description="Auxiliary metadata returned by Bunpro"
    )


class BunproReadingPassagesResponse(BunproBaseModel):
    passages: list[dict[str, object]] | None = Field(
        None, description="Reading passage collection"
    )
    results: list[dict[str, object]] | None = Field(
        None, description="Alternate collection key used by some payloads"
    )
    total: int | None = Field(None, description="Total number of passages")
    meta: dict[str, object] | None = Field(
        None, description="Auxiliary metadata returned by Bunpro"
    )
