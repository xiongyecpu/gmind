"""Entity and relation extraction from page content."""

from __future__ import annotations

import json
import re

from gmind.llm.engine import LLMEngine


def extract_entities(content: str, engine: LLMEngine, max_tokens: int = 2000) -> list[dict]:
    """Extract named entities from content."""
    prompt = f"""Extract all named entities from the following text.

For each entity, provide:
- name: the entity name (in original language)
- type: one of [person, company, product, concept, place, technology, book, event, other]
- description: a one-sentence description

Return ONLY a JSON array. No markdown, no explanation.

Text:
{content[:max_tokens]}
"""
    result = engine.ask(prompt, temperature=0.1)
    return _safe_parse_json_array(result)


def extract_relations(content: str, entities: list[str], engine: LLMEngine, max_tokens: int = 2000) -> list[dict]:
    """Extract relations between entities mentioned in content."""
    entity_list = ", ".join(f'"{e}"' for e in entities[:30])
    prompt = f"""From the following text, extract relationships between these entities: {entity_list}

For each relation, provide:
- from: the source entity name
- to: the target entity name
- relation: a short relation type, e.g. "works_at", "created", "based_on", "mentions", "opposes"

Only include relations that are clearly stated or strongly implied in the text.
Return ONLY a JSON array. No markdown, no explanation.

Text:
{content[:max_tokens]}
"""
    result = engine.ask(prompt, temperature=0.1)
    return _safe_parse_json_array(result)


def auto_summarize(content: str, engine: LLMEngine, max_tokens: int = 3000) -> dict:
    """Generate summary, tags, and key points."""
    prompt = f"""Summarize the following text concisely.

Return ONLY a JSON object with these fields:
- summary: one-sentence summary (under 100 characters)
- tags: array of 3-7 tags/keywords
- key_points: array of 2-5 key takeaways (each under 80 characters)

No markdown, no explanation.

Text:
{content[:max_tokens]}
"""
    result = engine.ask(prompt, temperature=0.2)
    parsed = _safe_parse_json_object(result)
    return {
        "summary": parsed.get("summary", ""),
        "tags": parsed.get("tags", []),
        "key_points": parsed.get("key_points", []),
    }


def suggest_title(content: str, engine: LLMEngine) -> str:
    """Suggest a title for untitled content."""
    prompt = f"""Suggest a concise, descriptive title (under 30 characters) for the following text.
Return ONLY the title, no quotes, no explanation.

Text:
{content[:2000]}
"""
    return engine.ask(prompt, temperature=0.2).strip().strip('"').strip("'")


def _safe_parse_json_array(text: str) -> list[dict]:
    """Safely parse a JSON array from LLM output, handling common formatting issues."""
    text = text.strip()
    # Remove markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        return []
    except json.JSONDecodeError:
        return []


def _safe_parse_json_object(text: str) -> dict:
    """Safely parse a JSON object from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except json.JSONDecodeError:
        return {}
