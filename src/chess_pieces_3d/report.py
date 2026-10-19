"""Plain-text profile reports, with names immediately after endpoints."""

from .geometry import Arc, Point
from .profile import Profile


def _number(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _point(point: Point) -> str:
    return f"({_number(point[0])}, {_number(point[1])})"


def format_profile(profile: Profile) -> str:
    rows = [("Type", "End", "Name"), ("start", _point(profile.start), "")]
    for segment in profile.segments:
        kind, details = "line", segment.name
        if isinstance(segment, Arc):
            kind = f"arc({segment.turn})"
            details += f"  r={_number(segment.radius)} centre={_point(segment.center)}"
        rows.append((kind, _point(segment.end), details))
    kind_width = max(len(row[0]) for row in rows)
    end_width = max(len(row[1]) for row in rows)
    return "\n".join(
        f"{kind:<{kind_width}}  {end:<{end_width}}  {details}".rstrip()
        for kind, end, details in rows
    )
