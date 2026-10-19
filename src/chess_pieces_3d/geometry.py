"""Directed, minor-arc constructions in the XY plane."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import atan2, copysign, cos, dist, hypot, isclose, isfinite, pi, sin, sqrt, tau
from typing import Literal, Self

type Point = tuple[float, float]
type Vector = tuple[float, float]
type Turn = Literal["cw", "ccw"]

TANGENT_X: Vector = (1.0, 0.0)
TANGENT_Y: Vector = (0.0, 1.0)
_TOL = 1e-9


class GeometryError(ValueError):
    """The requested construction is impossible, ambiguous, or invalid."""


def _add(a: Vector, b: Vector) -> Vector:
    return a[0] + b[0], a[1] + b[1]


def _sub(a: Vector, b: Vector) -> Vector:
    return a[0] - b[0], a[1] - b[1]


def _scale(a: Vector, factor: float) -> Vector:
    return a[0] * factor, a[1] * factor


def _dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _left(a: Vector) -> Vector:
    return -a[1], a[0]


def _point(value: Point) -> Point:
    if not all(isfinite(v) for v in value):
        raise GeometryError("coordinates and vectors must be finite")
    return float(value[0]), float(value[1])


def _unit(vector: Vector) -> Vector:
    vector = _point(vector)
    length = hypot(*vector)
    if length <= _TOL:
        raise GeometryError("a tangent or segment must have nonzero length")
    return _scale(vector, 1 / length)


def _positive(value: float, label: str) -> None:
    if not isfinite(value) or value <= 0:
        raise GeometryError(f"{label} must be finite and positive")


def _check_fraction(fraction: float) -> None:
    if not isfinite(fraction) or not 0 <= fraction <= 1:
        raise GeometryError("fraction must be finite and between 0 and 1")


def _close(a: float, b: float) -> bool:
    return isclose(a, b, rel_tol=_TOL, abs_tol=_TOL)


def _sign(turn: Turn) -> int:
    if turn not in ("cw", "ccw"):
        raise GeometryError("turn must be 'cw' or 'ccw'")
    return 1 if turn == "ccw" else -1


def _coordinate(current: float, absolute: float | None, delta: float | None) -> float | None:
    if absolute is not None and delta is not None:
        raise GeometryError("specify either an absolute coordinate or its offset, not both")
    value = absolute if absolute is not None else current + delta if delta is not None else None
    if value is not None and not isfinite(value):
        raise GeometryError("coordinates must be finite")
    return value


def _endpoint(start: Point, x: float | None, y: float | None) -> Point:
    return start[0] if x is None else x, start[1] if y is None else y


@dataclass(frozen=True, slots=True)
class Line:
    start: Point
    end: Point
    name: str

    def __post_init__(self) -> None:
        _point(self.start)
        _point(self.end)
        _unit(_sub(self.end, self.start))

    @property
    def length(self) -> float:
        return dist(self.start, self.end)

    def point_at(self, fraction: float) -> Point:
        """Sample by arc length, from start (0) to end (1)."""
        _check_fraction(fraction)
        if fraction == 0:
            return self.start
        if fraction == 1:
            return self.end
        return _add(self.start, _scale(_sub(self.end, self.start), fraction))

    @property
    def start_tangent(self) -> Vector:
        return _unit(_sub(self.end, self.start))

    @property
    def end_tangent(self) -> Vector:
        return self.start_tangent


@dataclass(frozen=True, slots=True)
class Arc:
    start: Point
    end: Point
    center: Point
    turn: Turn
    name: str

    def __post_init__(self) -> None:
        _point(self.start)
        _point(self.end)
        _point(self.center)
        _sign(self.turn)
        _positive(self.radius, "radius")
        if not _close(self.radius, dist(self.end, self.center)):
            raise GeometryError("arc endpoints must lie on the same circle")
        if dist(self.start, self.end) <= _TOL or not _TOL < self.sweep < pi - _TOL:
            raise GeometryError("an arc must have a sweep strictly between 0 and 180 degrees")

    @property
    def length(self) -> float:
        return self.radius * self.sweep

    def point_at(self, fraction: float) -> Point:
        """Sample by arc length, following the arc's turn direction."""
        _check_fraction(fraction)
        if fraction == 0:
            return self.start
        if fraction == 1:
            return self.end
        angle = atan2(self.start[1] - self.center[1], self.start[0] - self.center[0])
        angle += _sign(self.turn) * self.sweep * fraction
        return self.center[0] + self.radius * cos(angle), self.center[1] + self.radius * sin(angle)

    @property
    def radius(self) -> float:
        return dist(self.start, self.center)

    @property
    def sweep(self) -> float:
        """Positive angle in radians, measured in the direction of travel."""
        a, b = _sub(self.start, self.center), _sub(self.end, self.center)
        angle = atan2(a[0] * b[1] - a[1] * b[0], _dot(a, b))
        return (_sign(self.turn) * angle) % tau

    @property
    def start_tangent(self) -> Vector:
        return _scale(_left(_unit(_sub(self.start, self.center))), _sign(self.turn))

    @property
    def end_tangent(self) -> Vector:
        return _scale(_left(_unit(_sub(self.end, self.center))), _sign(self.turn))


