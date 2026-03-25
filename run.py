#!/usr/bin/env python
"""Run the Stock Analysis Agent API server."""

import uvicorn

uvicorn.run(
    "src.api:app",
    host="0.0.0.0",
    port=8001,
    reload=False,
    log_level="info",
)
