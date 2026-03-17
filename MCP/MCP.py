"""Fusion 360 MCP Add-In — HTTP server entry point."""
import adsk.core
import adsk.fusion
import traceback
import threading
import json
import queue
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

import config
import _geometry as geo  # Fusion 360 adds add-in dir to sys.path; absolute import required

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
app = None
ui = None
design = None
handlers = []
stopFlag = None
httpd = None
task_queue: queue.Queue = queue.Queue()
result_store: dict = {}
_TASK_TIMEOUT = 30.0
_INTERACTIVE_TIMEOUT = 120.0
myCustomEvent = "MCPTaskEvent"
customEvent = None


# ---------------------------------------------------------------------------
# Async task helpers
# ---------------------------------------------------------------------------
def _queue_task(task: tuple, timeout: float = _TASK_TIMEOUT) -> dict:
    """Put a task on the queue and block until it completes or times out."""
    task_id = str(uuid.uuid4())
    ev = threading.Event()
    result_store[task_id] = {"event": ev, "result": None}
    task_queue.put(task + (task_id,))
    if ev.wait(timeout):
        return result_store.pop(task_id, {}).get("result") or {
            "success": False, "error": {"code": "NO_RESULT"}
        }
    result_store.pop(task_id, None)
    return {"success": False, "error": {"code": "TIMEOUT",
            "message": f"Task did not complete within {timeout}s"}}


def _resolve(task_id: str, result: dict) -> None:
    """Store a result and wake the waiting HTTP thread."""
    if task_id in result_store:
        result_store[task_id]["result"] = result
        result_store[task_id]["event"].set()


# ---------------------------------------------------------------------------
# Fusion 360 custom-event machinery (required for thread-safety)
# ---------------------------------------------------------------------------
class TaskThread(threading.Thread):
    """Fires the Fusion custom event every 200 ms to drain the task queue."""
    def __init__(self, stopped: threading.Event):
        super().__init__()
        self.stopped = stopped

    def run(self):
        while not self.stopped.wait(0.2):
            try:
                app.fireCustomEvent(myCustomEvent, json.dumps({}))
            except Exception:
                break


