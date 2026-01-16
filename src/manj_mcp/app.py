#!/usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2025 sakakibara <sakakibara@organon>
#
# Distributed under terms of the MIT license.

from mcp.server.fastmcp import FastMCP

# from mcp.server.fastmcp.auth import TokenAuthBackend
import meilisearch
import os
import manj_ast
from google.cloud import storage
import gzip
import tempfile
import subprocess
import json

# https://www.meilisearch.com/docs/learn/chat/getting_started_with_chat : chat
# https://www.meilisearch.com/docs/learn/chat/chat_tooling_reference : chat
# https://www.meilisearch.com/docs/learn/ai_powered_search/getting_started_with_ai_search : ai_powerd_search
# https://www.meilisearch.com/docs/learn/chat/conversational_search : conversational
# https://www.meilisearch.com/docs/guides/ai/mcp#model-context-protocol-talk-to-meilisearch-with-claude-desktop : MCP
# https://www.meilisearch.com/docs/learn/async/working_with_tasks :tasks

# localization
# dumps

mcp = FastMCP(
    "ManMCP",
    json_response=True,
    host="0.0.0.0",
    port=8080,
)


MEILI_HOST = os.getenv("MEILI_HOST", "http://search:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY")
client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)

index = client.index("man-pages")

# Google Cloud Storage client
_storage_client: storage.Client | None = None


def get_storage_client() -> storage.Client:
    """Get or create a singleton Google Cloud Storage client."""
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def get_bucket() -> storage.Bucket:
    """Get the GCS bucket for man pages."""
    client = get_storage_client()
    bucket_name = os.getenv("BUCKET_NAME")
    if not bucket_name:
        raise ValueError("BUCKET_NAME environment variable is not set")
    return client.get_bucket(bucket_name)


# MeiliSearchでman pagesを検索するツール
@mcp.tool()
def search_man_pages(
    query: str,
    limit: int = 10,
    offset: int = 0,
    distro: str | None = None,
    section: str | None = None,
    command: str | None = None,
    version: str | None = None,
    hybrid: bool = False,
    semantic_ratio: float = 0.5,
) -> dict:
    """
    Search man pages using MeiliSearch with optional filters and hybrid search.

    Args:
        query: Search query string (e.g., "grep", "ldd security", "pldd bugs")
        limit: Maximum number of results to return (default: 10)
        offset: Number of results to skip (default: 0)
        distro: Filter by distribution (e.g., "debian", "alpine")
        section: Filter by man section (e.g., "1", "8")
        command: Filter by command name (e.g., "grep", "ldd")
        version: Filter by distribution version (e.g., "12.12", "3.22.2")
        hybrid: Enable hybrid search (semantic + keyword) using Gemini embeddings (default: False)
        semantic_ratio: Ratio of semantic vs keyword search (0.0-1.0, default: 0.5)
                       0.0 = pure keyword, 1.0 = pure semantic

    Returns:
        Dictionary containing search results with man page content
    """
    search_params: dict[str, int | str | dict] = {"limit": limit, "offset": offset}

    # Build filter string (filterable attributes: distro, section, command, version)
    filters = []
    if distro:
        filters.append(f"distro = '{distro}'")
    if section:
        filters.append(f"section = {section}")
    if command:
        filters.append(f"command = '{command}'")
    if version:
        filters.append(f"version = '{version}'")

    if filters:
        search_params["filter"] = " AND ".join(filters)

    # Enable hybrid search if requested
    if hybrid:
        search_params["hybrid"] = {
            "embedder": "man-gemini",
            "semanticRatio": semantic_ratio,
        }

    # Debug logging
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Search params: {search_params}")

    return index.search(query, search_params)


# @man://diffman-git を読んで。のようにすると、読んでくれる。
# LLMに読ませるためのresource.
# @mcp.resource("man://{command}")
# def get_command_options(command: str):
#     return index.search(command)


# @greeting://fuga を読んで。のようにすると、読んでくれる。
# LLMに読ませるresource.
# @mcp.resource("greeting://{name}")
# def get_greeting(name: str) -> str:
#     return f"Hello {name}"


# LLMに送るprompt を作成する。これはその雛形。
# つまり、これはLLM前の仕組み。
# @mcp.prompt()
# def greet_user(name: str, style: str = "friendly") -> str:
#     styles = {
#         "friendly": "Please write a warm, friendly greeting",
#         "formal": "Please write a formal, professional greeting",
#         "casual": "Please write a casual, relaxed greeting",
#     }
#
#     return f"{styles.get(style, styles['friendly'])} for someone named {name}."


# Natural language to command pipeline prompt
@mcp.prompt()
def suggest_command_pipeline(task_description: str) -> list[dict]:
    """
    Suggest Unix command pipeline from natural language description.

    This prompt guides Claude Code to search multiple man pages and construct
    a safe command pipeline based on the user's task description.

    Args:
        task_description: What you want to accomplish in natural language
          (e.g., "sort files by modification time and delete top 5")

    Returns:
        A prompt that instructs Claude to use search_man_pages tool multiple times
    """
    return [
        {
            "role": "user",
            "content": f"""You are a Unix command expert with access to man pages via MeiliSearch.

**User's Task:** {task_description}

**Your Mission:**
1. Use the `search_man_pages` tool MULTIPLE TIMES to find relevant commands
2. Enable hybrid search (hybrid=true) for semantic matching when searching
3. Search for concepts, not just command names (e.g., "list files", "sort by time", "delete files")
4. Consider common Unix commands: ls, find, sort, head, tail, xargs, rm, awk, sed, grep, etc.
5. Construct a safe command pipeline with explanations
6. WARN about dangerous operations (rm, mv, chmod, etc.)

**Example Search Queries:**
- search_man_pages(query="list files with details", hybrid=true)
- search_man_pages(query="sort by modification time", hybrid=true)
- search_man_pages(query="limit output to first N items", hybrid=true)
- search_man_pages(query="delete files safely", hybrid=true)
- search_man_pages(query="batch operations on files", hybrid=true)

**Output Format:**
1. List the relevant commands you found
2. Explain what each command does (based on man pages)
3. Propose a complete pipeline
4. Add safety warnings if needed
5. Suggest a dry-run option (e.g., using echo or -n flag)

Remember: Search multiple times, think step by step, and prioritize safety!""",
        }
    ]


