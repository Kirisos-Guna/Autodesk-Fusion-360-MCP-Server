"""Fusion 360 geometry helper functions. All functions raise on failure."""
import adsk.core
import adsk.fusion
import math
import os
import re


def _pick_plane(design, plane: str):
    rc = design.rootComponent
    if plane == "XZ":
        return rc.xZConstructionPlane
    if plane == "YZ":
        return rc.yZConstructionPlane
    return rc.xYConstructionPlane


def _offset_plane(design, base_plane, offset: float):
    rc = design.rootComponent
    planes = rc.constructionPlanes
    inp = planes.createInput()
    inp.setByOffset(base_plane, adsk.core.ValueInput.createByReal(offset))
    return planes.add(inp)


def draw_box(design, height, width, depth, x, y, z, plane=None):
    """Draw a box (width x height extruded by depth) centred at (x,y). z offsets the sketch plane."""
    rc = design.rootComponent
    base = _pick_plane(design, plane or "XY")
    sketch_plane = _offset_plane(design, base, z) if z != 0 else base
    sketch = rc.sketches.add(sketch_plane)
    sketch.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(x, y, 0),
        adsk.core.Point3D.create(x + width / 2, y + height / 2, 0),
    )
    prof = sketch.profiles.item(0)
    ext = rc.features.extrudeFeatures
    inp = ext.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(depth))
    ext.add(inp)
    return {"body_count": rc.bRepBodies.count}


def draw_cylinder(design, radius, height, x, y, z, plane="XY"):
    """Draw a cylinder of given radius and height with base circle centred at (x,y,z)."""
    rc = design.rootComponent
    sketch = rc.sketches.add(_pick_plane(design, plane))
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(x, y, z), radius
    )
    prof = sketch.profiles.item(0)
    ext = rc.features.extrudeFeatures
    inp = ext.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(height))
    ext.add(inp)
    return {"body_count": rc.bRepBodies.count}


def draw_circle(design, radius, x, y, z, plane="XY"):
    """Draw a 2-D circle sketch. The offset coordinate is used to offset the plane."""
    rc = design.rootComponent
    base = _pick_plane(design, plane)
    if plane == "XZ":
        offset = y
        cx, cy = x, z
    elif plane == "YZ":
        offset = x
        cx, cy = y, z
    else:
        offset = z
        cx, cy = x, y
    sketch_plane = _offset_plane(design, base, offset) if offset != 0 else base
    sketch = rc.sketches.add(sketch_plane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(cx, cy, 0), radius
    )
    return {"sketch_count": rc.sketches.count}


def draw_lines(design, points, plane="XY"):
    """Draw a closed polyline through the given points on the specified plane."""
    rc = design.rootComponent
    sketch = rc.sketches.add(_pick_plane(design, plane))
    lines = sketch.sketchCurves.sketchLines
    for i in range(len(points) - 1):
        lines.addByTwoPoints(
            adsk.core.Point3D.create(points[i][0], points[i][1], 0),
            adsk.core.Point3D.create(points[i + 1][0], points[i + 1][1], 0),
        )
    lines.addByTwoPoints(
        adsk.core.Point3D.create(points[-1][0], points[-1][1], 0),
        adsk.core.Point3D.create(points[0][0], points[0][1], 0),
    )
    return {"line_count": sketch.sketchCurves.count}


def draw_one_line(design, x1, y1, z1, x2, y2, z2, plane="XY"):
    """Add a single line to the most recent sketch (used after arc to close profiles)."""
    rc = design.rootComponent
    sketch = rc.sketches.item(rc.sketches.count - 1)
    sketch.sketchCurves.sketchLines.addByTwoPoints(
        adsk.core.Point3D.create(x1, y1, 0),
        adsk.core.Point3D.create(x2, y2, 0),
    )
    return {"success": True}


