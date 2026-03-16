# Fusion 360 MCP

A [Model Context Protocol](https://modelcontextprotocol.io) integration that lets AI assistants (Claude, GitHub Copilot) control Autodesk Fusion 360 via HTTP.

```
AI Client (Claude / Copilot)
        |  MCP protocol (stdio or SSE)
        v
  MCP_Server.py  (FastMCP)
        |  HTTP POST + X-API-Key header
        v
  MCP/MCP.py  (Fusion 360 Add-In HTTP server on 127.0.0.1:5000)
        |  Fusion 360 CustomEvent (thread-safe)
        v
  Fusion 360 API  (adsk.core / adsk.fusion)
```

## Repository Structure

```
.
├── MCP/
│   └── MCP.py          # Fusion 360 Add-In — runs an HTTP server on localhost:5000
├── Server/
│   ├── MCP_Server.py   # FastMCP server — exposes tools to AI assistants
│   ├── requirements.txt
│   └── tests/
├── Install_Addin.py    # Automated add-in installer
└── .env.example
```

---

## Prerequisites

- **Autodesk Fusion 360** (latest)
- **Python 3.11+**
- An AI client that supports MCP: [Claude Desktop](https://claude.ai/download) or VS Code with GitHub Copilot

---

## Installation

### 1. Install the Fusion 360 Add-In

**Automated (recommended):**

```bash
python Install_Addin.py
```

**Manual:**

Copy the `MCP/` folder to the Fusion 360 add-ins directory:

| Platform | Path |
|----------|------|
| Windows  | `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\` |
| macOS    | `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/` |

Then in Fusion 360: **Tools → Add-Ins → Scripts and Add-Ins → find MCP → Run**

---

### 2. Set Up the MCP Server

```bash
cd Server
pip install -r requirements.txt
cp ../.env.example .env
```

Edit `.env` and set `FUSION_API_KEY` to a strong random secret. To generate one:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### 3. Configure Your AI Client

#### Claude Desktop

Add the following to `claude_desktop_config.json`
(on Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "fusion360": {
      "command": "python",
      "args": ["path/to/Server/MCP_Server.py", "--server_type", "stdio"],
      "env": {
        "FUSION_API_KEY": "your-secret-key"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

#### VS Code with GitHub Copilot

Add the following to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "fusion360": {
      "type": "stdio",
      "command": "python",
      "args": ["Server/MCP_Server.py", "--server_type", "stdio"],
      "env": {
        "FUSION_API_KEY": "your-secret-key"
      }
    }
  }
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FUSION_API_KEY` | *(required)* | Shared secret sent as `X-API-Key` header on every request |
| `FUSION_HOST` | `127.0.0.1` | Add-in host address (loopback only) |
| `FUSION_PORT` | `5000` | Add-in HTTP port |
| `FUSION_REQUEST_TIMEOUT` | `35` | Request timeout in seconds |

---

## Available Tools

| Tool | Description |
|------|-------------|
| `health_check` | Check that the add-in is reachable |
| `test_connection` | Verify authentication and connectivity |
| `delete_all` | Remove all bodies from the active design |
| `undo` | Undo the last operation |
| `count_parameters` | Return the number of user parameters |
| `list_parameters` | List all user parameters and their values |
| `change_parameter` | Change a user parameter value |
| `list_bodies` | List all bodies in the active component |
| `rename_body` | Rename a body |
| `measure_bounding_box` | Return the bounding box dimensions of a body |
| `draw_box` | Create a box (rectangular prism) |
| `draw_cylinder` | Create a cylinder |
| `draw_2d_circle` | Sketch a circle on a plane |
| `draw_lines` | Sketch a polyline on a plane |
| `draw_one_line` | Sketch a single line segment |
| `draw_2d_rectangle` | Sketch a rectangle on a plane |
| `draw_arc` | Sketch an arc on a plane |
| `draw_spline` | Sketch a spline through a set of points |
| `draw_ellipse` | Sketch an ellipse on a plane |
| `draw_text` | Add sketch text on a plane |
| `extrude` | Extrude a sketch profile |
| `extrude_thin` | Extrude a sketch profile as a thin feature |
| `cut_extrude` | Extrude a profile as a cut |
| `revolve` | Revolve a profile around an axis |
| `sweep` | Sweep a profile along a path |
| `loft` | Loft between two or more profiles |
| `shell_body` | Apply a shell operation to a body |
| `fillet_edges` | Fillet selected edges |
| `chamfer_edges` | Chamfer selected edges |
| `boolean_operation` | Combine, cut, or intersect bodies |
| `mirror_body` | Mirror a body across a plane |
| `circular_pattern` | Create a circular pattern of a body |
| `rectangular_pattern` | Create a rectangular pattern of a body |
| `draw_holes` | Add holes to a body |
| `move_latest_body` | Translate or rotate the most recently created body |
| `export_step` | Export the design as a STEP file |
| `export_stl` | Export a body as an STL file |
| `create_thread` | Add a thread feature to a cylindrical face |
| `draw_witzenmann_logo` | Draw the Witzenmann logo as a sketch |

---

## Units

**1 unit = 1 cm (10 mm).** All dimension parameters must be provided in centimetres.

---

## Security

- The add-in binds exclusively to `127.0.0.1` — it is never exposed on the network.
- Every request must include a matching `X-API-Key` header; requests without a valid key are rejected with `401`.
- Export filenames are sanitized to prevent path traversal attacks.

---

## Running Tests

```bash
cd Server
pytest tests/ -v
```

---

## License

See [LICENSE](LICENSE).
