from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Optional, Sequence

from gmind import __version__
from gmind.ask import AskResult, answer_question
from gmind.config import DEFAULT_CONFIG_PATH, init_config, load_config
from gmind.db import check_database, init_database
from gmind.embed import embed_pending_chunks, embed_source_chunks
from gmind.extract import extract_llm_source, extract_stub_source
from gmind.ingest import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    ingest_text_source,
)
from gmind.knowledge import (
    get_claim,
    get_entity,
    get_task,
    list_claims,
    list_entities,
    list_events,
    list_logs,
    list_relations,
    list_tasks,
)
from gmind.providers import build_embedding_provider, build_llm_provider
from gmind.solo import judge_solo_add_file, record_solo_add_decision
from gmind.sources import get_source, list_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gmind")
    parser.add_argument("--version", action="version", version=f"gmind {__version__}")

    subcommands = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="{setup,add,ask,status,doctor,debug,init,config}",
    )

    setup_parser = subcommands.add_parser("setup", help="Create a local config file.")
    setup_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    setup_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the config file if it already exists.",
    )
    setup_parser.set_defaults(handler=handle_init)

    add_parser = subcommands.add_parser("add", help="Add material to gmind.")
    add_subcommands = add_parser.add_subparsers(dest="add_command", required=True)
    add_text_parser = add_subcommands.add_parser(
        "text", help="Add a plain text file and process it."
    )
    add_text_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    add_text_parser.add_argument(
        "--title",
        help="Source title. If omitted, gmind asks the LLM to infer one.",
    )
    add_text_input = add_text_parser.add_mutually_exclusive_group(required=True)
    add_text_input.add_argument(
        "--file",
        type=Path,
        help="Path to the text file to add.",
    )
    add_text_input.add_argument(
        "--text",
        help="Text content to add directly.",
    )
    add_text_input.add_argument(
        "--stdin",
        action="store_true",
        help="Read text content from standard input.",
    )
    add_text_parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Chunk size in characters. Defaults to {DEFAULT_CHUNK_SIZE}.",
    )
    add_text_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=f"Chunk overlap in characters. Defaults to {DEFAULT_CHUNK_OVERLAP}.",
    )
    add_text_parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Only store the source; do not generate embeddings.",
    )
    add_text_parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Only store/embed the source; do not run LLM extraction.",
    )
    add_text_parser.add_argument(
        "--solo",
        action="store_true",
        help="Ask the LLM whether this file should be added before importing.",
    )
    add_text_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only return the solo decision; do not import, embed, or extract.",
    )
    add_text_parser.add_argument("--json", action="store_true")
    add_text_parser.set_defaults(handler=handle_add_text)

    add_markdown_parser = add_subcommands.add_parser(
        "markdown", help="Add Markdown content and process it."
    )
    add_markdown_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    add_markdown_parser.add_argument(
        "--title",
        help="Source title. If omitted, gmind asks the LLM to infer one.",
    )
    add_markdown_input = add_markdown_parser.add_mutually_exclusive_group(required=True)
    add_markdown_input.add_argument(
        "--file",
        type=Path,
        help="Path to the Markdown file to add.",
    )
    add_markdown_input.add_argument(
        "--text",
        help="Markdown content to add directly.",
    )
    add_markdown_input.add_argument(
        "--stdin",
        action="store_true",
        help="Read Markdown content from standard input.",
    )
    add_markdown_parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Chunk size in characters. Defaults to {DEFAULT_CHUNK_SIZE}.",
    )
    add_markdown_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=f"Chunk overlap in characters. Defaults to {DEFAULT_CHUNK_OVERLAP}.",
    )
    add_markdown_parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Only store the source; do not generate embeddings.",
    )
    add_markdown_parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Only store/embed the source; do not run LLM extraction.",
    )
    add_markdown_parser.add_argument(
        "--solo",
        action="store_true",
        help="Ask the LLM whether this file should be added before importing.",
    )
    add_markdown_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only return the solo decision; do not import, embed, or extract.",
    )
    add_markdown_parser.add_argument("--json", action="store_true")
    add_markdown_parser.set_defaults(handler=handle_add_text)

    ask_parser = subcommands.add_parser("ask", help="Ask your knowledge base.")
    ask_parser.add_argument("question", nargs="+", help="Question to ask.")
    ask_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    ask_parser.add_argument("--json", action="store_true")
    ask_parser.set_defaults(handler=handle_ask)

    status_parser = subcommands.add_parser(
        "status", help="Show whether gmind is ready."
    )
    status_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(handler=handle_status)

    doctor_parser = subcommands.add_parser(
        "doctor", help="Diagnose local gmind setup."
    )
    doctor_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(handler=handle_doctor)

    debug_parser = subcommands.add_parser(
        "debug", help="Developer inspection and pipeline commands."
    )
    _add_debug_commands(debug_parser)

    init_parser = subcommands.add_parser("init", help="Create a gmind config file.")
    init_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    init_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the config file if it already exists.",
    )
    init_parser.set_defaults(handler=handle_init)

    config_parser = subcommands.add_parser("config", help="Inspect configuration.")
    config_subcommands = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    config_show_parser = config_subcommands.add_parser(
        "show", help="Show resolved configuration."
    )
    config_show_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    config_show_parser.set_defaults(handler=handle_config_show)

    db_parser = subcommands.add_parser("db", help=argparse.SUPPRESS)
    db_subcommands = db_parser.add_subparsers(dest="db_command", required=True)
    db_init_parser = db_subcommands.add_parser(
        "init", help="Create database tables, indexes, and views."
    )
    db_init_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    db_init_parser.set_defaults(handler=handle_db_init)

    db_check_parser = db_subcommands.add_parser(
        "check", help="Check database schema readiness."
    )
    db_check_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    db_check_parser.set_defaults(handler=handle_db_check)

    ingest_parser = subcommands.add_parser("ingest", help=argparse.SUPPRESS)
    ingest_subcommands = ingest_parser.add_subparsers(
        dest="ingest_command", required=True
    )
    ingest_text_parser = ingest_subcommands.add_parser(
        "text", help="Ingest a plain text file."
    )
    ingest_text_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    ingest_text_parser.add_argument("--title", required=True, help="Source title.")
    ingest_text_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Path to the text file to ingest.",
    )
    ingest_text_parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Chunk size in characters. Defaults to {DEFAULT_CHUNK_SIZE}.",
    )
    ingest_text_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=f"Chunk overlap in characters. Defaults to {DEFAULT_CHUNK_OVERLAP}.",
    )
    ingest_text_parser.set_defaults(handler=handle_ingest_text)

    sources_parser = subcommands.add_parser("sources", help=argparse.SUPPRESS)
    sources_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    sources_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of sources to show. Defaults to 20.",
    )
    sources_parser.set_defaults(handler=handle_sources_list)

    source_parser = subcommands.add_parser("source", help=argparse.SUPPRESS)
    source_subcommands = source_parser.add_subparsers(
        dest="source_command", required=True
    )
    source_show_parser = source_subcommands.add_parser("show", help="Show a source.")
    source_show_parser.add_argument("source_id", type=int, help="Source id.")
    source_show_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    source_show_parser.add_argument(
        "--chunk-preview",
        type=int,
        default=160,
        help="Characters to show per chunk. Defaults to 160.",
    )
    source_show_parser.set_defaults(handler=handle_source_show)

    extract_parser = subcommands.add_parser("extract", help=argparse.SUPPRESS)
    extract_subcommands = extract_parser.add_subparsers(
        dest="extract_command", required=True
    )
    extract_stub_parser = extract_subcommands.add_parser(
        "stub", help="Run deterministic stub extraction for one source."
    )
    extract_stub_parser.add_argument("source_id", type=int, help="Source id.")
    extract_stub_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    extract_stub_parser.set_defaults(handler=handle_extract_stub)

    extract_llm_parser = extract_subcommands.add_parser(
        "llm", help="Run LLM extraction for one source."
    )
    extract_llm_parser.add_argument("source_id", type=int, help="Source id.")
    extract_llm_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    extract_llm_parser.set_defaults(handler=handle_extract_llm)

    embed_parser = subcommands.add_parser("embed", help=argparse.SUPPRESS)
    embed_subcommands = embed_parser.add_subparsers(dest="embed_command", required=True)
    embed_source_parser = embed_subcommands.add_parser(
        "source", help="Embed pending chunks for one source."
    )
    embed_source_parser.add_argument("source_id", type=int, help="Source id.")
    embed_source_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    embed_source_parser.set_defaults(handler=handle_embed_source)

    embed_pending_parser = embed_subcommands.add_parser(
        "pending", help="Embed pending chunks across sources."
    )
    embed_pending_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    embed_pending_parser.add_argument("--limit", type=int, default=20)
    embed_pending_parser.set_defaults(handler=handle_embed_pending)

    entities_parser = subcommands.add_parser("entities", help=argparse.SUPPRESS)
    entities_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    entities_parser.add_argument("--limit", type=int, default=20)
    entities_parser.add_argument("--json", action="store_true")
    entities_parser.set_defaults(handler=handle_entities_list)

    entity_parser = subcommands.add_parser("entity", help=argparse.SUPPRESS)
    entity_subcommands = entity_parser.add_subparsers(
        dest="entity_command", required=True
    )
    entity_show_parser = entity_subcommands.add_parser("show", help="Show an entity.")
    entity_show_parser.add_argument("identifier", help="Entity id, name, or alias.")
    entity_show_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    entity_show_parser.add_argument("--json", action="store_true")
    entity_show_parser.set_defaults(handler=handle_entity_show)

    claims_parser = subcommands.add_parser("claims", help=argparse.SUPPRESS)
    claims_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    claims_parser.add_argument("--limit", type=int, default=20)
    claims_parser.add_argument("--status")
    claims_parser.add_argument("--entity")
    claims_parser.set_defaults(handler=handle_claims_list)

    claim_parser = subcommands.add_parser("claim", help=argparse.SUPPRESS)
    claim_subcommands = claim_parser.add_subparsers(dest="claim_command", required=True)
    claim_show_parser = claim_subcommands.add_parser("show", help="Show a claim.")
    claim_show_parser.add_argument("claim_id", type=int)
    claim_show_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    claim_show_parser.set_defaults(handler=handle_claim_show)

    events_parser = subcommands.add_parser("events", help=argparse.SUPPRESS)
    events_subcommands = events_parser.add_subparsers(dest="events_command")
    events_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    events_parser.add_argument("--limit", type=int, default=20)
    events_parser.set_defaults(handler=handle_events_list)
    events_timeline_parser = events_subcommands.add_parser(
        "timeline", help="Show an entity event timeline."
    )
    events_timeline_parser.add_argument("--entity", required=True)
    events_timeline_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    events_timeline_parser.set_defaults(handler=handle_events_timeline)

    relations_parser = subcommands.add_parser("relations", help=argparse.SUPPRESS)
    relations_subcommands = relations_parser.add_subparsers(dest="relations_command")
    relations_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    relations_parser.add_argument("--limit", type=int, default=20)
    relations_parser.set_defaults(handler=handle_relations_list)
    relations_for_parser = relations_subcommands.add_parser(
        "for", help="List relations for an object."
    )
    relations_for_parser.add_argument("subject_type")
    relations_for_parser.add_argument("subject_id", type=int)
    relations_for_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    relations_for_parser.set_defaults(handler=handle_relations_for)

    tasks_parser = subcommands.add_parser("tasks", help=argparse.SUPPRESS)
    tasks_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    tasks_parser.add_argument("--limit", type=int, default=20)
    tasks_parser.set_defaults(handler=handle_tasks_list)

    task_parser = subcommands.add_parser("task", help=argparse.SUPPRESS)
    task_subcommands = task_parser.add_subparsers(dest="task_command", required=True)
    task_show_parser = task_subcommands.add_parser("show", help="Show a task.")
    task_show_parser.add_argument("task_id", type=int)
    task_show_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    task_show_parser.set_defaults(handler=handle_task_show)

    logs_parser = subcommands.add_parser("logs", help=argparse.SUPPRESS)
    logs_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Defaults to gmind.toml.",
    )
    logs_parser.add_argument("--limit", type=int, default=20)
    logs_parser.set_defaults(handler=handle_logs_list)

    hidden_commands = {
        "db",
        "ingest",
        "sources",
        "source",
        "extract",
        "embed",
        "entities",
        "entity",
        "claims",
        "claim",
        "events",
        "relations",
        "tasks",
        "task",
        "logs",
    }
    subcommands._choices_actions = [
        action
        for action in subcommands._choices_actions
        if action.dest not in hidden_commands
    ]

    return parser