def draw_2d_rect(design, x_1, y_1, z_1, x_2, y_2, z_2, plane="XY"):
    """Draw a 2-D rectangle from corner (x_1,y_1,z_1) to (x_2,y_2,z_2)."""
    rc = design.rootComponent
    base = _pick_plane(design, plane)
    if plane == "XZ":
        offset = y_1 if y_1 != 0 or y_2 != 0 else 0
    elif plane == "YZ":
        offset = x_1 if x_1 != 0 or x_2 != 0 else 0
    else:
        offset = z_1 if z_1 != 0 or z_2 != 0 else 0
    sketch_plane = _offset_plane(design, base, offset) if offset != 0 else base
    sketch = rc.sketches.add(sketch_plane)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(x_1, y_1, z_1),
        adsk.core.Point3D.create(x_2, y_2, z_2),
    )
    return {"success": True}


def arc(design, point1, point2, point3, plane="XY", connect=False):
    """Draw a three-point arc. If connect=True also draws a closing line."""
    rc = design.rootComponent
    sketch = rc.sketches.add(_pick_plane(design, plane))
    p1 = adsk.core.Point3D.create(point1[0], point1[1], point1[2])
    p2 = adsk.core.Point3D.create(point2[0], point2[1], point2[2])
    p3 = adsk.core.Point3D.create(point3[0], point3[1], point3[2])
    sketch.sketchCurves.sketchArcs.addByThreePoints(p1, p2, p3)
    if connect:
        sketch.sketchCurves.sketchLines.addByTwoPoints(p1, p3)
    return {"success": True}


def spline(design, points, plane="XY"):
    """Draw a fitted spline through the given 3-D points."""
    rc = design.rootComponent
    sketch = rc.sketches.add(_pick_plane(design, plane))
    col = adsk.core.ObjectCollection.create()
    for p in points:
        col.add(adsk.core.Point3D.create(p[0], p[1], p[2]))
    sketch.sketchCurves.sketchFittedSplines.add(col)
    return {"success": True}


def draw_ellipse(design, x_center, y_center, z_center,
                 x_major, y_major, z_major,
                 x_through, y_through, z_through, plane="XY"):
    """Draw an ellipse defined by centre, major-axis endpoint, and a through point."""
    rc = design.rootComponent
    sketch = rc.sketches.add(_pick_plane(design, plane))
    sketch.sketchCurves.sketchEllipses.add(
        adsk.core.Point3D.create(float(x_center), float(y_center), float(z_center)),
        adsk.core.Point3D.create(float(x_major), float(y_major), float(z_major)),
        adsk.core.Point3D.create(float(x_through), float(y_through), float(z_through)),
    )
    return {"success": True}


def draw_text(design, text, thickness, x_1, y_1, z_1, x_2, y_2, z_2, extrusion_value, plane="XY"):
    """Draw and extrude 3-D text on the specified plane."""
    rc = design.rootComponent
    sketch = rc.sketches.add(_pick_plane(design, plane))
    inp = sketch.sketchTexts.createInput2(str(text), thickness)
    inp.setAsMultiLine(
        adsk.core.Point3D.create(x_1, y_1, z_1),
        adsk.core.Point3D.create(x_2, y_2, z_2),
        adsk.core.HorizontalAlignments.LeftHorizontalAlignment,
        adsk.core.VerticalAlignments.TopVerticalAlignment,
        0,
    )
    sktext = sketch.sketchTexts.add(inp)
    ext = rc.features.extrudeFeatures
    ei = ext.createInput(sktext, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(extrusion_value))
    ei.isSolid = True
    ext.add(ei)
    return {"body_count": rc.bRepBodies.count}


def extrude_last_sketch(design, value, taperangle=0.0):
    """Extrude the last sketch profile by value (cm). Optional taper angle in degrees."""
    rc = design.rootComponent
    sketch = rc.sketches.item(rc.sketches.count - 1)
    prof = sketch.profiles.item(0)
    ext = rc.features.extrudeFeatures
    inp = ext.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    dist = adsk.core.ValueInput.createByReal(value)
    if taperangle != 0:
        taper = adsk.core.ValueInput.createByString(f"{taperangle} deg")
        extent = adsk.fusion.DistanceExtentDefinition.create(dist)
        inp.setOneSideExtent(extent, adsk.fusion.ExtentDirections.PositiveExtentDirection, taper)
    else:
        inp.setDistanceExtent(False, dist)
    ext.add(inp)
    return {"body_count": rc.bRepBodies.count}


