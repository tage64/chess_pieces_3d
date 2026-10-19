"""Terminal-friendly geometric profiles, independent of the CAD backend."""

from .cad import revolve_profile
from .geometry import (
    TANGENT_X,
    TANGENT_Y,
    Arc,
    ArcPair,
    GeometryError,
    Line,
    Point,
    ProfilePath,
    Segment,
    Turn,
    Vector,
)
from .profile import Profile
from .report import format_profile
from .rings import SandPatch, ring_sand

__all__ = [
    "TANGENT_X",
    "TANGENT_Y",
    "Arc",
    "ArcPair",
    "GeometryError",
    "Line",
    "Point",
    "Profile",
    "ProfilePath",
    "SandPatch",
    "Segment",
    "Turn",
    "Vector",
    "format_profile",
    "revolve_profile",
    "ring_sand",
]


def main() -> None:
    """Run the original CadQuery exporter, loading CAD only when requested."""
    from .bishop import main as export_bishop

    export_bishop()