def _add_debug_commands(debug_parser: argparse.ArgumentParser) -> None:
    debug_subcommands = debug_parser.add_subparsers(
        dest="debug_command", required=True
    )

    db_parser = debug_subcommands.add_parser("db", help="Database diagnostics.")
    db_subcommands = db_parser.add_subparsers(dest="db_command", required=True)
    db_init_parser = db_subcommands.add_parser("init")
    db_init_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    db_init_parser.set_defaults(handler=handle_db_init)
    db_check_parser = db_subcommands.add_parser("check")
    db_check_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    db_check_parser.set_defaults(handler=handle_db_check)

    pipeline_parser = debug_subcommands.add_parser(
        "pipeline", help="Run individual pipeline stages."
    )
    pipeline_subcommands = pipeline_parser.add_subparsers(
        dest="pipeline_command", required=True
    )
    pipeline_ingest_parser = pipeline_subcommands.add_parser("ingest-text")
    pipeline_ingest_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    pipeline_ingest_parser.add_argument("--title", required=True)
    pipeline_ingest_parser.add_argument("--file", type=Path, required=True)
    pipeline_ingest_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    pipeline_ingest_parser.add_argument(
        "--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP
    )
    pipeline_ingest_parser.set_defaults(handler=handle_ingest_text)

    pipeline_embed_parser = pipeline_subcommands.add_parser("embed-source")
    pipeline_embed_parser.add_argument("source_id", type=int)
    pipeline_embed_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    pipeline_embed_parser.set_defaults(handler=handle_embed_source)
    pipeline_embed_pending_parser = pipeline_subcommands.add_parser("embed-pending")
    pipeline_embed_pending_parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH
    )
    pipeline_embed_pending_parser.add_argument("--limit", type=int, default=20)
    pipeline_embed_pending_parser.set_defaults(handler=handle_embed_pending)

    pipeline_extract_stub_parser = pipeline_subcommands.add_parser("extract-stub")
    pipeline_extract_stub_parser.add_argument("source_id", type=int)
    pipeline_extract_stub_parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH
    )
    pipeline_extract_stub_parser.set_defaults(handler=handle_extract_stub)
    pipeline_extract_llm_parser = pipeline_subcommands.add_parser("extract-llm")
    pipeline_extract_llm_parser.add_argument("source_id", type=int)
    pipeline_extract_llm_parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH
    )
    pipeline_extract_llm_parser.set_defaults(handler=handle_extract_llm)

    sources_parser = debug_subcommands.add_parser("sources")
    sources_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    sources_parser.add_argument("--limit", type=int, default=20)
    sources_parser.set_defaults(handler=handle_sources_list)

    source_parser = debug_subcommands.add_parser("source")
    source_subcommands = source_parser.add_subparsers(
        dest="source_command", required=True
    )
    source_show_parser = source_subcommands.add_parser("show")
    source_show_parser.add_argument("source_id", type=int)
    source_show_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    source_show_parser.add_argument("--chunk-preview", type=int, default=160)
    source_show_parser.set_defaults(handler=handle_source_show)

    entities_parser = debug_subcommands.add_parser("entities")
    entities_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    entities_parser.add_argument("--limit", type=int, default=20)
    entities_parser.add_argument("--json", action="store_true")
    entities_parser.set_defaults(handler=handle_entities_list)

    entity_parser = debug_subcommands.add_parser("entity")
    entity_subcommands = entity_parser.add_subparsers(
        dest="entity_command", required=True
    )
    entity_show_parser = entity_subcommands.add_parser("show")
    entity_show_parser.add_argument("identifier")
    entity_show_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    entity_show_parser.add_argument("--json", action="store_true")
    entity_show_parser.set_defaults(handler=handle_entity_show)

    claims_parser = debug_subcommands.add_parser("claims")
    claims_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    claims_parser.add_argument("--limit", type=int, default=20)
    claims_parser.add_argument("--status")
    claims_parser.add_argument("--entity")
    claims_parser.set_defaults(handler=handle_claims_list)

    claim_parser = debug_subcommands.add_parser("claim")
    claim_subcommands = claim_parser.add_subparsers(
        dest="claim_command", required=True
    )
    claim_show_parser = claim_subcommands.add_parser("show")
    claim_show_parser.add_argument("claim_id", type=int)
    claim_show_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    claim_show_parser.set_defaults(handler=handle_claim_show)

    events_parser = debug_subcommands.add_parser("events")
    events_subcommands = events_parser.add_subparsers(dest="events_command")
    events_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    events_parser.add_argument("--limit", type=int, default=20)
    events_parser.set_defaults(handler=handle_events_list)
    events_timeline_parser = events_subcommands.add_parser("timeline")
    events_timeline_parser.add_argument("--entity", required=True)
    events_timeline_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    events_timeline_parser.set_defaults(handler=handle_events_timeline)

    relations_parser = debug_subcommands.add_parser("relations")
    relations_subcommands = relations_parser.add_subparsers(dest="relations_command")
    relations_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    relations_parser.add_argument("--limit", type=int, default=20)
    relations_parser.set_defaults(handler=handle_relations_list)
    relations_for_parser = relations_subcommands.add_parser("for")
    relations_for_parser.add_argument("subject_type")
    relations_for_parser.add_argument("subject_id", type=int)
    relations_for_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    relations_for_parser.set_defaults(handler=handle_relations_for)

    tasks_parser = debug_subcommands.add_parser("tasks")
    tasks_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    tasks_parser.add_argument("--limit", type=int, default=20)
    tasks_parser.set_defaults(handler=handle_tasks_list)

    task_parser = debug_subcommands.add_parser("task")
    task_subcommands = task_parser.add_subparsers(dest="task_command", required=True)
    task_show_parser = task_subcommands.add_parser("show")
    task_show_parser.add_argument("task_id", type=int)
    task_show_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    task_show_parser.set_defaults(handler=handle_task_show)

    logs_parser = debug_subcommands.add_parser("logs")
    logs_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    logs_parser.add_argument("--limit", type=int, default=20)
    logs_parser.set_defaults(handler=handle_logs_list)