@dataclass(frozen=True, slots=True)
class ArcPair:
    first: Arc
    second: Arc
    name: str

    @property
    def start(self) -> Point:
        return self.first.start

    @property
    def end(self) -> Point:
        return self.second.end

    @property
    def start_tangent(self) -> Vector:
        return self.first.start_tangent

    @property
    def end_tangent(self) -> Vector:
        return self.second.end_tangent

    @property
    def length(self) -> float:
        return self.first.length + self.second.length

    def point_at(self, fraction: float) -> Point:
        return ProfilePath((self.first, self.second)).point_at(fraction)


type Segment = Line | Arc


class ProfilePath[S: Segment](tuple[S, ...]):
    """An immutable, connected profile part, retaining tuple indexing/unpacking."""

    __slots__ = ()

    def __new__(cls, segments: Iterable[S]) -> Self:
        path = super().__new__(cls, segments)
        if not path:
            raise GeometryError("a profile path must contain at least one segment")
        if any(dist(a.end, b.start) > _TOL for a, b in zip(path[:-1], path[1:], strict=True)):
            raise GeometryError("profile path segments must be connected in order")
        return path

    @property
    def start(self) -> Point:
        return self[0].start

    @property
    def end(self) -> Point:
        return self[-1].end

    @property
    def length(self) -> float:
        return sum(segment.length for segment in self)

    def point_at(self, fraction: float) -> Point:
        """Sample the whole path by arc length, not by segment count."""
        _check_fraction(fraction)
        if fraction == 0:
            return self.start
        if fraction == 1:
            return self.end
        remaining = fraction * self.length
        for segment in self:
            if remaining <= segment.length:
                return segment.point_at(min(1, max(0, remaining / segment.length)))
            remaining -= segment.length
        return self.end


def _matches(arc: Arc, start: Vector | None, end: Vector | None) -> bool:
    return (start is None or dist(arc.start_tangent, start) <= _TOL * 10) and (
        end is None or dist(arc.end_tangent, end) <= _TOL * 10
    )


def _circle_intersections(center: Point, radius: float, axis: int, value: float) -> list[Point]:
    offset = value - center[axis]
    remainder = radius**2 - offset**2
    if remainder < 0 and not _close(abs(offset), radius):
        return []
    height = sqrt(max(0, remainder))
    points: list[Point] = []
    for other in (center[1 - axis] + height, center[1 - axis] - height):
        point = (value, other) if axis == 0 else (other, value)
        if not any(dist(point, p) <= _TOL for p in points):
            points.append(point)
    return points


