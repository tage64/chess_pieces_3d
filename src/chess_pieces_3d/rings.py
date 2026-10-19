"""Staggered sphere rings sampled by distance along a revolved profile."""

from dataclasses import dataclass
from math import atan2, cos, dist, floor, isfinite, radians, sin, sqrt, tau
from typing import TYPE_CHECKING

from .geometry import _TOL, Arc, GeometryError, Point, Segment, Vector, _point, _positive
from .profile import Profile

if TYPE_CHECKING:
    import cadquery as cq


@dataclass(frozen=True, slots=True)
class SandPatch:
    """Unfused balls and the selected untextured surface area, in mm²."""

    balls: tuple[cq.Shape, ...]
    area: float

    @property
    def count(self) -> int:
        return len(self.balls)

    @property
    def density_per_cm2(self) -> float:
        return 100 * self.count / self.area


def _sample(segment: Segment, fraction: float) -> tuple[Point, Vector]:
    point = segment.point_at(fraction)
    if isinstance(segment, Arc):
        sign = 1 if segment.turn == "ccw" else -1
        angle = atan2(point[1] - segment.center[1], point[0] - segment.center[0])
        return point, (-sign * sin(angle), sign * cos(angle))
    return point, segment.start_tangent


def _fraction(segment: Segment, point: Point) -> float | None:
    if dist(point, segment.start) <= _TOL:
        return 0
    if dist(point, segment.end) <= _TOL:
        return 1
    if isinstance(segment, Arc):
        if abs(dist(point, segment.center) - segment.radius) > _TOL:
            return None
        start = atan2(segment.start[1] - segment.center[1], segment.start[0] - segment.center[0])
        angle = atan2(point[1] - segment.center[1], point[0] - segment.center[0])
        sign = 1 if segment.turn == "ccw" else -1
        fraction = ((sign * (angle - start)) % tau) / segment.sweep
    else:
        dx, dy = segment.end[0] - segment.start[0], segment.end[1] - segment.start[1]
        fraction = ((point[0] - segment.start[0]) * dx + (point[1] - segment.start[1]) * dy) / (
            dx**2 + dy**2
        )
    if not 0 <= fraction <= 1 or dist(_sample(segment, fraction)[0], point) > _TOL:
        return None
    return fraction


def _locate(profile: Profile, point: Point, *, end: bool) -> float:
    point = _point(point)
    matches: list[float] = []
    position = 0.0
    for segment in profile.segments:
        fraction = _fraction(segment, point)
        if fraction is not None:
            location = position + fraction * segment.length
            if not matches or abs(matches[-1] - location) > _TOL:
                matches.append(location)
        position += segment.length
    label = "end" if end else "start"
    if not matches:
        raise GeometryError(f"{label} point does not lie on the profile")
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 2 and abs(matches[0]) <= _TOL and abs(matches[1] - position) <= _TOL:
        return matches[-1] if end else matches[0]
    raise GeometryError(f"{label} point is ambiguous: the profile passes through it more than once")


@dataclass(frozen=True, slots=True)
class _Section:
    segment: Segment
    start: float
    end: float

    @property
    def length(self) -> float:
        return (self.end - self.start) * self.segment.length

    @property
    def radial_integral(self) -> float:
        """Integral of radius over meridian arc length."""
        a, _ = _sample(self.segment, self.start)
        b, _ = _sample(self.segment, self.end)
        if isinstance(self.segment, Arc):
            arc = self.segment
            # sin(theta) = (height - centre_height) / circle_radius.
            sign = 1 if arc.turn == "ccw" else -1
            return arc.center[0] * self.length + sign * arc.radius * (b[1] - a[1])
        return (a[0] + b[0]) * self.length / 2

    def validate_radius(self) -> None:
        a, _ = _sample(self.segment, self.start)
        b, _ = _sample(self.segment, self.end)
        minimum = min(a[0], b[0])
        if isinstance(self.segment, Arc):
            arc = self.segment
            angle = atan2(a[1] - arc.center[1], a[0] - arc.center[0])
            sign = 1 if arc.turn == "ccw" else -1
            to_leftmost = (sign * (tau / 2 - angle)) % tau
            if to_leftmost <= arc.sweep * (self.end - self.start) + _TOL:
                minimum = min(minimum, arc.center[0] - arc.radius)
        if minimum < -_TOL:
            raise GeometryError(
                f"{self.segment.name}: the selected profile crosses negative X radii"
            )


