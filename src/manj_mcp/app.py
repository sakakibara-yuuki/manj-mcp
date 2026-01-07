#!/usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2025 sakakibara <sakakibara@organon>
#
# Distributed under terms of the MIT license.

from mcp.server.fastmcp import FastMCP
# from mcp.server.fastmcp.auth import TokenAuthBackend

# auth = TokenAuthBackend(token=["secret"])
mcp = FastMCP(
    "SecretDemo",
    # auth=auth,
    json_response=True,
    port=8080,
)


# LLMに使わせるツール。
@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b

# @greeting://fuga を読んで。のようにすると、読んでくれる。LLMに読ませるresource.
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    return f"Hello {name}"


# LLMに送るprompt を作成する。これはその雛形。
# つまり、これはLLM前の仕組み。
@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    styles = {
        "friendly": "Please write a warm, friendly greeting",
        "formal": "Please write a formal, professional greeting",
        "casual": "Please write a casual, relaxed greeting",
    }

    return f"{styles.get(style, styles['friendly'])} for someone named {name}."