def extrude_thin(design, thickness, distance):
    """Extrude the last sketch profile as a thin wall."""
    rc = design.rootComponent
    prof = rc.sketches.item(rc.sketches.count - 1).profiles.item(0)
    ext = rc.features.extrudeFeatures
    inp = ext.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setThinExtrude(
        adsk.fusion.ThinExtrudeWallLocation.Center,
        adsk.core.ValueInput.createByReal(thickness),
    )
    inp.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(distance)),
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    ext.add(inp)
    return {"body_count": rc.bRepBodies.count}


def cut_extrude(design, depth):
    """Cut-extrude from the last sketch. depth should be negative."""
    rc = design.rootComponent
    sketch = rc.sketches.item(rc.sketches.count - 1)
    prof = sketch.profiles.item(0)
    ext = rc.features.extrudeFeatures
    inp = ext.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(depth))
    ext.add(inp)
    return {"success": True}


def revolve_profile(design, ui, angle=360):
    """Revolve a profile (user selects profile and axis in Fusion 360 UI)."""
    ui.messageBox("Select a profile to revolve.")
    profile = ui.selectEntity("Select a profile to revolve.", "Profiles").entity
    ui.messageBox("Select sketch line for axis.")
    axis = ui.selectEntity("Select sketch line for axis.", "SketchLines").entity
    rc = design.rootComponent
    inp = rc.features.revolveFeatures.createInput(
        profile, axis, adsk.fusion.FeatureOperations.NewComponentFeatureOperation
    )
    inp.setAngleExtent(False, adsk.core.ValueInput.createByString(f"{angle} deg"))
    rc.features.revolveFeatures.add(inp)
    return {"body_count": rc.bRepBodies.count}