def _single_arc(
    start: Point,
    x: float | None,
    y: float | None,
    radius: float | None,
    start_tangent: Vector | None,
    end_tangent: Vector | None,
    turn: Turn | None,
    name: str,
) -> Arc:
    if turn is not None:
        _sign(turn)
    candidates: list[tuple[Point, Point, Turn]] = []
    if radius is None:
        end = _endpoint(start, x, y)
        displacement = _sub(end, start)
        tangent = start_tangent if start_tangent is not None else end_tangent
        assert tangent is not None
        normal = _left(tangent)
        projection = _dot(displacement, normal)
        if abs(projection) <= _TOL or dist(start, end) <= _TOL:
            raise GeometryError("endpoint and tangent do not define a finite-radius arc")
        signed_radius = _dot(displacement, displacement) / (2 * projection)
        anchor = start
        if start_tangent is None:
            signed_radius = -signed_radius
            anchor = end
        direction: Turn = "ccw" if signed_radius > 0 else "cw"
        candidates.append((end, _add(anchor, _scale(normal, signed_radius)), direction))
    else:
        _positive(radius, "radius")
        if x is None and y is None:
            raise GeometryError("a radius-constrained arc needs at least one endpoint coordinate")
        for direction in ("cw", "ccw"):
            if turn is not None and direction != turn:
                continue
            tangent = start_tangent if start_tangent is not None else end_tangent
            assert tangent is not None
            offset = _scale(_left(tangent), _sign(direction) * radius)
            # An end tangent translates the endpoint's circle locus by -offset.
            locus = _add(start, offset) if start_tangent is not None else _sub(start, offset)
            if x is not None and y is not None:
                ends = [(x, y)]
            else:
                axis, value = (0, x) if x is not None else (1, y)
                assert value is not None
                ends = _circle_intersections(locus, radius, axis, value)
            for end in ends:
                center = locus if start_tangent is not None else _add(end, offset)
                candidates.append((end, center, direction))

    solutions: list[Arc] = []
    for end, center, direction in candidates:
        if turn is not None and direction != turn:
            continue
        try:
            arc = Arc(start, end, center, direction, name)
        except GeometryError:
            continue
        if radius is not None and not _close(arc.radius, radius):
            continue
        if _matches(arc, start_tangent, end_tangent):
            solutions.append(arc)
    if not solutions:
        raise GeometryError("no arc below 180 degrees satisfies the supplied constraints")
    if len(solutions) > 1:
        raise GeometryError("ambiguous arc; specify a turn or the other endpoint coordinate")
    return solutions[0]


def _quadratic_roots(a: float, b: float, c: float, scale: float) -> list[float]:
    if abs(a) <= _TOL * scale:
        return [] if abs(b) <= _TOL else [-c / b]
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        if abs(discriminant) > _TOL * max(b * b, abs(4 * a * c)):
            return []
        discriminant = 0
    q = -0.5 * (b + copysign(sqrt(discriminant), b))
    if q == 0:
        return [-b / (2 * a)]
    roots = [q / a, c / q]
    return roots[:1] if _close(*roots) else roots


def _arc_pair(
    start: Point,
    end: Point,
    start_tangent: Vector,
    end_tangent: Vector,
    turns: tuple[Turn, Turn],
    ratio: float,
    name: str,
) -> ArcPair:
    _positive(ratio, "radius_ratio")
    first_sign, second_sign = _sign(turns[0]), _sign(turns[1])
    if first_sign == second_sign:
        raise GeometryError("arc_pair requires opposite turn directions")
    displacement = _sub(end, start)
    first_offset = _scale(_left(start_tangent), first_sign * ratio)
    second_offset = _scale(_left(end_tangent), second_sign)
    offset = _sub(second_offset, first_offset)
    # Externally tangent circles: |displacement + r * offset| = (ratio + 1) * r.
    scale = (ratio + 1) ** 2
    radii = _quadratic_roots(
        _dot(offset, offset) - scale,
        2 * _dot(displacement, offset),
        _dot(displacement, displacement),
        scale,
    )
    solutions: list[ArcPair] = []
    for radius in radii:
        if not isfinite(radius) or radius <= _TOL:
            continue
        center1 = _add(start, _scale(first_offset, radius))
        center2 = _add(end, _scale(second_offset, radius))
        join = _add(center1, _scale(_sub(center2, center1), ratio / (ratio + 1)))
        try:
            first = Arc(start, join, center1, turns[0], f"{name}.1")
            second = Arc(join, end, center2, turns[1], f"{name}.2")
        except GeometryError:
            continue
        if (
            _close(first.radius / second.radius, ratio)
            and _matches(first, start_tangent, second.start_tangent)
            and _matches(second, first.end_tangent, end_tangent)
        ):
            solutions.append(ArcPair(first, second, name))
    if not solutions:
        raise GeometryError(
            "no tangent arc pair below 180 degrees satisfies the supplied constraints"
        )
    if len(solutions) > 1:
        raise GeometryError("ambiguous arc pair; the constraints admit multiple solutions")
    return solutions[0]
