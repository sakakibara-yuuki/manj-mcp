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


# Man page parsing tools using manj-ast-py


@mcp.tool()
def parse_man_to_json(file_path: str) -> dict:
    """
    Parse a roff/man format file and convert it to unist-format JSON.

    This tool converts man pages (both compressed .gz and uncompressed formats)
    into structured JSON using the unist (Universal Syntax Tree) format.
    The resulting JSON can be used for further processing, analysis, or conversion.

    Args:
        file_path: Path to the roff/man file (supports .gz compressed files)
                  e.g., "/usr/share/man/man1/ls.1.gz" or "ls.1"

    Returns:
        Dictionary containing the unist-format JSON structure with:
        - type: node type (root, section, paragraph, text, etc.)
        - children: nested nodes
        - value: text content (for text nodes)
        - Additional metadata depending on node type

    Raises:
        Exception: If the file cannot be found, read, or parsed
    """
    json_str = manj_ast.roff_to_json(file_path)
    import json

    return json.loads(json_str)


@mcp.tool()
def convert_json_to_roff(json_data: dict | str) -> str:
    """
    Convert unist-format JSON back to roff format.

    This tool takes structured JSON (in unist format) and converts it back
    to roff markup that can be displayed with man, rendered to other formats,
    or saved as a man page file.

    Args:
        json_data: Either a dictionary containing unist-format JSON structure,
                   or a JSON string representing the structure

    Returns:
        String containing roff format markup (e.g., ".TH COMMAND 1\\n.SH NAME\\n...")

    Raises:
        Exception: If the JSON structure is invalid or cannot be converted
    """
    import json

    if isinstance(json_data, dict):
        json_str = json.dumps(json_data)
    else:
        json_str = json_data

    return manj_ast.json_to_roff(json_str)


@mcp.tool()
def list_man_sections(json_data: dict | str) -> list[str]:
    """
    List all section headers (SH) and subsections (SS) from a man page JSON.

    This tool extracts all section and subsection names from a parsed man page,
    making it easy to see the structure and navigate to specific parts.
    Subsections are indented with "  " prefix to show hierarchy.

    Common man page sections include:
    - NAME: Command name and brief description
    - SYNOPSIS: Command syntax
    - DESCRIPTION: Detailed description
    - OPTIONS: Command-line options
    - EXAMPLES: Usage examples
    - SEE ALSO: Related commands
    - BUGS: Known issues
    - AUTHOR: Author information

    Args:
        json_data: Either a dictionary containing unist-format JSON structure,
                   or a JSON string representing the structure from parse_man_to_json

    Returns:
        List of section names. Subsections (SS) are prefixed with "  " (two spaces)
        Example: ["NAME", "SYNOPSIS", "DESCRIPTION", "  Basic Usage", "  Advanced Usage", "OPTIONS"]

    Raises:
        Exception: If the JSON structure is invalid
    """
    import json

    if isinstance(json_data, dict):
        json_str = json.dumps(json_data)
    else:
        json_str = json_data

    return manj_ast.list_sections_py(json_str)


@mcp.tool()
def extract_man_section(json_data: dict | str, section_names: list[str]) -> str:
    """
    Extract specific sections from a man page and convert them to roff format.

    This tool is useful for extracting only relevant parts of a man page,
    such as just the OPTIONS section, or combining EXAMPLES with DESCRIPTION.
    The output is in roff format and can be piped to man or further processed.

    Args:
        json_data: Either a dictionary containing unist-format JSON structure,
                   or a JSON string from parse_man_to_json
        section_names: List of section/subsection names to extract
                      Section names are case-insensitive and whitespace-flexible
                      Examples: ["OPTIONS"], ["DESCRIPTION", "EXAMPLES"],
                               ["Basic Usage"] (for subsections)

    Returns:
        String containing roff format markup with only the specified sections

    Raises:
        Exception: If the JSON is invalid or no matching sections are found

    Examples:
        # Extract just the OPTIONS section
        extract_man_section(json_data, ["OPTIONS"])

        # Extract multiple sections
        extract_man_section(json_data, ["SYNOPSIS", "DESCRIPTION", "EXAMPLES"])

        # Extract a subsection
        extract_man_section(json_data, ["Basic Usage"])
    """
    import json

    if isinstance(json_data, dict):
        json_str = json.dumps(json_data)
    else:
        json_str = json_data

    return manj_ast.extract_section(json_str, section_names)
