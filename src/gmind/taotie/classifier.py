"""LLM-based file privacy and knowledge classification."""

from __future__ import annotations

import json
from pathlib import Path

from gmind import config
from gmind.llm import engine as llm_engine
from gmind.taotie.scanner import FileInfo

CLASSIFY_PROMPT = """你是 GMind 的「知识雷达」分类器。
请判断以下文件是否值得自动知识化后存入个人知识库。

GMind 存的不是“所有文件”，而是对未来思考、检索、写作、决策、复盘有复用价值的个人记忆和知识材料。

文件路径：{filepath}
内容预览：
{preview}

必须入库的典型内容：
- 笔记、读书摘录、研究材料、项目方案、会议纪要、复盘、TODO 背后的思考
- AI/Agent 会话中包含的需求、决策、设计讨论、实现线索
- 用户自己写的文章、长文草稿、知识整理、学习记录
- 可被摘要、打标签、抽实体关系，并且未来可能被问答检索复用的内容

不要入库的典型内容：
- 安装包说明、系统日志、构建输出、报错堆栈、缓存、纯配置、临时文件
- 发票、账单、报销、银行流水、快递、身份证扫描件、合同扫描件等事务/凭证类文件
- 无上下文的表格、数据导出、名单、通讯录、下载说明、软件 license、README 模板
- 图片 OCR 后的证件/票据/截图内容，除非它明显是用户整理的知识笔记
- 内容过短、重复、无明确主题、无法形成个人知识卡片的文件

隐私规则：
- 只要包含密码、密钥、Token、API Key、cookie、私钥，
  privacy_level 必须是 "private"，should_ingest 必须 false
- 包含身份证号、手机号、银行卡号、客户名单、公司机密、
  个人医疗/财务/法律材料，privacy_level 用 "private" 或 "sensitive"，
  should_ingest 必须 false
- 只有 privacy_level 为 "safe" 且确实有知识复用价值时，should_ingest 才能 true

判断标准：
- 如果不确定，宁可 should_ingest=false
- 不要因为文件扩展名是 md/pdf/docx/txt 就入库
- 不要因为内容“可读”就入库；必须是“值得未来检索的知识/记忆”

返回严格 JSON（不要 markdown 代码块）：
{{
    "should_ingest": false,
    "reason": "简短说明",
    "privacy_level": "safe",
    "contains_passwords": false,
    "contains_pii": false,
    "is_knowledge": false
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
        except Exception as exc:
            raise RuntimeError(f"LLM config is required for Knowledge Radar: {exc}") from exc
        if not llm_cfg or not llm_cfg.get("provider"):
            raise RuntimeError("LLM not configured. Knowledge Radar requires a reasoning model.")
        engine = llm_engine.load_llm_engine(llm_cfg)

    if engine is None or not engine.is_available():
        raise RuntimeError("LLM provider not available. Knowledge Radar cannot run without AI.")

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
            if file_info.privacy_level != "safe" or not file_info.is_knowledge:
                file_info.should_ingest = False
        else:
            raise RuntimeError("LLM classification returned invalid JSON")
    except Exception as exc:
        raise RuntimeError(f"LLM classification failed for {file_info.path}: {exc}") from exc

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
    """Strict non-AI prefilter for tests and explicit offline tools only."""
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

    non_memory_patterns = [
        "invoice", "receipt", "bill", "statement", "bank", "salary", "payroll",
        "log", "debug", "trace", "crash", "license", "readme", "changelog",
        "export", "backup", "cache", "tmp", "temp", "download", "安装", "发票",
        "账单", "流水", "工资", "身份证", "报销", "日志", "缓存", "备份",
    ]
    for pattern in non_memory_patterns:
        if pattern in path_lower:
            file_info.should_ingest = False
            file_info.privacy_level = "safe"
            file_info.is_knowledge = False
            file_info.reason = f"Heuristic skip: path contains '{pattern}'"
            return file_info

    knowledge_patterns = [
        "note", "notes", "memo", "meeting", "research", "draft", "idea",
        "project", "plan", "review", "summary", "reading", "agent", "session",
        "笔记", "会议", "纪要", "研究", "方案", "复盘", "总结", "草稿",
        "想法", "阅读", "摘录", "项目", "会话",
    ]
    if any(pattern in path_lower for pattern in knowledge_patterns):
        file_info.should_ingest = True
        file_info.privacy_level = "safe"
        file_info.is_knowledge = True
        file_info.reason = "Heuristic: path looks like reusable knowledge"
        return file_info

    file_info.should_ingest = False
    file_info.privacy_level = "safe"
    file_info.is_knowledge = False
    file_info.reason = "Heuristic skip: not clearly reusable personal knowledge"
    return file_info
