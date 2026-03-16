"""
MCP Server configuration.
All values can be overridden via environment variables.
"""
import os

_HOST = os.environ.get("FUSION_HOST", "127.0.0.1")
_PORT = os.environ.get("FUSION_PORT", "5000")
BASE_URL = os.environ.get("FUSION_BASE_URL", f"http://{_HOST}:{_PORT}")

API_KEY = os.environ.get("FUSION_API_KEY", "")

ENDPOINTS = {
    "health":              f"{BASE_URL}/health",
    "test_connection":     f"{BASE_URL}/test_connection",
    "holes":               f"{BASE_URL}/holes",
    "witzenmann":          f"{BASE_URL}/Witzenmann",
    "spline":              f"{BASE_URL}/spline",
    "sweep":               f"{BASE_URL}/sweep",
    "undo":                f"{BASE_URL}/undo",
    "count_parameters":    f"{BASE_URL}/count_parameters",
    "list_parameters":     f"{BASE_URL}/list_parameters",
    "export_step":         f"{BASE_URL}/Export_STEP",
    "export_stl":          f"{BASE_URL}/Export_STL",
    "fillet_edges":        f"{BASE_URL}/fillet_edges",
    "chamfer_edges":       f"{BASE_URL}/chamfer_edges",
    "change_parameter":    f"{BASE_URL}/set_parameter",
    "draw_cylinder":       f"{BASE_URL}/draw_cylinder",
    "draw_box":            f"{BASE_URL}/Box",
    "shell_body":          f"{BASE_URL}/shell_body",
    "draw_lines":          f"{BASE_URL}/draw_lines",
    "extrude":             f"{BASE_URL}/extrude_last_sketch",
    "extrude_thin":        f"{BASE_URL}/extrude_thin",
    "cut_extrude":         f"{BASE_URL}/cut_extrude",
    "revolve":             f"{BASE_URL}/revolve",
    "arc":                 f"{BASE_URL}/arc",
    "draw_one_line":       f"{BASE_URL}/draw_one_line",
    "circular_pattern":    f"{BASE_URL}/circular_pattern",
    "rectangular_pattern": f"{BASE_URL}/rectangular_pattern",
    "ellipsie":            f"{BASE_URL}/ellipsis",
    "draw2Dcircle":        f"{BASE_URL}/create_circle",
    "loft":                f"{BASE_URL}/loft",
    "draw_sphere":         f"{BASE_URL}/sphere",
    "threaded":            f"{BASE_URL}/threaded",
    "delete_everything":   f"{BASE_URL}/delete_everything",
    "boolean_operation":   f"{BASE_URL}/boolean_operation",
    "draw_2d_rectangle":   f"{BASE_URL}/draw_2d_rectangle",
    "draw_text":           f"{BASE_URL}/draw_text",
    "move_body":           f"{BASE_URL}/move_body",
    "mirror_body":         f"{BASE_URL}/mirror_body",
    "list_bodies":         f"{BASE_URL}/list_bodies",
    "rename_body":         f"{BASE_URL}/rename_body",
    "measure_bounding_box":f"{BASE_URL}/measure_bounding_box",
}

HEADERS = {
    "Content-Type": "application/json",
    **({"X-API-Key": API_KEY} if API_KEY else {}),
}

REQUEST_TIMEOUT = int(os.environ.get("FUSION_REQUEST_TIMEOUT", "35"))