# Man page parsing tools using manj-ast-py
def get_man_pages_json(hit):
    language = "en"
    blob_path = f"latest/{hit['distro']}/{hit['version']}/{language}/man/man{hit['section']}/{hit['command']}.{hit['section']}.gz"

    # Download from GCS
    bucket = get_bucket()
    blob = bucket.get_blob(blob_path)
    if blob is None:
        raise Exception(f"Man page file not found in storage: {blob_path}")

    # Download to memory and decompress
    compressed_data = blob.download_as_bytes()
    decompressed_data = gzip.decompress(compressed_data)

    # Use a temporary file with auto-deletion
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".man", delete=True) as tmp:
        tmp.write(decompressed_data)
        tmp.flush()

        # Parse to JSON and extract sections
        json_str = manj_ast.roff_to_json(tmp.name)
        # sections = manj_ast.list_sections_py(json_str)
    return json_str


@mcp.tool()
def list_man_page_sections(
    command: str,
    distro: str | None = None,
    section: str | None = None,
) -> list[str]:
    """
    List all section headers (SH) and subsections (SS) from a man page.

    This tool searches for a man page by command name, downloads it from
    Google Cloud Storage, and extracts all section names. Useful for exploring
    the structure of a man page before extracting specific sections.

    Common sections: NAME, SYNOPSIS, DESCRIPTION, OPTIONS, EXAMPLES, SEE ALSO, BUGS

    Args:
        command: Command name to look up (e.g., "ls", "grep")
        distro: Optional distribution filter (e.g., "debian", "alpine")
        section: Optional man section filter (e.g., "1", "8")

    Returns:
        List of section names. Subsections are prefixed with "  " (two spaces).
        Example: ["NAME", "SYNOPSIS", "DESCRIPTION", "  Basic Usage", "OPTIONS"]

    Raises:
        Exception: If man page not found or cannot be parsed
    """
    # Search for the man page in MeiliSearch
    search_params: dict[str, int | str] = {"limit": 1}
    filters = [f"command = '{command}'"]
    if distro:
        filters.append(f"distro = '{distro}'")
    if section:
        filters.append(f"section = {section}")
    search_params["filter"] = " AND ".join(filters)

    results = index.search("", search_params)
    if not results["hits"]:
        raise Exception(
            f"Man page not found: {command}"
            + (f" (distro={distro})" if distro else "")
            + (f" (section={section})" if section else "")
        )
    hit = results["hits"][0]

    json_str = get_man_pages_json(hit)
    sections = manj_ast.list_sections_py(json_str)
    return sections


@mcp.tool()
def get_man_page_section(
    command: str,
    section_names: list[str],
    distro: str | None = None,
    section: str | None = None,
) -> str:
    """
    Extract and display specific sections from a man page.

    This tool searches for a man page, downloads it from Google Cloud Storage,
    extracts the specified sections, and formats them for display using col -b.

    Args:
        command: Command name to look up (e.g., "ls", "grep")
        section_names: List of section names to extract (e.g., ["OPTIONS"], ["DESCRIPTION", "EXAMPLES"])
        distro: Optional distribution filter (e.g., "debian", "alpine")
        section: Optional man section filter (e.g., "1", "8")

    Returns:
        Formatted text content of the requested sections

    Raises:
        Exception: If man page not found, sections not found, or cannot be parsed

    Examples:
        # Get just the OPTIONS section
        get_man_page_section("ls", ["OPTIONS"])

        # Get multiple sections
        get_man_page_section("grep", ["DESCRIPTION", "EXAMPLES"])
    """
    # Search for the man page in MeiliSearch
    search_params: dict[str, int | str] = {"limit": 1}
    filters = [f"command = '{command}'"]
    if distro:
        filters.append(f"distro = '{distro}'")
    if section:
        filters.append(f"section = {section}")
    search_params["filter"] = " AND ".join(filters)

    results = index.search("", search_params)
    if not results["hits"]:
        raise Exception(
            f"Man page not found: {command}"
            + (f" (distro={distro})" if distro else "")
            + (f" (section={section})" if section else "")
        )
    hit = results["hits"][0]

    json_str = get_man_pages_json(hit)
    roff_text = manj_ast.extract_section(json_str, section_names)

    # Debug: Log the roff text length and first 500 chars
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Extracted roff text length: {len(roff_text)}")
    logger.info(f"Roff text preview: {roff_text[:500]}")

    # Format with mandoc | col -b
    man_result = subprocess.run(
        ["mandoc", "-c"],
        input=roff_text.encode(),
        capture_output=True,
        check=False,  # Don't raise exception immediately
    )

    # Debug: Log mandoc result
    logger.info(f"mandoc exit code: {man_result.returncode}")
    if man_result.stderr:
        logger.error(f"mandoc stderr: {man_result.stderr.decode()}")

    if man_result.returncode != 0:
        raise Exception(
            f"mandoc failed with exit code {man_result.returncode}: {man_result.stderr.decode()}"
        )

    col_result = subprocess.run(
        ["col", "-b"],
        input=man_result.stdout,
        capture_output=True,
        check=True,
    )

    return col_result.stdout.decode()