class TaskEventHandler(adsk.core.CustomEventHandler):
    """Processes queued tasks on the Fusion main thread."""
    def __init__(self):
        super().__init__()

    def notify(self, args):
        if not design:
            return
        while not task_queue.empty():
            try:
                task = task_queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._process(task)
            except Exception as exc:
                try:
                    _resolve(task[-1], {
                        "success": False,
                        "error": {
                            "code": "TASK_ERROR",
                            "message": str(exc),
                            "detail": traceback.format_exc(),
                        },
                    })
                except Exception:
                    pass

    def _process(self, task):  # noqa: C901
        op = task[0]
        tid = task[-1]
        try:
            if op == "draw_box":
                r = geo.draw_box(design, task[1], task[2], task[3], task[4], task[5], task[6], task[7])
            elif op == "draw_cylinder":
                r = geo.draw_cylinder(design, task[1], task[2], task[3], task[4], task[5], task[6])
            elif op == "draw_circle":
                r = geo.draw_circle(design, task[1], task[2], task[3], task[4], task[5])
            elif op == "draw_lines":
                r = geo.draw_lines(design, task[1], task[2])
            elif op == "draw_one_line":
                r = geo.draw_one_line(design, task[1], task[2], task[3], task[4], task[5], task[6], task[7])
            elif op == "draw_2d_rect":
                r = geo.draw_2d_rect(design, task[1], task[2], task[3], task[4], task[5], task[6], task[7])
            elif op == "arc":
                r = geo.arc(design, task[1], task[2], task[3], task[4], task[5])
            elif op == "spline":
                r = geo.spline(design, task[1], task[2])
            elif op == "draw_ellipse":
                r = geo.draw_ellipse(design, *task[1:11])
            elif op == "draw_text":
                r = geo.draw_text(design, task[1], task[2], task[3], task[4], task[5],
                                  task[6], task[7], task[8], task[9], task[10])
            elif op == "extrude_last_sketch":
                r = geo.extrude_last_sketch(design, task[1], task[2])
            elif op == "extrude_thin":
                r = geo.extrude_thin(design, task[1], task[2])
            elif op == "cut_extrude":
                r = geo.cut_extrude(design, task[1])
            elif op == "revolve_profile":
                r = geo.revolve_profile(design, ui, task[1])
            elif op == "sweep":
                r = geo.sweep(design)
            elif op == "loft":
                r = geo.loft(design, task[1])
            elif op == "shell_body":
                r = geo.shell_body(design, task[1], task[2])
            elif op == "fillet_edges":
                r = geo.fillet_edges(design, task[1])
            elif op == "chamfer_edges":
                r = geo.chamfer_edges(design, task[1])
            elif op == "mirror_body":
                r = geo.mirror_body(design, task[1])
            elif op == "measure_bounding_box":
                r = geo.measure_bounding_box(design, task[1])
            elif op == "list_bodies":
                r = geo.list_bodies(design)
            elif op == "rename_body":
                r = geo.rename_body(design, task[1], task[2])
            elif op == "boolean_operation":
                r = geo.boolean_operation(design, task[1])
            elif op == "circular_pattern":
                r = geo.circular_pattern(design, task[1], task[2], task[3])
            elif op == "rect_pattern":
                r = geo.rect_pattern(design, task[1], task[2], task[3],
                                     task[4], task[5], task[6], task[7])
            elif op == "offsetplane":
                r = geo.offsetplane(design, task[1], task[2])
            elif op == "holes":
                r = geo.holes(design, task[1], task[2], task[3], task[4])
            elif op == "move_last_body":
                r = geo.move_last_body(design, task[1], task[2], task[3])
            elif op == "delete_all":
                r = geo.delete_all(design)
            elif op == "undo":
                r = geo.undo(app)
            elif op == "set_parameter":
                r = geo.set_parameter(design, task[1], task[2])
            elif op == "export_step":
                r = geo.export_as_step(design, task[1])
            elif op == "export_stl":
                r = geo.export_as_stl(design, task[1])
            elif op == "threaded":
                r = geo.create_thread(design, ui, task[1], task[2])
            elif op == "witzenmann":
                r = geo.draw_witzenmann(design, task[1], task[2])
            else:
                r = {"success": False, "error": {"code": "UNKNOWN_OP", "message": op}}
            _resolve(tid, {"success": True, "data": r})
        except Exception as exc:
            _resolve(tid, {
                "success": False,
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": str(exc),
                    "detail": traceback.format_exc(),
                },
            })


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # suppress default stdout logging  # noqa: A002
        pass

    def _auth(self) -> bool:
        if not config.API_KEY:
            return True
        return self.headers.get("X-API-Key", "") == config.API_KEY

    def _json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        cl = self.headers.get("Content-Length")
        if cl is None:
            return {}
        length = int(cl)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def do_GET(self):
        if not self._auth():
            self._json(401, {"success": False, "error": {"code": "UNAUTHORIZED"}})
            return
        if self.path == "/health":
            rc = design.rootComponent if design else None
            self._json(200, {
                "status": "ok",
                "body_count": rc.bRepBodies.count if rc else 0,
                "sketch_count": rc.sketches.count if rc else 0,
            })
            return
        if self.path == "/count_parameters":
            params = geo.get_model_parameters(design)
            self._json(200, {"success": True, "data": {"count": len(params)}})
        elif self.path == "/list_parameters":
            params = geo.get_model_parameters(design)
            self._json(200, {"success": True, "data": {"parameters": params}})
        else:
            self._json(404, {"success": False, "error": {"code": "NOT_FOUND"}})

    def do_POST(self):  # noqa: C901
        if not self._auth():
            self._json(401, {"success": False, "error": {"code": "UNAUTHORIZED"}})
            return
        try:
            d = self._read_body()
            p = self.path
            if p == "/test_connection":
                self._json(200, {"success": True, "message": "Connection OK"})
            elif p == "/undo":
                self._json(200, _queue_task(("undo",)))
            elif p == "/delete_everything":
                self._json(200, _queue_task(("delete_all",)))
            elif p == "/set_parameter":
                self._json(200, _queue_task(("set_parameter", d["name"], d["value"])))
            elif p == "/Box":
                self._json(200, _queue_task((
                    "draw_box",
                    float(d.get("height", 5)), float(d.get("width", 5)),
                    float(d.get("depth", 5)), float(d.get("x", 0)),
                    float(d.get("y", 0)), float(d.get("z", 0)),
                    d.get("Plane") or d.get("plane"),
                )))
            elif p == "/draw_cylinder":
                self._json(200, _queue_task((
                    "draw_cylinder",
                    float(d["radius"]), float(d["height"]),
                    float(d.get("x", 0)), float(d.get("y", 0)), float(d.get("z", 0)),
                    d.get("plane", "XY"),
                )))
            elif p == "/create_circle":
                self._json(200, _queue_task((
                    "draw_circle",
                    float(d.get("radius", 1)), float(d.get("x", 0)),
                    float(d.get("y", 0)), float(d.get("z", 0)),
                    d.get("plane", "XY"),
                )))
            elif p == "/draw_lines":
                self._json(200, _queue_task(("draw_lines", d.get("points", []), d.get("plane", "XY"))))
            elif p == "/draw_one_line":
                self._json(200, _queue_task((
                    "draw_one_line",
                    float(d.get("x1", 0)), float(d.get("y1", 0)), float(d.get("z1", 0)),
                    float(d.get("x2", 1)), float(d.get("y2", 1)), float(d.get("z2", 0)),
                    d.get("plane", "XY"),
                )))
            elif p == "/draw_2d_rectangle":
                self._json(200, _queue_task((
                    "draw_2d_rect",
                    float(d.get("x_1", 0)), float(d.get("y_1", 0)), float(d.get("z_1", 0)),
                    float(d.get("x_2", 1)), float(d.get("y_2", 1)), float(d.get("z_2", 0)),
                    d.get("plane", "XY"),
                )))
            elif p == "/arc":
                self._json(200, _queue_task((
                    "arc",
                    d.get("point1", [0, 0, 0]), d.get("point2", [1, 1, 0]),
                    d.get("point3", [2, 0, 0]), d.get("plane", "XY"),
                    bool(d.get("connect", False)),
                )))
            elif p == "/spline":
                self._json(200, _queue_task(("spline", d.get("points", []), d.get("plane", "XY"))))
            elif p == "/ellipsis":
                self._json(200, _queue_task((
                    "draw_ellipse",
                    float(d.get("x_center", 0)), float(d.get("y_center", 0)), float(d.get("z_center", 0)),
                    float(d.get("x_major", 5)), float(d.get("y_major", 0)), float(d.get("z_major", 0)),
                    float(d.get("x_through", 0)), float(d.get("y_through", 3)), float(d.get("z_through", 0)),
                    d.get("plane", "XY"),
                )))
            elif p == "/draw_text":
                self._json(200, _queue_task((
                    "draw_text",
                    str(d.get("text", "Hello")), float(d.get("thickness", 0.5)),
                    float(d.get("x_1", 0)), float(d.get("y_1", 0)), float(d.get("z_1", 0)),
                    float(d.get("x_2", 10)), float(d.get("y_2", 4)), float(d.get("z_2", 0)),
                    float(d.get("extrusion_value", 1.0)), d.get("plane", "XY"),
                )))
            elif p == "/extrude_last_sketch":
                self._json(200, _queue_task((
                    "extrude_last_sketch",
                    float(d.get("value", 1.0)), float(d.get("taperangle", 0)),
                )))
            elif p == "/extrude_thin":
                self._json(200, _queue_task((
                    "extrude_thin", float(d.get("thickness", 0.5)), float(d.get("distance", 1.0)),
                )))
            elif p == "/cut_extrude":
                self._json(200, _queue_task(("cut_extrude", float(d.get("depth", -1.0)))))
            elif p == "/revolve":
                self._json(200, _queue_task(
                    ("revolve_profile", float(d.get("angle", 360))), _INTERACTIVE_TIMEOUT
                ))
            elif p == "/sweep":
                self._json(200, _queue_task(("sweep",)))
            elif p == "/loft":
                self._json(200, _queue_task(("loft", int(d.get("sketchcount", 2)))))
            elif p == "/shell_body":
                self._json(200, _queue_task((
                    "shell_body", float(d.get("thickness", 0.5)), int(d.get("faceindex", 0)),
                )))
            elif p == "/fillet_edges":
                self._json(200, _queue_task(("fillet_edges", float(d.get("radius", 0.3)))))
            elif p == "/chamfer_edges":
                self._json(200, _queue_task(("chamfer_edges", float(d.get("distance", 0.3)))))
            elif p == "/boolean_operation":
                self._json(200, _queue_task(("boolean_operation", d.get("operation", "join"))))
            elif p == "/mirror_body":
                self._json(200, _queue_task(("mirror_body", d.get("plane", "XY"))))
            elif p == "/circular_pattern":
                self._json(200, _queue_task((
                    "circular_pattern",
                    float(d.get("quantity", 2)), str(d.get("axis", "Z")), str(d.get("plane", "XY")),
                )))
            elif p == "/rectangular_pattern":
                self._json(200, _queue_task((
                    "rect_pattern",
                    str(d.get("axis_one", "X")), str(d.get("axis_two", "Y")),
                    float(d.get("quantity_one", 2)), float(d.get("quantity_two", 2)),
                    float(d.get("distance_one", 5)), float(d.get("distance_two", 5)),
                    str(d.get("plane", "XY")),
                )))
            elif p == "/offsetplane":
                self._json(200, _queue_task((
                    "offsetplane", float(d.get("offset", 0)), d.get("plane", "XY"),
                )))
            elif p == "/holes":
                self._json(200, _queue_task((
                    "holes",
                    d.get("points", [[0, 0]]), float(d.get("width", 1.0)),
                    float(d.get("depth", 1.0)), int(d.get("faceindex", 0)),
                )))
            elif p == "/move_body":
                self._json(200, _queue_task((
                    "move_last_body",
                    float(d.get("x", 0)), float(d.get("y", 0)), float(d.get("z", 0)),
                )))
            elif p == "/measure_bounding_box":
                self._json(200, _queue_task(("measure_bounding_box", int(d.get("body_index", 0)))))
            elif p == "/list_bodies":
                self._json(200, _queue_task(("list_bodies",)))
            elif p == "/rename_body":
                self._json(200, _queue_task(("rename_body", str(d["old_name"]), str(d["new_name"]))))
            elif p == "/Export_STEP":
                self._json(200, _queue_task(("export_step", str(d.get("name", "export")))))
            elif p == "/Export_STL":
                self._json(200, _queue_task(("export_stl", str(d.get("name", "export")))))
            elif p == "/threaded":
                self._json(200, _queue_task(
                    ("threaded", bool(d.get("inside", True)), int(d.get("allsizes", 0))),
                    _INTERACTIVE_TIMEOUT,
                ))
            elif p == "/Witzenmann":
                self._json(200, _queue_task((
                    "witzenmann", float(d.get("scale", 1.0)), float(d.get("z", 0)),
                )))
            else:
                self._json(404, {"success": False, "error": {"code": "NOT_FOUND", "message": p}})
        except Exception as exc:
            self._json(500, {
                "success": False,
                "error": {"code": "HANDLER_ERROR", "message": str(exc), "detail": traceback.format_exc()},
            })


