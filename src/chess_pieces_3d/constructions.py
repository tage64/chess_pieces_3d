"""Compound constructions; solvers return segments without mutating a profile."""

from math import dist, isfinite, sqrt

from .geometry import (
    _TOL,
    Arc,
    GeometryError,
    Line,
    Point,
    Turn,
    Vector,
    _add,
    _close,
    _dot,
    _left,
    _matches,
    _positive,
    _quadratic_roots,
    _scale,
    _sign,
    _sub,
)


def arc_line(
    start: Point, end: Point, tangent: Vector, radius: float, turn: Turn, name: str
) -> tuple[Arc, Line]:
    _positive(radius, "radius")
    center = _add(start, _scale(_left(tangent), _sign(turn) * radius))
    displacement = _sub(end, center)
    squared_distance = _dot(displacement, displacement)
    if squared_distance <= radius**2:
        raise GeometryError("the endpoint must lie outside the arc's circle")
    midpoint = _add(center, _scale(displacement, radius**2 / squared_distance))
    offset = _scale(
        _left(displacement), radius * sqrt(squared_distance - radius**2) / squared_distance
    )
    solutions: list[tuple[Arc, Line]] = []
    for contact in (_add(midpoint, offset), _sub(midpoint, offset)):
        try:
            arc = Arc(start, contact, center, turn, f"{name}.arc")
            line = Line(contact, end, f"{name}.line")
        except GeometryError:
            continue
        if _matches(arc, tangent, line.start_tangent):
            solutions.append((arc, line))
    if not solutions:
        raise GeometryError("no arc below 180 degrees joins the endpoint with a tangent line")
    if len(solutions) > 1:
        raise GeometryError("ambiguous arc-line construction")
    return solutions[0]


def arc_via_extreme(
    start: Point,
    end: Point,
    extreme_x: float,
    start_radius: float,
    end_radius: float,
    name: str,
) -> tuple[Arc, ...]:
    for radius in (start_radius, end_radius):
        if not isfinite(radius) or radius < 0:
            raise GeometryError("fillet radii must be finite and nonnegative")
    if not isfinite(extreme_x):
        raise GeometryError("extreme_x must be finite")
    side = 1 if extreme_x > start[0] else -1
    width = side * (extreme_x - start[0])
    inset = side * (extreme_x - end[0])
    rise = end[1] - start[1]
    if width <= _TOL or inset <= _TOL:
        raise GeometryError("extreme_x must lie strictly to the same side of both endpoints")
    if abs(rise) <= _TOL:
        raise GeometryError("endpoints must have different Y coordinates")

    # Eliminate radius from the two external circle-tangency equations.
    levels = _quadratic_roots(
        1 - inset / width,
        -2 * rise,
        2 * inset * start_radius + inset**2 + rise**2 - width * inset - 2 * inset * end_radius,
        max(1, inset / width),
    )
    turn: Turn = "ccw" if side * rise > 0 else "cw"
    fillet_turn: Turn = "cw" if turn == "ccw" else "ccw"
    vertical: Vector = (0, 1 if rise > 0 else -1)
    start_center = (start[0] + side * start_radius, start[1])
    end_center = (end[0] + side * end_radius, end[1])
    solutions: list[tuple[Arc, ...]] = []
    for level in levels:
        if not _TOL < level / rise < 1 - _TOL:
            continue
        radius = (level**2 + width**2 - 2 * width * start_radius) / (2 * width)
        if not isfinite(radius) or radius <= _TOL:
            continue
        center = (extreme_x - side * radius, start[1] + level)
        extreme = (extreme_x, center[1])
        start_join = _add(
            start_center, _scale(_sub(center, start_center), start_radius / (start_radius + radius))
        )
        end_join = _add(
            end_center, _scale(_sub(center, end_center), end_radius / (end_radius + radius))
        )
        try:
            segments: list[Arc] = []
            if start_radius > 0:
                segments.append(
                    Arc(start, start_join, start_center, fillet_turn, f"{name}.start_fillet")
                )
            segments.extend(
                (
                    Arc(start_join, extreme, center, turn, f"{name}.before_extreme"),
                    Arc(extreme, end_join, center, turn, f"{name}.after_extreme"),
                )
            )
            if end_radius > 0:
                segments.append(Arc(end_join, end, end_center, fillet_turn, f"{name}.end_fillet"))
        except GeometryError:
            continue
        if not all(
            dist(a.end_tangent, b.start_tangent) <= _TOL * 10
            for a, b in zip(segments[:-1], segments[1:], strict=True)
        ):
            continue
        if start_radius > 0 and not (
            _close(segments[0].radius, start_radius) and _matches(segments[0], vertical, None)
        ):
            continue
        if end_radius > 0 and not (
            _close(segments[-1].radius, end_radius) and _matches(segments[-1], None, vertical)
        ):
            continue
        solutions.append(tuple(segments))
    if not solutions:
        raise GeometryError("no minor-arc construction satisfies the X extremum and fillet radii")
    if len(solutions) > 1:
        raise GeometryError("ambiguous X-extremum construction")
    return solutions[0]
