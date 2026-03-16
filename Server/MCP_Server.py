"""
MCP Server – bridges AI assistants (Claude, Copilot) to Fusion 360 via HTTP.
"""
import json
import logging

import requests
from dotenv import load_dotenv

load_dotenv()
import config  # must be AFTER load_dotenv so env vars are set

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Fusion",
    instructions="""You are a professional Fusion 360 CAD assistant specialized in mechanical and industrial design.
Answer only questions related to Fusion 360 CAD operations.

**Units (critical):**
- 1 unit = 1 cm = 10 mm
- All mm values must be divided by 10. Examples: 28.3 mm = 2.83, 5 mm = 0.5

**Planes and coordinates:**
- XY plane: x and y set position, z sets height offset
- XZ plane: x and z set position, y sets offset
- YZ plane: y and z set position, x sets offset

**Workflow rules:**
- After each tool call, pause briefly to verify the result before the next step.
- Before creating new geometry, call delete_all to clear the scene.
- For hollow bodies, prefer extrude_thin over shell_body.
- For sweep: create profile sketch first, then path sketch in the same plane, then call sweep.
- For loft: create all section sketches first, then call loft with the count.
- Boolean operations: first body drawn = target, second body drawn = tool.
- Circular pattern cannot be applied to holes (holes are not bodies).
- Depth for cut_extrude must be negative.

**DrawBox / DrawCylinder:**
- Coordinates given are always the center of the body.
""",
)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def send_request(endpoint: str, data: dict, timeout: float | None = None) -> dict:
    """Send a POST request to the Fusion 360 add-in with automatic retries."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            payload = json.dumps(data).encode()
            response = requests.post(
                endpoint,
                data=payload,
                headers=config.HEADERS,
                timeout=timeout or config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logging.error("Request failed attempt %d/%d: %s", attempt + 1, max_retries, exc)
            if attempt == max_retries - 1:
                raise
    return {}


def send_get(endpoint: str) -> dict:
    """Send a GET request to the Fusion 360 add-in."""
    response = requests.get(endpoint, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def health_check() -> dict:
    """Check if the Fusion 360 add-in is running and return body/sketch counts."""
    return send_get(config.ENDPOINTS["health"])


@mcp.tool()
def test_connection() -> dict:
    """Test connectivity to the Fusion 360 add-in."""
    return send_request(config.ENDPOINTS["test_connection"], {})


@mcp.tool()
def delete_all() -> dict:
    """Delete all bodies and sketches from the active design."""
    return send_request(config.ENDPOINTS["delete_everything"], {})


@mcp.tool()
def undo() -> dict:
    """Undo the last action in Fusion 360."""
    return send_request(config.ENDPOINTS["undo"], {})


@mcp.tool()
def count_parameters() -> dict:
    """Return the number of model parameters in the active design."""
    return send_get(config.ENDPOINTS["count_parameters"])


@mcp.tool()
def list_parameters() -> dict:
    """List all model parameters with names, values, units, and expressions."""
    return send_get(config.ENDPOINTS["list_parameters"])


@mcp.tool()
def change_parameter(name: str, value: str) -> dict:
    """Change the value of a named model parameter. value is an expression string e.g. '10 mm'."""
    return send_request(config.ENDPOINTS["change_parameter"], {"name": name, "value": value})


@mcp.tool()
def list_bodies() -> dict:
    """List all solid bodies in the active design with their index and name."""
    return send_request(config.ENDPOINTS["list_bodies"], {})


@mcp.tool()
def rename_body(old_name: str, new_name: str) -> dict:
    """Rename a body in the active design."""
    return send_request(config.ENDPOINTS["rename_body"], {"old_name": old_name, "new_name": new_name})


@mcp.tool()
def measure_bounding_box(body_index: int = 0) -> dict:
    """Return the axis-aligned bounding box of a body. Returns min/max XYZ and width/height/depth in cm."""
    return send_request(config.ENDPOINTS["measure_bounding_box"], {"body_index": body_index})


@mcp.tool()
def draw_box(height: float, width: float, depth: float, x: float, y: float, z: float, plane: str = "XY") -> dict:
    """
    Draw a rectangular box. Coordinates are the center of the box.
    depth is the extrusion height in the normal direction.
    plane: "XY" (default), "XZ", or "YZ".
    All units in cm (1 cm = 10 mm).
    """
    return send_request(
        config.ENDPOINTS["draw_box"],
        {"height": height, "width": width, "depth": depth, "x": x, "y": y, "z": z, "Plane": plane},
    )


@mcp.tool()
def draw_cylinder(radius: float, height: float, x: float, y: float, z: float, plane: str = "XY") -> dict:
    """Draw a cylinder. x,y,z is the center of the base circle. plane: XY, XZ, or YZ."""
    return send_request(
        config.ENDPOINTS["draw_cylinder"],
        {"radius": radius, "height": height, "x": x, "y": y, "z": z, "plane": plane},
    )


@mcp.tool()
def draw_2d_circle(radius: float, x: float, y: float, z: float, plane: str = "XY") -> dict:
    """
    Draw a 2D circle sketch (for use with extrude, sweep, loft).
    plane: XY (z=offset), XZ (y=offset), YZ (x=offset).
    """
    return send_request(
        config.ENDPOINTS["draw2Dcircle"],
        {"radius": radius, "x": x, "y": y, "z": z, "plane": plane},
    )


@mcp.tool()
def draw_lines(points: list, plane: str = "XY") -> dict:
    """Draw connected lines forming a closed profile. points = [[x,y,z], ...]. Last point connects to first."""
    return send_request(config.ENDPOINTS["draw_lines"], {"points": points, "plane": plane})


@mcp.tool()
def draw_one_line(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float, plane: str = "XY") -> dict:
    """Draw a single line segment in the last open sketch. Use after draw_arc to close profiles."""
    return send_request(
        config.ENDPOINTS["draw_one_line"],
        {"x1": x1, "y1": y1, "z1": z1, "x2": x2, "y2": y2, "z2": z2, "plane": plane},
    )


@mcp.tool()
def draw_2d_rectangle(x_1: float, y_1: float, z_1: float, x_2: float, y_2: float, z_2: float, plane: str = "XY") -> dict:
    """Draw a 2D rectangle sketch from corner (x_1,y_1,z_1) to corner (x_2,y_2,z_2). For loft/sweep use."""
    return send_request(
        config.ENDPOINTS["draw_2d_rectangle"],
        {"x_1": x_1, "y_1": y_1, "z_1": z_1, "x_2": x_2, "y_2": y_2, "z_2": z_2, "plane": plane},
    )


@mcp.tool()
def draw_arc(point1: list, point2: list, point3: list, plane: str = "XY") -> dict:
    """Draw an arc through three points. point1=start, point2=midpoint, point3=end."""
    return send_request(
        config.ENDPOINTS["arc"],
        {"point1": point1, "point2": point2, "point3": point3, "plane": plane},
    )


@mcp.tool()
def draw_spline(points: list, plane: str = "XY") -> dict:
    """Draw a fitted spline through the given points. points = [[x,y,z], ...]."""
    return send_request(config.ENDPOINTS["spline"], {"points": points, "plane": plane})


@mcp.tool()
def draw_ellipse(
    x_center: float,
    y_center: float,
    z_center: float,
    x_major: float,
    y_major: float,
    z_major: float,
    x_through: float,
    y_through: float,
    z_through: float,
    plane: str = "XY",
) -> dict:
    """Draw an ellipse defined by center point, major axis endpoint, and a through point."""
    return send_request(
        config.ENDPOINTS["ellipsie"],
        {
            "x_center": x_center,
            "y_center": y_center,
            "z_center": z_center,
            "x_major": x_major,
            "y_major": y_major,
            "z_major": z_major,
            "x_through": x_through,
            "y_through": y_through,
            "z_through": z_through,
            "plane": plane,
        },
    )


@mcp.tool()
def draw_text(
    text: str,
    plane: str,
    x_1: float,
    y_1: float,
    z_1: float,
    x_2: float,
    y_2: float,
    z_2: float,
    thickness: float,
    extrusion_value: float,
) -> dict:
    """Draw and extrude 3D text. x_1/y_1/z_1 = bottom-left corner, x_2/y_2/z_2 = top-right corner of text box."""
    return send_request(
        config.ENDPOINTS["draw_text"],
        {
            "text": text,
            "plane": plane,
            "x_1": x_1,
            "y_1": y_1,
            "z_1": z_1,
            "x_2": x_2,
            "y_2": y_2,
            "z_2": z_2,
            "thickness": thickness,
            "extrusion_value": extrusion_value,
        },
    )


@mcp.tool()
def extrude(value: float, taperangle: float = 0.0) -> dict:
    """Extrude the last sketch by value (cm). taperangle in degrees (0 = straight)."""
    return send_request(config.ENDPOINTS["extrude"], {"value": value, "taperangle": taperangle})


@mcp.tool()
def extrude_thin(thickness: float, distance: float) -> dict:
    """Create a thin-wall extrusion from the last sketch. Use this instead of shell for hollow bodies."""
    return send_request(config.ENDPOINTS["extrude_thin"], {"thickness": thickness, "distance": distance})


@mcp.tool()
def cut_extrude(depth: float) -> dict:
    """Cut-extrude from the last sketch. depth must be negative to cut into the body."""
    return send_request(config.ENDPOINTS["cut_extrude"], {"depth": depth})


@mcp.tool()
def revolve(angle: float) -> dict:
    """Revolve a profile around an axis. The user will be prompted in Fusion 360 to select the profile and axis."""
    return send_request(config.ENDPOINTS["revolve"], {"angle": angle})


@mcp.tool()
def sweep() -> dict:
    """Sweep: uses the second-to-last sketch as profile and the last sketch as path."""
    return send_request(config.ENDPOINTS["sweep"], {})


@mcp.tool()
def loft(sketchcount: int) -> dict:
    """Loft through the last N sketches. Create all section sketches before calling loft."""
    return send_request(config.ENDPOINTS["loft"], {"sketchcount": sketchcount})


@mcp.tool()
def shell_body(thickness: float, faceindex: int) -> dict:
    """Shell the first body, removing the face at faceindex. For a filleted box, faceindex >= 21."""
    return send_request(config.ENDPOINTS["shell_body"], {"thickness": thickness, "faceindex": faceindex})


@mcp.tool()
def fillet_edges(radius: float) -> dict:
    """Apply a fillet of given radius to all edges of all bodies in the design."""
    return send_request(config.ENDPOINTS["fillet_edges"], {"radius": radius})


@mcp.tool()
def chamfer_edges(distance: float) -> dict:
    """Apply a chamfer of given distance to all edges of all bodies in the design."""
    return send_request(config.ENDPOINTS["chamfer_edges"], {"distance": distance})


@mcp.tool()
def boolean_operation(operation: str) -> dict:
    """
    Perform a boolean operation between body[0] (target) and body[1] (tool).
    operation: "cut", "join", or "intersect".
    Draw target body first, then tool body.
    """
    return send_request(config.ENDPOINTS["boolean_operation"], {"operation": operation})


@mcp.tool()
def mirror_body(plane: str = "XY") -> dict:
    """Mirror the last body about a construction plane. plane: XY, XZ, or YZ."""
    return send_request(config.ENDPOINTS["mirror_body"], {"plane": plane})


@mcp.tool()
def circular_pattern(quantity: float, axis: str, plane: str) -> dict:
    """Distribute the last body in a circular pattern. axis: X/Y/Z. quantity = number of instances."""
    return send_request(config.ENDPOINTS["circular_pattern"], {"quantity": quantity, "axis": axis, "plane": plane})


@mcp.tool()
def rectangular_pattern(
    axis_one: str,
    axis_two: str,
    quantity_one: float,
    quantity_two: float,
    distance_one: float,
    distance_two: float,
    plane: str = "XY",
) -> dict:
    """Distribute the last body in a rectangular pattern along two axes."""
    return send_request(
        config.ENDPOINTS["rectangular_pattern"],
        {
            "axis_one": axis_one,
            "axis_two": axis_two,
            "quantity_one": quantity_one,
            "quantity_two": quantity_two,
            "distance_one": distance_one,
            "distance_two": distance_two,
            "plane": plane,
        },
    )


@mcp.tool()
def draw_holes(points: list, width: float, depth: float, faceindex: int = 0) -> dict:
    """
    Drill holes on a body face. points = [[x,y], ...] relative to face center.
    width = diameter (cm), depth = hole depth (cm), faceindex = face to drill on.
    For a cylinder top face: faceindex=1. For a box top face: faceindex=4.
    """
    return send_request(
        config.ENDPOINTS["holes"],
        {"points": points, "width": width, "depth": depth, "faceindex": faceindex},
    )


@mcp.tool()
def move_latest_body(x: float, y: float, z: float) -> dict:
    """Translate the most recently created body by (x, y, z) in cm."""
    return send_request(config.ENDPOINTS["move_body"], {"x": x, "y": y, "z": z})


@mcp.tool()
def export_step(name: str) -> dict:
    """Export the design as a STEP file. name = base filename (no extension). Saved to Desktop/Fusion_Exports/."""
    return send_request(config.ENDPOINTS["export_step"], {"name": name})


@mcp.tool()
def export_stl(name: str) -> dict:
    """Export the design as STL files. name = folder name. Saved to Desktop/Fusion_Exports/."""
    return send_request(config.ENDPOINTS["export_stl"], {"name": name})


@mcp.tool()
def create_thread(inside: bool, size_index: int) -> dict:
    """
    Add a thread feature to a cylindrical face selected by the user in Fusion 360.
    inside=True for internal thread, False for external.
    size_index: 0=1/4, 1=5/16, 2=3/8, 3=7/16, 4=1/2, 5=5/8, 6=3/4, 7=7/8,
                8=1, 9=1-1/8, 10=1-1/4, 11=1-3/8, 12=1-1/2 (up to 22).
    """
    return send_request(config.ENDPOINTS["threaded"], {"inside": inside, "allsizes": size_index})


@mcp.tool()
def draw_witzenmann_logo(scale: float = 1.0, z: float = 0.0) -> dict:
    """Draw the Witzenmann logo as extruded 3D geometry. scale adjusts size, z sets vertical offset."""
    return send_request(config.ENDPOINTS["witzenmann"], {"scale": scale, "z": z})


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def flange():
    return """
    STEP 1: Draw cylinder (e.g. radius=5, height=1, x=0, y=0, z=0, plane=XY)
    STEP 2: draw_holes - 6 holes in a circle pattern
            points: [[4,0],[2,3.46],[-2,3.46],[-4,0],[-2,-3.46],[2,-3.46]]
            depth > cylinder height (through-holes), faceindex=1
    STEP 3 (optional): draw_2d_circle radius=2 x=0 y=0 z=0 plane=XY, then cut_extrude depth=-2
    """


@mcp.prompt()
def vase():
    return """
    STEP 1: draw_2d_circle radius=2.5 z=0 plane=XY
    STEP 2: draw_2d_circle radius=1.5 z=4 plane=XY
    STEP 3: draw_2d_circle radius=3.0 z=8 plane=XY
    STEP 4: draw_2d_circle radius=2.0 z=12 plane=XY
    STEP 5: loft sketchcount=4
    STEP 6: shell_body thickness=0.3 faceindex=1
    """


@mcp.prompt()
def dna_helix():
    return """
    STRAND 1:
    STEP 1: draw_2d_circle radius=0.5 x=3 y=0 z=0 plane=XY
    STEP 2: draw_spline plane=XY points=[[3,0,0],[2.121,2.121,6.25],[0,3,12.5],[-2.121,2.121,18.75],[-3,0,25],[-2.121,-2.121,31.25],[0,-3,37.5],[2.121,-2.121,43.75],[3,0,50]]
    STEP 3: sweep
    STRAND 2:
    STEP 4: draw_2d_circle radius=0.5 x=-3 y=0 z=0 plane=XY
    STEP 5: draw_spline plane=XY points=[[-3,0,0],[-2.121,-2.121,6.25],[0,-3,12.5],[2.121,-2.121,18.75],[3,0,25],[2.121,2.121,31.25],[0,3,37.5],[-2.121,2.121,43.75],[-3,0,50]]
    STEP 6: sweep
    """


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--server_type", type=str, default="sse", choices=["sse", "stdio"])
    args = parser.parse_args()
    mcp.run(transport=args.server_type)
