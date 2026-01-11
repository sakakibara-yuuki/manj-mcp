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
