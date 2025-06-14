# simple-browser-use

This repository is based of the Open-sourced [Browser Use](https://github.com/browser-use/browser-use)

## Overview

Simple browser use is not a complicated project, its just wrapping it with MCP server layer to then extract the screen shot from the Browser use agent to send SSE event back to a MCP client. It runs the MCP server in SSE transport mode.

## Running

Run the Docker image to start up the SSE MCP server, required Open AI API key (considering allowing to change the LLM to open router to allow changing models to experiment).

```
docker run --name simple-browser-use --rm --env-file .env -p8000:8000 ghcr.io/jckhoe/simple-browser-use:latest
```

---

`.env` just requires the value for `OPENAI_API_KEY`.
