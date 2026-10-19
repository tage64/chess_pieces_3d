"""Incremental construction of named geometric profiles."""

from math import dist

from .constructions import arc_line as _arc_line
from .constructions import arc_via_extreme as _arc_via_extreme
from .geometry import (
    _TOL,
    Arc,
    ArcPair,
    GeometryError,
    Line,
    Point,
    ProfilePath,
    Segment,
    Turn,
    Vector,
    _arc_pair,
    _coordinate,
    _endpoint,
    _point,
    _single_arc,
    _unit,
)


class Profile:
    """An ordered profile; failed constructions leave it unchanged."""

    def __init__(self, start: Point = (0, 0)) -> None:
        self._start = _point(start)
        self._segments: list[Segment] = []
        self._names: set[str] = set()

    @property
    def start(self) -> Point:
        return self._start

    @property
    def end(self) -> Point:
        return self._segments[-1].end if self._segments else self.start

    @property
    def segments(self) -> tuple[Segment, ...]:
        return tuple(self._segments)

    @property
    def length(self) -> float:
        return sum(segment.length for segment in self._segments)

    def point_at(self, fraction: float) -> Point:
        """Sample the complete profile by arc length, from 0 to 1."""
        return ProfilePath(self._segments).point_at(fraction)

    @property
    def last_tangent(self) -> Vector:
        if not self._segments:
            raise GeometryError("the profile has no tangent yet; supply one explicitly")
        return self._segments[-1].end_tangent

    def _name(self, name: str | None, kind: str, *, suffixes: tuple[str, ...] = ()) -> str:
        if name is None:
            index = 1
            while True:
                candidate = f"{kind}_{index}"
                labels = {candidate} | {f"{candidate}.{suffix}" for suffix in suffixes}
                if not labels & self._names:
                    return candidate
                index += 1
        if not name.strip() or any(c in name for c in "\n\r\t"):
            raise GeometryError("names must be nonempty, single-line strings without tabs")
        labels = {name} | {f"{name}.{suffix}" for suffix in suffixes}
        if labels & self._names:
            raise GeometryError(f"duplicate name: {name!r}")
        return name

    def _append(self, *segments: Segment, name: str) -> None:
        self._segments.extend(segments)
        self._names.update(segment.name for segment in segments)
        self._names.add(name)

    def line(
        self,
        *,
        x: float | None = None,
        dx: float | None = None,
        y: float | None = None,
        dy: float | None = None,
        name: str | None = None,
    ) -> Line:
        label = self._name(name, "line")
        try:
            end = _endpoint(
                self.end, _coordinate(self.end[0], x, dx), _coordinate(self.end[1], y, dy)
            )
            segment = Line(self.end, end, label)
        except GeometryError as exc:
            raise GeometryError(f"{label}: {exc}") from exc
        self._append(segment, name=label)
        return segment

    def arc(
        self,
        *,
        x: float | None = None,
        dx: float | None = None,
        y: float | None = None,
        dy: float | None = None,
        radius: float | None = None,
        start_tangent: Vector | None = None,
        end_tangent: Vector | None = None,
        turn: Turn | None = None,
        name: str | None = None,
    ) -> Arc:
        """Solve an arc from a tangent and endpoint, or a tangent, radius and coordinate."""
        label = self._name(name, "arc")
        try:
            if start_tangent is None and end_tangent is None:
                start_tangent = self.last_tangent
            start_vector = None if start_tangent is None else _unit(start_tangent)
            end_vector = None if end_tangent is None else _unit(end_tangent)
            segment = _single_arc(
                self.end,
                _coordinate(self.end[0], x, dx),
                _coordinate(self.end[1], y, dy),
                radius,
                start_vector,
                end_vector,
                turn,
                label,
            )
        except GeometryError as exc:
            raise GeometryError(f"{label}: {exc}") from exc
        self._append(segment, name=label)
        return segment

    def arc_pair(
        self,
        *,
        end_tangent: Vector,
        turns: tuple[Turn, Turn],
        radius_ratio: float,
        x: float | None = None,
        dx: float | None = None,
        y: float | None = None,
        dy: float | None = None,
        start_tangent: Vector | None = None,
        name: str | None = None,
    ) -> ArcPair:
        """Solve two opposite-turn arcs with a tangent join and r1 / r2 = radius_ratio."""
        label = self._name(name, "arc_pair", suffixes=("1", "2"))
        try:
            end = _endpoint(
                self.end, _coordinate(self.end[0], x, dx), _coordinate(self.end[1], y, dy)
            )
            pair = _arc_pair(
                self.end,
                end,
                _unit(self.last_tangent if start_tangent is None else start_tangent),
                _unit(end_tangent),
                turns,
                radius_ratio,
                label,
            )
        except GeometryError as exc:
            raise GeometryError(f"{label}: {exc}") from exc
        self._append(pair.first, pair.second, name=label)
        return pair

    def arc_line(
        self,
        *,
        radius: float,
        turn: Turn,
        x: float | None = None,
        dx: float | None = None,
        y: float | None = None,
        dy: float | None = None,
        start_tangent: Vector | None = None,
        name: str | None = None,
    ) -> tuple[Arc, Line]:
        """Add an arc followed by a tangent line ending at the requested coordinate."""
        label = self._name(name, "arc_line", suffixes=("arc", "line"))
        try:
            end = _endpoint(
                self.end, _coordinate(self.end[0], x, dx), _coordinate(self.end[1], y, dy)
            )
            segments = _arc_line(
                self.end,
                end,
                _unit(self.last_tangent if start_tangent is None else start_tangent),
                radius,
                turn,
                label,
            )
        except GeometryError as exc:
            raise GeometryError(f"{label}: {exc}") from exc
        self._append(*segments, name=label)
        return segments

    def arc_via_extreme(
        self,
        *,
        extreme_x: float,
        x: float | None = None,
        dx: float | None = None,
        y: float | None = None,
        dy: float | None = None,
        start_radius: float = 0,
        end_radius: float = 0,
        name: str | None = None,
    ) -> ProfilePath[Arc]:
        """Add a circle split at its X extremum, optionally filleted at vertical ends.

        The extremum lies strictly between endpoint Y values and beyond both X
        values. Nonzero fillets meet vertical endpoint tangents; zero omits a fillet
        and imposes no tangent constraint at that endpoint.
        """
        suffixes = (
            *(("start_fillet",) if start_radius > 0 else ()),
            "before_extreme",
            "after_extreme",
            *(("end_fillet",) if end_radius > 0 else ()),
        )
        label = self._name(name, "arc_via_extreme", suffixes=suffixes)
        try:
            end = _endpoint(
                self.end, _coordinate(self.end[0], x, dx), _coordinate(self.end[1], y, dy)
            )
            segments = ProfilePath(
                _arc_via_extreme(self.end, end, extreme_x, start_radius, end_radius, label)
            )
            if (
                start_radius > 0
                and self._segments
                and dist(self.last_tangent, segments[0].start_tangent) > _TOL * 10
            ):
                raise GeometryError(
                    "a start fillet requires a vertical incoming tangent toward the endpoint"
                )
        except GeometryError as exc:
            raise GeometryError(f"{label}: {exc}") from exc
        self._append(*segments, name=label)
        return segments
