# Cursor MCP Setup (MentraOS Docs)

This project uses a **project-scoped** MCP config so the MentraOS docs server is only active in this repo.

Config file: **`.cursor/mcp.json`** (in this project):

```json
{
  "mcpServers": {
    "mentraos-docs": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://docs.mentraglass.com/mcp"]
    }
  }
}
```

This enables the **MentraOS** MCP server for this project, which provides:

- **`search_mentra_os`** — Search the MentraOS knowledge base for documentation, code examples, API references, and guides. Use it when you need info about MentraOS, how features work, or implementation details. Results include titles and links to the docs.

After saving `mcp.json`, restart Cursor or reload the window so the MCP server is picked up.