def sweep(design):
    """Sweep: second-to-last sketch = profile, last sketch = path."""
    rc = design.rootComponent
    sketches = rc.sketches
    prof = sketches.item(sketches.count - 2).profiles.item(0)
    path_sketch = sketches.item(sketches.count - 1)
    curves = adsk.core.ObjectCollection.create()
    for i in range(path_sketch.sketchCurves.count):
        curves.add(path_sketch.sketchCurves.item(i))
    path = adsk.fusion.Path.create(curves, 0)
    inp = rc.features.sweepFeatures.createInput(
        prof, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    rc.features.sweepFeatures.add(inp)
    return {"body_count": rc.bRepBodies.count}


def loft(design, sketchcount):
    """Loft through the last N sketch profiles."""
    rc = design.rootComponent
    sketches = rc.sketches
    lf = rc.features.loftFeatures
    inp = lf.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    for i in range(sketchcount):
        sk = sketches.item(sketches.count - 1 - i)
        inp.loftSections.add(sk.profiles.item(0))
    inp.isSolid = True
    inp.isClosed = False
    inp.isTangentEdgesMerged = True
    lf.add(inp)
    return {"body_count": rc.bRepBodies.count}


def shell_body(design, thickness=0.5, faceindex=0):
    """Shell the first body by removing the face at faceindex."""
    rc = design.rootComponent
    body = rc.bRepBodies.item(0)
    entities = adsk.core.ObjectCollection.create()
    entities.add(body.faces.item(faceindex))
    inp = rc.features.shellFeatures.createInput(entities, False)
    inp.insideThickness = adsk.core.ValueInput.createByReal(thickness)
    inp.shellType = adsk.fusion.ShellTypes.SharpOffsetShellType
    rc.features.shellFeatures.add(inp)
    return {"success": True}


def fillet_edges(design, radius=0.3):
    """Apply a constant-radius fillet to all edges of all bodies."""
    rc = design.rootComponent
    col = adsk.core.ObjectCollection.create()
    for bi in range(rc.bRepBodies.count):
        body = rc.bRepBodies.item(bi)
        for ei in range(body.edges.count):
            col.add(body.edges.item(ei))
    fillets = rc.features.filletFeatures
    inp = fillets.createInput()
    inp.isRollingBallCorner = True
    es = inp.edgeSetInputs.addConstantRadiusEdgeSet(
        col, adsk.core.ValueInput.createByReal(radius), True
    )
    es.continuity = adsk.fusion.SurfaceContinuityTypes.TangentSurfaceContinuityType
    fillets.add(inp)
    return {"success": True}


def chamfer_edges(design, distance=0.3):
    """Apply an equal-distance chamfer to all edges of all bodies."""
    rc = design.rootComponent
    col = adsk.core.ObjectCollection.create()
    for bi in range(rc.bRepBodies.count):
        body = rc.bRepBodies.item(bi)
        for ei in range(body.edges.count):
            col.add(body.edges.item(ei))
    chamfers = rc.features.chamferFeatures
    inp = chamfers.createInput(col, True)
    inp.setToEqualDistance(adsk.core.ValueInput.createByReal(distance))
    chamfers.add(inp)
    return {"success": True}


def mirror_body(design, plane="XY"):
    """Mirror the last body about a construction plane."""
    rc = design.rootComponent
    body = rc.bRepBodies.item(rc.bRepBodies.count - 1)
    col = adsk.core.ObjectCollection.create()
    col.add(body)
    mirror_plane = _pick_plane(design, plane)
    inp = rc.features.mirrorFeatures.createInput(col, mirror_plane)
    rc.features.mirrorFeatures.add(inp)
    return {"body_count": rc.bRepBodies.count}


def measure_bounding_box(design, body_index=0):
    """Return the axis-aligned bounding box of the body at body_index."""
    rc = design.rootComponent
    body = rc.bRepBodies.item(body_index)
    bb = body.boundingBox
    mn, mx = bb.minPoint, bb.maxPoint
    return {
        "min_x": mn.x, "min_y": mn.y, "min_z": mn.z,
        "max_x": mx.x, "max_y": mx.y, "max_z": mx.z,
        "width": mx.x - mn.x,
        "height": mx.y - mn.y,
        "depth": mx.z - mn.z,
    }


def list_bodies(design):
    """Return a list of all solid bodies with index and name."""
    rc = design.rootComponent
    return {
        "bodies": [
            {"index": i, "name": rc.bRepBodies.item(i).name}
            for i in range(rc.bRepBodies.count)
        ]
    }


def rename_body(design, old_name, new_name):
    """Rename a body identified by old_name."""
    rc = design.rootComponent
    body = rc.bRepBodies.itemByName(old_name)
    if body is None:
        raise ValueError(f"Body '{old_name}' not found.")
    body.name = new_name
    return {"success": True, "new_name": new_name}


def boolean_operation(design, op):
    """Combine body[0] (target) with body[1] (tool). op: 'cut', 'join', or 'intersect'."""
    rc = design.rootComponent
    bodies = rc.bRepBodies
    target = bodies.item(0)
    tool = bodies.item(1)
    tools_col = adsk.core.ObjectCollection.create()
    tools_col.add(tool)
    inp = rc.features.combineFeatures.createInput(target, tools_col)
    inp.isNewComponent = False
    inp.isKeepToolBodies = False
    ops = {
        "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
        "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
        "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
    }
    inp.operation = ops[op]
    rc.features.combineFeatures.add(inp)
    return {"body_count": rc.bRepBodies.count}


def circular_pattern(design, quantity, axis, plane):
    """Create a circular pattern of the last body."""
    rc = design.rootComponent
    body = rc.bRepBodies.item(rc.bRepBodies.count - 1)
    col = adsk.core.ObjectCollection.create()
    col.add(body)
    axes = {"X": rc.xConstructionAxis, "Y": rc.yConstructionAxis, "Z": rc.zConstructionAxis}
    inp = rc.features.circularPatternFeatures.createInput(col, axes[axis])
    inp.quantity = adsk.core.ValueInput.createByReal(quantity)
    inp.totalAngle = adsk.core.ValueInput.createByString("360 deg")
    inp.isSymmetric = False
    rc.features.circularPatternFeatures.add(inp)
    return {"success": True}


def rect_pattern(design, axis_one, axis_two, quantity_one, quantity_two,
                 distance_one, distance_two, plane="XY"):
    """Create a rectangular pattern of the last body along two axes."""
    rc = design.rootComponent
    body = rc.bRepBodies.item(rc.bRepBodies.count - 1)
    col = adsk.core.ObjectCollection.create()
    col.add(body)
    axes = {"X": rc.xConstructionAxis, "Y": rc.yConstructionAxis, "Z": rc.zConstructionAxis}
    feats = rc.features.rectangularPatternFeatures
    inp = feats.createInput(
        col, axes[axis_one],
        adsk.core.ValueInput.createByString(str(quantity_one)),
        adsk.core.ValueInput.createByString(str(distance_one)),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType,
    )
    inp.setDirectionTwo(
        axes[axis_two],
        adsk.core.ValueInput.createByString(str(quantity_two)),
        adsk.core.ValueInput.createByString(str(distance_two)),
    )
    feats.add(inp)
    return {"success": True}


def offsetplane(design, offset, plane="XY"):
    """Create a new offset construction plane."""
    rc = design.rootComponent
    base = _pick_plane(design, plane)
    _offset_plane(design, base, offset)
    return {"success": True}


def holes(design, points, width=1.0, distance=1.0, faceindex=0):
    """Drill simple holes on the specified face of the last body."""
    rc = design.rootComponent
    body = rc.bRepBodies.item(rc.bRepBodies.count - 1)
    face = body.faces.item(faceindex)
    sk = rc.sketches.add(face)
    hole_feats = rc.features.holeFeatures
    for pt in points:
        hp = sk.sketchPoints.add(adsk.core.Point3D.create(pt[0], pt[1], 0))
        inp = hole_feats.createSimpleInput(adsk.core.ValueInput.createByReal(width))
        inp.tipAngle = adsk.core.ValueInput.createByString("180 deg")
        inp.setPositionBySketchPoint(hp)
        inp.setDistanceExtent(adsk.core.ValueInput.createByReal(distance))
        hole_feats.add(inp)
    return {"hole_count": len(points)}


def move_last_body(design, x, y, z):
    """Translate the last body by vector (x, y, z)."""
    rc = design.rootComponent
    body = rc.bRepBodies.item(rc.bRepBodies.count - 1)
    col = adsk.core.ObjectCollection.create()
    col.add(body)
    t = adsk.core.Matrix3D.create()
    t.translation = adsk.core.Vector3D.create(x, y, z)
    inp = rc.features.moveFeatures.createInput2(col)
    inp.defineAsFreeMove(t)
    rc.features.moveFeatures.add(inp)
    return {"success": True}


def delete_all(design):
    """Remove all solid bodies from the design."""
    rc = design.rootComponent
    remove = rc.features.removeFeatures
    for i in range(rc.bRepBodies.count - 1, -1, -1):
        remove.add(rc.bRepBodies.item(i))
    return {"success": True}


def undo(app):
    """Undo the last Fusion 360 action."""
    app.userInterface.commandDefinitions.itemById("UndoCommand").execute()
    return {"success": True}


def set_parameter(design, name, value):
    """Set a model parameter by name."""
    param = design.allParameters.itemByName(name)
    if param is None:
        raise ValueError(f"Parameter '{name}' not found.")
    param.expression = value
    return {"name": name, "value": value}


def get_model_parameters(design):
    """Return a list of model parameters (non-user-defined)."""
    user = design.userParameters
    result = []
    for p in design.allParameters:
        if all(user.item(i) != p for i in range(user.count)):
            try:
                val = str(p.value)
            except Exception:
                val = ""
            result.append({
                "name": str(p.name),
                "value": val,
                "unit": str(p.unit),
                "expression": str(p.expression) if p.expression else "",
            })
    return result


def export_as_step(design, name):
    """Export the design as a STEP file to Desktop/Fusion_Exports/<name>/."""
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", name)
    desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    out_dir = os.path.join(desktop, "Fusion_Exports", safe)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{safe}.step")
    opts = design.exportManager.createSTEPExportOptions(path)
    if not design.exportManager.execute(opts):
        raise RuntimeError("STEP export failed.")
    return {"path": path}


def export_as_stl(design, name):
    """Export all bodies as STL files to Desktop/Fusion_Exports/<name>/."""
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", name)
    desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    out_dir = os.path.join(desktop, "Fusion_Exports", safe)
    os.makedirs(out_dir, exist_ok=True)
    mgr = design.exportManager
    rc = design.rootComponent
    for i in range(rc.bRepBodies.count):
        body = rc.bRepBodies.item(i)
        body_name = re.sub(r"[^A-Za-z0-9_\-]", "_", body.name)
        path = os.path.join(out_dir, body_name)
        opts = mgr.createSTLExportOptions(body, path)
        opts.sendToPrintUtility = False
        mgr.execute(opts)
    return {"path": out_dir}


def create_thread(design, ui, inside, sizes):
    """Add a thread to a user-selected cylindrical face."""
    ui.messageBox("Select a face for threading.")
    face = ui.selectEntity("Select a face for threading.", "Faces").entity
    faces = adsk.core.ObjectCollection.create()
    faces.add(face)
    tf = design.rootComponent.features.threadFeatures
    query = tf.threadDataQuery
    thread_type = query.allThreadTypes[0]
    thread_size = query.allSizes(thread_type)[sizes]
    designation = query.allDesignations(thread_type, thread_size)[0]
    cls = query.allClasses(False, thread_type, designation)[0]
    info = tf.createThreadInfo(inside, thread_type, designation, cls)
    inp = tf.createInput(faces, info)
    inp.isFullLength = True
    tf.add(inp)
    return {"success": True}


def draw_witzenmann(design, scaling, z):
    """Draw the Witzenmann logo as extruded geometry."""
    rc = design.rootComponent
    sketch = rc.sketches.add(rc.xYConstructionPlane)
    points1 = [
        (8.283, 10.475), (8.283, 6.471), (-0.126, 6.471), (8.283, 2.691),
        (8.283, -1.235), (-0.496, -1.246), (8.283, -5.715), (8.283, -9.996),
        (-8.862, -1.247), (-8.859, 2.69), (-0.639, 2.69), (-8.859, 6.409),
        (-8.859, 10.459),
    ]
    pts1 = [(x * scaling, y * scaling, z) for x, y in points1]
    lines = sketch.sketchCurves.sketchLines
    for i in range(len(pts1) - 1):
        lines.addByTwoPoints(
            adsk.core.Point3D.create(*pts1[i]),
            adsk.core.Point3D.create(*pts1[i + 1]),
        )
    lines.addByTwoPoints(
        adsk.core.Point3D.create(*pts1[-1]),
        adsk.core.Point3D.create(*pts1[0]),
    )
    points2 = [(-3.391, -5.989), (5.062, -10.141), (-8.859, -10.141), (-8.859, -5.989)]
    pts2 = [(x * scaling, y * scaling, z) for x, y in points2]
    for i in range(len(pts2) - 1):
        lines.addByTwoPoints(
            adsk.core.Point3D.create(*pts2[i]),
            adsk.core.Point3D.create(*pts2[i + 1]),
        )
    lines.addByTwoPoints(
        adsk.core.Point3D.create(*pts2[-1]),
        adsk.core.Point3D.create(*pts2[0]),
    )
    ext = rc.features.extrudeFeatures
    dist = adsk.core.ValueInput.createByReal(2.0 * scaling)
    for i in range(sketch.profiles.count):
        inp = ext.createInput(
            sketch.profiles.item(i),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        inp.setDistanceExtent(False, dist)
        ext.add(inp)
    return {"body_count": rc.bRepBodies.count}