def _sections(profile: Profile, start: Point, end: Point) -> list[_Section]:
    first, last = _locate(profile, start, end=False), _locate(profile, end, end=True)
    if last - first <= _TOL:
        raise GeometryError("end must follow start along the profile; intervals do not wrap")
    sections: list[_Section] = []
    position = 0.0
    for segment in profile.segments:
        length = segment.length
        low, high = max(first, position), min(last, position + length)
        if high - low > _TOL:
            section = _Section(
                segment, max(0, (low - position) / length), min(1, (high - position) / length)
            )
            section.validate_radius()
            if section.radial_integral > _TOL:
                sections.append(section)
        position += length
    if not sections:
        raise GeometryError("the selected profile interval has no revolved surface area")
    return sections


def ring_sand(
    profile: Profile,
    start: Point,
    end: Point,
    angle: float = 360,
    *,
    start_angle: float = 0,
    spacing: float = 0.8,
    radius: float = 0.2,
) -> SandPatch:
    """Generate unfused sphere rings between two exact profile points.

    Distances and radii are in mm; angles are degrees counterclockwise about Z,
    starting at +X. Profile (X, Y) maps to (radius, height). The interval follows
    profile order, without wrapping, and may start/end inside a line or arc.

    Ring centres are inset by half a row from the interval ends. Row spacing is
    approximately spacing * sqrt(3)/2; counts are rounded to fit each ring and
    alternating rings shift by half an angular step. Full revolutions have no
    duplicate seam balls. Axis-only sections are omitted.

    This is approximately hexagonal, not an exact geodesic lattice: changing
    circumference, integer counts, poles and sharp corners affect neighbours.
    Bounds apply to sphere centres, not their protruding footprints. The patch's
    area is the exact selected untextured surface area, not the balls' area.
    """
    _positive(spacing, "spacing")
    _positive(radius, "radius")
    if spacing <= 2 * radius:
        raise GeometryError("spacing must exceed the sphere diameter")
    if not isfinite(angle) or not 0 < angle <= 360:
        raise GeometryError("angle must be greater than 0 and at most 360 degrees")
    if not isfinite(start_angle):
        raise GeometryError("start_angle must be finite")
    sections = _sections(profile, start, end)
    sweep = radians(angle)
    area = sweep * sum(section.radial_integral for section in sections)
    length = sum(section.length for section in sections)
    rows = max(1, floor(length / (spacing * sqrt(3) / 2) + 0.5))
    row_spacing = length / rows
    origin_angle = radians(start_angle % 360)

    import cadquery as cq

    balls: list[cq.Shape] = []
    section_index = 0
    section_start = 0.0
    for row in range(rows):
        position = (row + 0.5) * row_spacing
        while (
            position > section_start + sections[section_index].length
            and section_index < len(sections) - 1
        ):
            section_start += sections[section_index].length
            section_index += 1
        section = sections[section_index]
        fraction = section.start + (position - section_start) / section.segment.length
        (r, z), tangent = _sample(section.segment, fraction)
        if r <= _TOL:
            continue
        count = max(1, floor(sweep * r / spacing + 0.5))
        step = sweep / count
        phase = (0.5 * (row % 2)) if angle == 360 else (0.25 + 0.5 * (row % 2))
        for column in range(count):
            theta = origin_angle + (column + phase) * step
            c, s = cos(theta), sin(theta)
            point = (r * c, r * s, z)
            normal = (tangent[1] * c, tangent[1] * s, -tangent[0])
            balls.append(cq.Solid.makeSphere(radius, point, dir=normal, angleDegrees1=-90))
    return SandPatch(tuple(balls), area)
