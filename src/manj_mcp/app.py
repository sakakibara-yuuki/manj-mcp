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


# auth = TokenAuthBackend(token=["secret"])
mcp = FastMCP(
    "ManMCP",
    # auth=auth,
    json_response=True,
    host="0.0.0.0",
    port=8080,
)


client = meilisearch.Client(
    os.getenv("MEILI_HOST", "http://search:7700"), os.getenv("MEILI_MASTER_KEY")
)
index = client.index("man-pages")


# LLMに使わせるツール。
@mcp.tool()
def search_man_pages(query: str, limit: int = 10, offset: int = 0) -> dict:
    search_params: dict[str, int | str] = {"limit": limit, "offset": offset}
    return index.search(query, search_params)


# @man://diffman-git を読んで。のようにすると、読んでくれる。LLMに読ませるためのresource.
@mcp.resource("man://{command}")
def get_command_options(command: str):
    return index.search(command)


# # @greeting://fuga を読んで。のようにすると、読んでくれる。LLMに読ませるresource.
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
