from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from gmind.providers import LLMProvider


SOLO_PREVIEW_CHARS = 12000


@dataclass(frozen=True)
class SoloAddDecision:
    should_ingest: bool
    reason: str
    confidence: float


def judge_solo_add_file(
    *,
    title: str,
    file_path: Path,
    text: str,
    provider: LLMProvider,
) -> SoloAddDecision:
    if file_path is None:
        raise ValueError("--solo requires --file input")
    preview = text.strip()[:SOLO_PREVIEW_CHARS]
    if not preview:
        return SoloAddDecision(
            should_ingest=False,
            reason="文件没有可判断的文本内容。",
            confidence=1.0,
        )

    decision = provider.judge_source_for_ingest(
        title=title,
        source_path=str(file_path.expanduser().resolve()),
        text_preview=preview,
    )
    return SoloAddDecision(
        should_ingest=bool(decision["should_ingest"]),
        reason=str(decision["reason"]).strip(),
        confidence=float(decision["confidence"]),
    )


def record_solo_add_decision(
    database_url: str,
    *,
    title: str,
    file_path: Path,
    decision: SoloAddDecision,
    dry_run: bool = False,
) -> None:
    action = "solo_add_allowed" if decision.should_ingest else "solo_add_rejected"
    resolved_path = str(file_path.expanduser().resolve())
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into logs (
                    action,
                    title,
                    summary,
                    actor,
                    object_type,
                    object_id,
                    metadata_json
                )
                values (%s, %s, %s, 'gmind', 'source_candidate', null, %s)
                """,
                (
                    action,
                    f"Solo {'allowed' if decision.should_ingest else 'rejected'}: {title}",
                    decision.reason,
                    Jsonb(
                        {
                            "source_path": resolved_path,
                            "should_ingest": decision.should_ingest,
                            "reason": decision.reason,
                            "confidence": decision.confidence,
                            "dry_run": dry_run,
                        }
                    ),
                ),
            )
