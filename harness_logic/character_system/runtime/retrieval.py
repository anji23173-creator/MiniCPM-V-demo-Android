from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RetrievedEvent:
    event: dict[str, Any]
    score: float
    matched_terms: tuple[str, ...]


class StoryRetriever(Protocol):
    def retrieve(
        self, query: str, events: list[dict[str, Any]], limit: int = 12
    ) -> list[RetrievedEvent]:
        ...


SEARCH_STOP_TERMS = {
    "你是",
    "我是",
    "有何",
    "有关",
    "关于",
}

QUERY_FILLERS = (
    "究竟",
    "到底",
    "请问",
    "真的",
    "为什么",
    "是什么",
    "怎么样",
    "是不是",
    "会不会",
    "是谁",
    "什么",
    "怎么",
    "为何",
    "如何",
    "吗",
    "呢",
)


def _normalize(text: str) -> str:
    normalized = re.sub(r"\s+", "", text.lower())
    normalized = re.sub(r"[，。！？、：；“”‘’（）《》【】,.!?;:'\"()\[\]]", "", normalized)
    for filler in QUERY_FILLERS:
        normalized = normalized.replace(filler, "")
    return normalized


def _terms(text: str) -> set[str]:
    normalized = _normalize(text)
    terms = set(re.findall(r"[a-z0-9_]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u3400-\u9fff]", normalized))
    terms.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    terms.update(chinese[index : index + 3] for index in range(max(0, len(chinese) - 2)))
    return {term for term in terms if term and term not in SEARCH_STOP_TERMS}


class KeywordRetriever:
    """Low-dependency retriever replaceable by BM25 or an embedding backend."""

    def retrieve(
        self, query: str, events: list[dict[str, Any]], limit: int = 12
    ) -> list[RetrievedEvent]:
        query_terms = _terms(query)
        normalized_query = _normalize(query)
        results: list[RetrievedEvent] = []
        for event in events:
            matched_keywords = [
                keyword
                for keyword in event.get("keywords", [])
                if _normalize(keyword) in normalized_query
                or normalized_query in _normalize(keyword)
            ]
            event_terms = _terms(event["fact"] + "".join(event.get("keywords", [])))
            overlap = query_terms & event_terms
            if not matched_keywords and not overlap:
                continue
            lexical = len(overlap) / max(1, len(query_terms))
            keyword_score = min(
                1.25,
                sum(
                    min(
                        0.78,
                        0.30
                        + len(
                            _normalize(keyword)
                            if _normalize(keyword) in normalized_query
                            else normalized_query
                        )
                        * 0.08,
                    )
                    for keyword in matched_keywords
                ),
            )
            score = (
                lexical * 0.55
                + keyword_score
                + float(event["importance"]) * 0.08
            )
            if score < 0.2:
                continue
            matched = tuple(dict.fromkeys([*matched_keywords, *sorted(overlap)]))
            results.append(RetrievedEvent(event, round(score, 5), matched))
        return sorted(
            results,
            key=lambda item: (
                item.score,
                item.event["importance"],
                -item.event["time_index"],
            ),
            reverse=True,
        )[:limit]
