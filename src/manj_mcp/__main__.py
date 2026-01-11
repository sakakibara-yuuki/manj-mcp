#!/usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2026 sakakibara <sakakibara@organon>
#
# Distributed under terms of the MIT license.
from .app import mcp

mcp.run(transport="streamable-http")
