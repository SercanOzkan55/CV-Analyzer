"""Server-side moderation for community blog posts and comments."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

from loguru import logger


@dataclass(frozen=True)
class ModerationDecision:
    allowed: bool
    reason: str = ""


_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_HTML_RE = re.compile(r"<\s*(script|iframe|object|embed|style)\b", re.IGNORECASE)
_REPEATED_RE = re.compile(r"(.)\1{11,}", re.IGNORECASE)
_SPAM_PHRASES = (
    "guaranteed income",
    "guaranteed profit",
    "buy followers",
    "free followers",
    "casino bonus",
    "crypto giveaway",
    "whatsapp me",
    "telegram me",
    "kesin kazanç",
    "garantili kazanç",
    "takipçi satın al",
    "ücretsiz takipçi",
    "casino bonus",
)


def _local_moderation(text: str) -> ModerationDecision:
    normalized = unicodedata.normalize("NFKC", text or "").strip()
    lowered = normalized.casefold()
    if not normalized:
        return ModerationDecision(False, "empty")
    if _HTML_RE.search(normalized):
        return ModerationDecision(False, "unsafe_markup")
    if len(_URL_RE.findall(normalized)) > 2:
        return ModerationDecision(False, "link_spam")
    if _REPEATED_RE.search(normalized):
        return ModerationDecision(False, "repeated_content")
    if any(phrase in lowered for phrase in _SPAM_PHRASES):
        return ModerationDecision(False, "spam")

    words = re.findall(r"\w+", lowered, flags=re.UNICODE)
    if len(words) >= 12:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.22:
            return ModerationDecision(False, "repeated_content")
    return ModerationDecision(True)


def moderate_text(text: str) -> ModerationDecision:
    """Apply deterministic checks, then OpenAI Moderation when configured.

    Local checks are always active. Setting BLOG_REQUIRE_AI_MODERATION=true
    makes a moderation-provider outage fail closed instead of publishing.
    """

    local = _local_moderation(text)
    if not local.allowed:
        return local

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        if os.getenv("BLOG_REQUIRE_AI_MODERATION", "").lower() in ("1", "true", "yes"):
            return ModerationDecision(False, "moderation_unavailable")
        return local

    try:
        from openai import OpenAI

        response = OpenAI(api_key=api_key).moderations.create(
            model="omni-moderation-latest",
            input=text,
        )
        if response.results and response.results[0].flagged:
            return ModerationDecision(False, "unsafe_content")
    except Exception as exc:
        logger.warning("blog moderation provider failed: {}", type(exc).__name__)
        if os.getenv("BLOG_REQUIRE_AI_MODERATION", "").lower() in ("1", "true", "yes"):
            return ModerationDecision(False, "moderation_unavailable")
    return local
