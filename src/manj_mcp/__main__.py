#!/usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2026 sakakibara <sakakibara@organon>
#
# Distributed under terms of the MIT license.
from .app import mcp

mcp.run(transport="streamable-http")


# import uvicorn
# from starlette.applications import Starlette
# from starlette.routing import Route, Mount
# from .app import mcp
#
# app = Starlette(
#     routes=[
#         # Route("/health-check", health_check),
#         Route("/mcp", mcp.streamable_http_app())
#     ]
# )
#
#
# uvicorn.run(app, host="0.0.0.0", port=8080)
