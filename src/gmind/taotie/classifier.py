"""LLM-based file privacy and knowledge classification."""

from __future__ import annotations

import json
from pathlib import Path

from gmind import config
from gmind.llm import engine as llm_engine
from gmind.taotie.scanner import FileInfo


CLASSIFY_PROMPT = """判断以下文件是否适合作为个人知识库存入。

文件路径：{filepath}
内容预览：
{preview}

判断规则：
1. 是否包含密码、密钥、Token、API Key？
2. 是否包含身份证号、手机号、银行卡号等个人隐私？
3. 是否包含公司内部机密或商业敏感信息？
4. 内容是否有知识价值（笔记、文档、文章、思考、会话记录）？

返回严格 JSON（不要 markdown 代码块）：
{{
    "should_ingest": true,
    "reason": "简短说明",
    "privacy_level": "safe",
    "contains_passwords": false,
    "contains_pii": false,
    "is_knowledge": true
}}
"""


def _read_preview(file_path: str, max_chars: int = 1000) -> str:
    """Read first N characters of a file for preview."""
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    text = ""
                    for page in pdf.pages[:3]:  # first 3 pages
                        text += page.extract_text() or ""
                        if len(text) >= max_chars:
                            break
                    return text[:max_chars]
            except Exception:
                return "[PDF read error]"

        elif ext == ".docx":
            try:
                from docx import Document
                doc = Document(path)
                text = "\n".join(p.text for p in doc.paragraphs[:50])
                return text[:max_chars]
            except Exception:
                return "[DOCX read error]"

        else:
            # md, txt
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]

    except Exception:
        return "[read error]"


def classify_file(
    file_info: FileInfo,
    *,
    engine: llm_engine.LLMEngine | None = None,
    use_cache: bool = True,
) -> FileInfo:
    """Classify a file using LLM. Returns updated FileInfo with classification."""
    # Try to load engine if not provided
    if engine is None:
        try:
            cfg = config.load_config()
            llm_cfg = cfg.llm
            if llm_cfg and llm_cfg.get("provider"):
                engine = llm_engine.load_llm_engine(llm_cfg)
        except Exception:
            pass

    if engine is None or not engine.is_available():
        # Fallback: simple heuristic classification
        return _heuristic_classify(file_info)

    preview = _read_preview(file_info.path, max_chars=1000)
    prompt = CLASSIFY_PROMPT.format(filepath=file_info.path, preview=preview)

    try:
        response = engine.ask(prompt, temperature=0.1, use_cache=use_cache)
        # Parse JSON
        result = _extract_json(response)
        if result:
            file_info.should_ingest = result.get("should_ingest", True)
            file_info.reason = result.get("reason", "")
            file_info.privacy_level = result.get("privacy_level", "safe")
            file_info.contains_passwords = result.get("contains_passwords", False)
            file_info.contains_pii = result.get("contains_pii", False)
            file_info.is_knowledge = result.get("is_knowledge", True)
        else:
            # fallback
            file_info = _heuristic_classify(file_info)
    except Exception:
        file_info = _heuristic_classify(file_info)

    return file_info


def _extract_json(text: str) -> dict | None:
    """Extract JSON object from LLM response text."""
    # Try to find JSON object
    text = text.strip()
    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first line (```json or ```)
        if lines:
            lines = lines[1:]
        # Remove last line (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _heuristic_classify(file_info: FileInfo) -> FileInfo:
    """Fallback heuristic classification when LLM is unavailable."""
    path_lower = file_info.path.lower()

    # Password/secret patterns
    password_patterns = [
        "password", "passwd", "secret", "token", "api_key", "apikey",
        "private_key", "ssh_key", "credentials", "密码", "密钥",
        ".env", ".ssh", ".aws", ".docker",
    ]

    for pattern in password_patterns:
        if pattern in path_lower:
            file_info.should_ingest = False
            file_info.privacy_level = "private"
            file_info.contains_passwords = True
            file_info.reason = f"Path contains '{pattern}'"
            return file_info

    # If it looks like a knowledge file
    file_info.should_ingest = True
    file_info.privacy_level = "safe"
    file_info.is_knowledge = True
    file_info.reason = "Heuristic: likely knowledge file"
    return file_info