def handle_init(args: argparse.Namespace) -> int:
    path = init_config(args.config, overwrite=args.overwrite)
    print(f"Created config: {path}")
    return 0


def handle_config_show(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except ValueError as error:
        print(f"Config error: {error}", file=sys.stderr)
        print("Run `gmind init` to create a config file.", file=sys.stderr)
        return 2

    print(json.dumps(asdict(config), ensure_ascii=False, indent=2))
    return 0


def handle_db_init(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        init_database(config.database.url)
    except ValueError as error:
        print(f"Config error: {error}", file=sys.stderr)
        print("Run `gmind init` to create a config file.", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Database init failed: {error}", file=sys.stderr)
        return 1

    print("Database initialized.")
    return 0


def handle_db_check(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        check = check_database(config.database.url)
    except ValueError as error:
        print(f"Config error: {error}", file=sys.stderr)
        print("Run `gmind init` to create a config file.", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Database check failed: {error}", file=sys.stderr)
        return 1

    print(f"vector extension: {'ok' if check.vector_extension else 'missing'}")
    print(f"tables: {len(check.tables)} found")
    print(f"views: {len(check.views)} found")

    if check.missing_tables:
        print("missing tables: " + ", ".join(check.missing_tables))
    if check.missing_views:
        print("missing views: " + ", ".join(check.missing_views))

    if not check.ok:
        return 1

    print("Database check passed.")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        check = check_database(config.database.url)
        entities = list_entities(config.database.url, limit=100)
    except ValueError as error:
        if args.json:
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Config error: {error}", file=sys.stderr)
            print("Run `gmind setup` to create a config file.", file=sys.stderr)
        return 2
    except Exception as error:
        if args.json:
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Status check failed: {error}", file=sys.stderr)
        return 1

    claim_count = sum(entity.claim_count for entity in entities)
    event_count = sum(entity.event_count for entity in entities)
    payload = {
        "ok": check.ok,
        "database": {
            "vector_extension": check.vector_extension,
            "tables": len(check.tables),
            "views": len(check.views),
            "missing_tables": check.missing_tables,
            "missing_views": check.missing_views,
        },
        "knowledge": {
            "entities": len(entities),
            "claims": claim_count,
            "events": event_count,
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if check.ok else 1

    print(f"gmind: {'ready' if check.ok else 'needs attention'}")
    print(f"database: {'ok' if check.ok else 'not ready'}")
    print(f"knowledge: {len(entities)} knowledge points, {claim_count} facts, {event_count} events")
    if check.missing_tables:
        print("missing tables: " + ", ".join(check.missing_tables))
    if check.missing_views:
        print("missing views: " + ", ".join(check.missing_views))
    return 0 if check.ok else 1


def handle_doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, object]] = []

    config_exists = args.config.exists()
    checks.append(
        {
            "name": "config",
            "ok": config_exists,
            "detail": str(args.config) if config_exists else "config file not found",
            "fix": None if config_exists else "Run `gmind setup` or open Settings in the app.",
        }
    )
    if not config_exists:
        return _print_doctor(args, checks, ok=False)

    try:
        config = load_config(args.config)
    except ValueError as error:
        checks.append(
            {
                "name": "config_valid",
                "ok": False,
                "detail": str(error),
                "fix": "Check database.url in your config.",
            }
        )
        return _print_doctor(args, checks, ok=False)

    api_key_present = bool(os.getenv(config.models.llm_api_key_env))
    checks.append(
        {
            "name": "api_key",
            "ok": api_key_present,
            "detail": config.models.llm_api_key_env,
            "fix": None
            if api_key_present
            else f"Set {config.models.llm_api_key_env} in your shell or app Keychain.",
        }
    )

    try:
        check = check_database(config.database.url)
        checks.append(
            {
                "name": "database",
                "ok": check.ok,
                "detail": {
                    "vector_extension": check.vector_extension,
                    "tables": len(check.tables),
                    "views": len(check.views),
                    "missing_tables": check.missing_tables,
                    "missing_views": check.missing_views,
                },
                "fix": None if check.ok else "Run `gmind debug db init` or check database permissions.",
            }
        )
    except Exception as error:
        checks.append(
            {
                "name": "database",
                "ok": False,
                "detail": str(error),
                "fix": "Check database.url and network access.",
            }
        )

    try:
        entities = list_entities(config.database.url, limit=100)
        checks.append(
            {
                "name": "knowledge",
                "ok": True,
                "detail": {
                    "entities": len(entities),
                    "claims": sum(entity.claim_count for entity in entities),
                    "events": sum(entity.event_count for entity in entities),
                },
                "fix": None,
            }
        )
    except Exception as error:
        checks.append(
            {
                "name": "knowledge",
                "ok": False,
                "detail": str(error),
                "fix": "Fix database before reading knowledge.",
            }
        )

    ok = all(bool(check["ok"]) for check in checks)
    return _print_doctor(args, checks, ok=ok)


def handle_add_text(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        text = _read_add_text(args)
        source_type = "markdown" if args.add_command == "markdown" else "text"
        solo_decision = None
        llm_provider = None
        if args.dry_run and not args.solo:
            raise ValueError("--dry-run requires --solo")
        if not args.title:
            llm_provider = build_llm_provider(config.models)
        title = _add_title(args, text, llm_provider)
        if args.solo:
            if args.file is None:
                raise ValueError("--solo requires --file input")
            llm_provider = llm_provider or build_llm_provider(config.models)
            solo_decision = judge_solo_add_file(
                title=title,
                file_path=args.file,
                text=text,
                provider=llm_provider,
            )
            record_solo_add_decision(
                config.database.url,
                title=title,
                file_path=args.file,
                decision=solo_decision,
                dry_run=args.dry_run,
            )
            if args.dry_run or not solo_decision.should_ingest:
                payload = {
                    "source_id": None,
                    "chunk_count": 0,
                    "chunks_embedded": None,
                    "entities_created": None,
                    "claims_created": None,
                    "events_created": None,
                    "skipped": not solo_decision.should_ingest,
                    "dry_run": args.dry_run,
                    "title": title,
                    "source_path": _source_path(args.file),
                    "solo_decision": asdict(solo_decision),
                }
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                elif args.dry_run:
                    print(
                        "Solo would "
                        f"{'add' if solo_decision.should_ingest else 'skip'}: "
                        f"{solo_decision.reason} "
                        f"(confidence={solo_decision.confidence:.2f})"
                    )
                else:
                    print(
                        "Solo skipped: "
                        f"{solo_decision.reason} "
                        f"(confidence={solo_decision.confidence:.2f})"
                    )
                return 0

        ingest_result = ingest_text_source(
            config.database.url,
            title=title,
            text=text,
            source_type=source_type,
            source_path=_source_path(args.file),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        payload = {
            "source_id": ingest_result.source_id,
            "chunk_count": ingest_result.chunk_count,
            "chunks_embedded": None,
            "entities_created": None,
            "claims_created": None,
            "events_created": None,
            "skipped": False,
            "solo_decision": asdict(solo_decision) if solo_decision else None,
        }
        if not args.json:
            if solo_decision is not None:
                print(
                    "Solo accepted: "
                    f"{solo_decision.reason} "
                    f"(confidence={solo_decision.confidence:.2f})"
                )
            print(
                f"Added source {ingest_result.source_id} "
                f"with {ingest_result.chunk_count} chunks."
            )

        if not args.skip_embed:
            embedding_provider = build_embedding_provider(config.models)
            embed_result = embed_source_chunks(
                config.database.url,
                source_id=ingest_result.source_id,
                model_config=config.models,
                provider=embedding_provider,
            )
            embedded = 0 if embed_result is None else embed_result.chunks_embedded
            payload["chunks_embedded"] = embedded
            if not args.json:
                print(f"Embedded {embedded} chunks.")

        if not args.skip_extract:
            llm_provider = llm_provider or build_llm_provider(config.models)
            extract_result = extract_llm_source(
                config.database.url,
                ingest_result.source_id,
                llm_provider,
            )
            if extract_result is None:
                print("Extraction skipped: source not found.", file=sys.stderr)
                return 1
            payload["entities_created"] = extract_result.entities_created
            payload["claims_created"] = extract_result.claims_created
            payload["events_created"] = extract_result.events_created
            if not args.json:
                print(
                    "Extracted "
                    f"{extract_result.entities_created} entities, "
                    f"{extract_result.claims_created} claims, "
                    f"{extract_result.events_created} events."
                )
    except ValueError as error:
        print(f"Add error: {error}", file=sys.stderr)
        return 2
    except FileNotFoundError as error:
        print(f"Add error: file not found: {error.filename}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Add failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def _read_add_text(args: argparse.Namespace) -> str:
    if args.file is not None:
        return args.file.read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    if args.stdin:
        return sys.stdin.read()
    raise ValueError("No text input provided.")


def _add_title(args: argparse.Namespace, text: str, llm_provider) -> str:
    if args.title:
        return args.title
    if llm_provider is None:
        raise ValueError("LLM provider is required when --title is omitted")
    return llm_provider.suggest_source_title(
        source_path=_source_path(args.file),
        text_preview=text.strip()[:12000],
    )


def _source_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.expanduser().resolve())


def handle_ask(args: argparse.Namespace) -> int:
    question = " ".join(args.question).strip()
    try:
        config = load_config(args.config)
        embedding_provider = build_embedding_provider(config.models)
        llm_provider = build_llm_provider(config.models)
        result = answer_question(
            config.database.url,
            question=question,
            model_config=config.models,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )
    except ValueError as error:
        print(f"Ask error: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Ask failed: {error}", file=sys.stderr)
        return 1

    return _print_ask_result(args, result)


def handle_ingest_text(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        text = args.file.read_text(encoding="utf-8")
        result = ingest_text_source(
            config.database.url,
            title=args.title,
            text=text,
            source_path=_source_path(args.file),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    except ValueError as error:
        print(f"Ingest error: {error}", file=sys.stderr)
        return 2
    except FileNotFoundError as error:
        print(f"Ingest error: file not found: {error.filename}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Ingest failed: {error}", file=sys.stderr)
        return 1

    print(
        f"Ingested source {result.source_id} with {result.chunk_count} source chunks."
    )
    return 0


def handle_sources_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        sources = list_sources(config.database.url, limit=args.limit)
    except ValueError as error:
        print(f"Sources error: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Sources failed: {error}", file=sys.stderr)
        return 1

    if not sources:
        print("No sources found.")
        return 0

    print("id\ttype\tchunks\tcreated_at\ttitle")
    for source in sources:
        print(
            f"{source.id}\t{source.source_type}\t{source.chunk_count}"
            f"\t{source.created_at}\t{source.title}"
        )
    return 0


def handle_source_show(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        source = get_source(config.database.url, args.source_id)
    except Exception as error:
        print(f"Source failed: {error}", file=sys.stderr)
        return 1

    if source is None:
        print(f"Source not found: {args.source_id}", file=sys.stderr)
        return 2

    print(f"id: {source.id}")
    print(f"title: {source.title}")
    print(f"type: {source.source_type}")
    print(f"created_at: {source.created_at}")
    print(f"chunks: {len(source.chunks)}")

    for chunk in source.chunks:
        preview = _preview_text(chunk.chunk_text, args.chunk_preview)
        print("")
        print(f"chunk {chunk.chunk_index} [{chunk.id}]")
        print(preview)

    return 0


def _preview_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def handle_extract_stub(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        result = extract_stub_source(config.database.url, args.source_id)
    except Exception as error:
        print(f"Extract failed: {error}", file=sys.stderr)
        return 1

    if result is None:
        print(f"Source not found: {args.source_id}", file=sys.stderr)
        return 2

    print(f"Extracted source {result.source_id}.")
    print(f"entities_created: {result.entities_created}")
    print(f"claims_created: {result.claims_created}")
    print(f"events_created: {result.events_created}")
    print(f"relations_created: {result.relations_created}")
    return 0


def handle_extract_llm(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        provider = build_llm_provider(config.models)
        result = extract_llm_source(config.database.url, args.source_id, provider)
    except Exception as error:
        print(f"Extract failed: {error}", file=sys.stderr)
        return 1

    if result is None:
        print(f"Source not found: {args.source_id}", file=sys.stderr)
        return 2

    print(f"Extracted source {result.source_id}.")
    print(f"entities_created: {result.entities_created}")
    print(f"claims_created: {result.claims_created}")
    print(f"events_created: {result.events_created}")
    print(f"relations_created: {result.relations_created}")
    return 0


def handle_embed_source(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        provider = build_embedding_provider(config.models)
        result = embed_source_chunks(
            config.database.url,
            source_id=args.source_id,
            model_config=config.models,
            provider=provider,
        )
    except Exception as error:
        print(f"Embed failed: {error}", file=sys.stderr)
        return 1

    if result is None:
        print(f"Source not found: {args.source_id}", file=sys.stderr)
        return 2

    print(f"Embedded {result.chunks_embedded} chunks for source {args.source_id}.")
    return 0


def handle_embed_pending(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        provider = build_embedding_provider(config.models)
        result = embed_pending_chunks(
            config.database.url,
            limit=args.limit,
            model_config=config.models,
            provider=provider,
        )
    except ValueError as error:
        print(f"Embed error: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Embed failed: {error}", file=sys.stderr)
        return 1

    print(f"Embedded {result.chunks_embedded} pending chunks.")
    return 0


def handle_entities_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        entities = list_entities(config.database.url, limit=args.limit)
    except Exception as error:
        print(f"Entities failed: {error}", file=sys.stderr)
        return 1

    if not entities:
        if args.json:
            print(json.dumps([], ensure_ascii=False))
            return 0
        print("No entities found.")
        return 0

    if args.json:
        print(json.dumps([asdict(entity) for entity in entities], ensure_ascii=False))
        return 0

    print("id\ttype\tstatus\tclaims\tevents\tname")
    for entity in entities:
        print(
            f"{entity.id}\t{entity.entity_type}\t{entity.status}"
            f"\t{entity.claim_count}\t{entity.event_count}\t{entity.name}"
        )
    return 0


def handle_entity_show(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        entity = get_entity(config.database.url, args.identifier)
    except Exception as error:
        print(f"Entity failed: {error}", file=sys.stderr)
        return 1

    if entity is None:
        print(f"Entity not found: {args.identifier}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(entity), ensure_ascii=False))
        return 0

    print(f"id: {entity.id}")
    print(f"name: {entity.name}")
    print(f"type: {entity.entity_type}")
    print(f"status: {entity.status}")
    if entity.description:
        print(f"description: {entity.description}")

    _print_claims("claims", entity.claims)
    _print_events("events", entity.events)
    _print_tasks("tasks", entity.tasks)
    _print_relations("relations", entity.relations)
    return 0


def handle_claims_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        claims = list_claims(
            config.database.url,
            limit=args.limit,
            status=args.status,
            entity=args.entity,
        )
    except Exception as error:
        print(f"Claims failed: {error}", file=sys.stderr)
        return 1

    _print_claims("claims", claims)
    return 0


def handle_claim_show(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        claim = get_claim(config.database.url, args.claim_id)
    except Exception as error:
        print(f"Claim failed: {error}", file=sys.stderr)
        return 1

    if claim is None:
        print(f"Claim not found: {args.claim_id}", file=sys.stderr)
        return 2

    print(f"id: {claim.id}")
    print(f"type: {claim.claim_type}")
    print(f"origin: {claim.origin}")
    print(f"status: {claim.status}")
    print(f"confidence: {claim.confidence}")
    print(f"source_id: {claim.source_id}")
    print(f"source_chunk_id: {claim.source_chunk_id}")
    print(f"text: {claim.text}")
    if claim.source_chunk_text:
        print("")
        print("evidence:")
        print(_preview_text(claim.source_chunk_text, 260))
    _print_entities("entities", claim.entities)
    _print_relations("relations", claim.relations)
    return 0


def handle_events_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        events = list_events(config.database.url, limit=args.limit)
    except Exception as error:
        print(f"Events failed: {error}", file=sys.stderr)
        return 1

    _print_events("events", events)
    return 0


def handle_events_timeline(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        events = list_events(config.database.url, entity=args.entity, limit=100)
    except Exception as error:
        print(f"Timeline failed: {error}", file=sys.stderr)
        return 1

    _print_events(f"timeline: {args.entity}", events)
    return 0


def handle_relations_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        relations = list_relations(config.database.url, limit=args.limit)
    except Exception as error:
        print(f"Relations failed: {error}", file=sys.stderr)
        return 1

    _print_relations("relations", relations)
    return 0


def handle_relations_for(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        relations = list_relations(
            config.database.url,
            subject_type=args.subject_type,
            subject_id=args.subject_id,
            limit=100,
        )
    except Exception as error:
        print(f"Relations failed: {error}", file=sys.stderr)
        return 1

    _print_relations(
        f"relations for {args.subject_type} {args.subject_id}",
        relations,
    )
    return 0


def handle_tasks_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        tasks = list_tasks(config.database.url, limit=args.limit)
    except Exception as error:
        print(f"Tasks failed: {error}", file=sys.stderr)
        return 1

    _print_tasks("tasks", tasks)
    return 0


def handle_task_show(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        task = get_task(config.database.url, args.task_id)
    except Exception as error:
        print(f"Task failed: {error}", file=sys.stderr)
        return 1

    if task is None:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 2

    print(f"id: {task.id}")
    print(f"type: {task.task_type}")
    print(f"title: {task.title}")
    print(f"status: {task.status}")
    print(f"priority: {task.priority}")
    print(f"related_entity_id: {task.related_entity_id}")
    print(f"source_id: {task.source_id}")
    print(f"claim_id: {task.claim_id}")
    print(f"event_id: {task.event_id}")
    print(f"next_run_at: {task.next_run_at}")
    if task.description:
        print(f"description: {task.description}")
    if task.last_error:
        print(f"last_error: {task.last_error}")
    return 0


def handle_logs_list(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        logs = list_logs(config.database.url, limit=args.limit)
    except Exception as error:
        print(f"Logs failed: {error}", file=sys.stderr)
        return 1

    if not logs:
        print("No logs found.")
        return 0

    print("id\taction\tobject\tcreated_at\ttitle")
    for log in logs:
        object_label = "-"
        if log.object_type and log.object_id is not None:
            object_label = f"{log.object_type}:{log.object_id}"
        print(f"{log.id}\t{log.action}\t{object_label}\t{log.created_at}\t{log.title}")
    return 0


def _print_entities(title: str, entities) -> None:
    print("")
    print(title)
    if not entities:
        print("  none")
        return
    for entity in entities:
        print(f"  [{entity.id}] {entity.name} ({entity.entity_type}, {entity.status})")


def _print_claims(title: str, claims) -> None:
    print("")
    print(title)
    if not claims:
        print("  none")
        return
    for claim in claims:
        text = _preview_text(claim.text, 120)
        print(
            f"  [{claim.id}] {claim.status}/{claim.origin}/{claim.claim_type} "
            f"conf={claim.confidence}: {text}"
        )


def _print_events(title: str, events) -> None:
    print("")
    print(title)
    if not events:
        print("  none")
        return
    for event in events:
        occurred_at = event.occurred_at or "unknown"
        print(
            f"  [{event.id}] {occurred_at} {event.event_type} "
            f"conf={event.confidence}: {event.title}"
        )


def _print_tasks(title: str, tasks) -> None:
    print("")
    print(title)
    if not tasks:
        print("  none")
        return
    for task in tasks:
        print(
            f"  [{task.id}] {task.status} p={task.priority} "
            f"{task.task_type}: {task.title}"
        )


def _print_relations(title: str, relations) -> None:
    print("")
    print(title)
    if not relations:
        print("  none")
        return
    for relation in relations:
        print(
            f"  [{relation.id}] {relation.subject_type}:{relation.subject_id} "
            f"--{relation.predicate}--> "
            f"{relation.object_type}:{relation.object_id} "
            f"conf={relation.confidence}"
        )


def _print_ask_result(args: argparse.Namespace, result: AskResult) -> int:
    if args.json:
        print(
            json.dumps(
                {
                    "question": result.question,
                    "answer": result.answer,
                    "evidence": [asdict(item) for item in result.evidence],
                    "followups": result.followups,
                },
                ensure_ascii=False,
            )
        )
        return 0

    print(result.answer)
    if result.evidence:
        print("")
        print("evidence")
        for item in result.evidence:
            print(
                f"  - source:{item.source_id} chunk:{item.chunk_id} "
                f"score={item.score:.3f} {item.title}: {_preview_text(item.text, 90)}"
            )
    if result.followups:
        print("")
        print("followups")
        for item in result.followups:
            print(f"  - {item}")
    return 0


def _print_doctor(
    args: argparse.Namespace,
    checks: list[dict[str, object]],
    *,
    ok: bool,
) -> int:
    if args.json:
        print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False))
        return 0 if ok else 1

    print(f"gmind doctor: {'ok' if ok else 'needs attention'}")
    for check in checks:
        marker = "ok" if check["ok"] else "fail"
        print(f"- {check['name']}: {marker}")
        detail = check.get("detail")
        if detail:
            print(f"  detail: {detail}")
        fix = check.get("fix")
        if fix:
            print(f"  fix: {fix}")
    return 0 if ok else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