# ---------------------------------------------------------------------------
# Server thread and add-in lifecycle
# ---------------------------------------------------------------------------
def run_server():
    global httpd
    httpd = HTTPServer((config.HOST, config.PORT), Handler)
    httpd.serve_forever()


def run(context):
    global app, ui, design, handlers, stopFlag, customEvent
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            ui.messageBox("No active design found. Open a design before starting the add-in.")
            return
        customEvent = app.registerCustomEvent(myCustomEvent)
        handler = TaskEventHandler()
        customEvent.add(handler)
        handlers.append(handler)
        stopFlag = threading.Event()
        t = TaskThread(stopFlag)
        t.daemon = True
        t.start()
        threading.Thread(target=run_server, daemon=True).start()
        ui.messageBox(f"Fusion MCP Add-In started on {config.HOST}:{config.PORT}")
    except Exception:
        try:
            ui.messageBox(f"Add-in error:\n{traceback.format_exc()}")
        except Exception:
            pass


def stop(context):
    global stopFlag, httpd, handlers, app, customEvent
    if stopFlag:
        stopFlag.set()
    for h in handlers:
        try:
            if customEvent:
                customEvent.remove(h)
        except Exception:
            pass
    handlers.clear()
    # Drain the task queue so no new tasks start
    while not task_queue.empty():
        try:
            task_queue.get_nowait()
        except Exception:
            break
    # Unblock any HTTP threads blocked in _queue_task waiting for a result
    for task_id in list(result_store.keys()):
        _resolve(task_id, {
            "success": False,
            "error": {"code": "SHUTDOWN", "message": "Add-in is shutting down"},
        })
    if httpd:
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass
        httpd = None
    try:
        adsk.core.Application.get().userInterface.messageBox("Fusion MCP Add-In stopped.")
    except Exception:
        pass
