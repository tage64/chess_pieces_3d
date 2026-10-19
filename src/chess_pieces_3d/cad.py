"""Revolve geometric profiles without loading CadQuery until a solid is requested."""

from math import atan2, cos, dist, pi, sin, tau
from typing import TYPE_CHECKING

from .geometry import _TOL, Arc, GeometryError, Point
from .profile import Profile

if TYPE_CHECKING:
    import cadquery as cq


def _arc_midpoint(arc: Arc) -> Point:
    angle = atan2(arc.start[1] - arc.center[1], arc.start[0] - arc.center[0])
    angle += (1 if arc.turn == "ccw" else -1) * arc.sweep / 2
    return arc.center[0] + arc.radius * cos(angle), arc.center[1] + arc.radius * sin(angle)


def _validate_profile(profile: Profile) -> None:
    if not profile.segments:
        raise GeometryError("cannot revolve an empty profile")
    if dist(profile.start, profile.end) > _TOL:
        raise GeometryError("the profile must be closed before revolving")
    for segment in profile.segments:
        if min(segment.start[0], segment.end[0]) < -_TOL:
            raise GeometryError(f"{segment.name}: X must be nonnegative when used as a radius")
        if isinstance(segment, Arc):
            start_angle = atan2(
                segment.start[1] - segment.center[1], segment.start[0] - segment.center[0]
            )
            sign = 1 if segment.turn == "ccw" else -1
            to_leftmost = (sign * (pi - start_angle)) % tau
            if to_leftmost <= segment.sweep + _TOL and segment.center[0] - segment.radius < -_TOL:
                raise GeometryError(f"{segment.name}: the arc crosses into negative X radii")


def revolve_profile(profile: Profile) -> cq.Workplane:
    """Revolve a closed profile 360° about Z, mapping profile (X, Y) to CAD (X, Z).

    Circular edges are preserved. The contour must stay at nonnegative X and
    produce exactly one valid solid; it is never implicitly closed.
    """
    _validate_profile(profile)

    import cadquery as cq

    wire = cq.Workplane("XZ").moveTo(*profile.start)
    for segment in profile.segments:
        if isinstance(segment, Arc):
            wire = wire.threePointArc(_arc_midpoint(segment), segment.end)
        else:
            wire = wire.lineTo(*segment.end)
    result = wire.close().revolve(360, (0, 0), (0, 1))
    shape = result.findSolid()
    if len(shape.Solids()) != 1 or not shape.isValid():
        raise GeometryError("revolving the profile did not produce a single valid solid")
    return result
