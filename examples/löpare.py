"""Port of löpare.xlsx, constructed upward from the base with Y=0 at the bottom."""

from typing import TYPE_CHECKING

from chess_pieces_3d import TANGENT_Y, Profile, revolve_profile

if TYPE_CHECKING:
    import cadquery as cq

profile = Profile(start=(0, 0))

profile.line(x=10, name="base.bottom")
profile.line(dy=1.75, name="base.wall")
profile.arc_pair(
    x=8,
    dy=3,
    end_tangent=TANGENT_Y,
    turns=("ccw", "cw"),
    radius_ratio=2,
    name="base_transition",
)
profile.line(dy=1.5, name="rim")
profile.arc_via_extreme(
    x=6.5,
    dy=14,
    extreme_x=4,
    start_radius=1,
    end_radius=2,
    name="stem",
)
profile.arc_line(x=3.4, dy=2.5, radius=2, turn="ccw", name="collar")
profile.arc_via_extreme(x=2.5, dy=12.3, extreme_x=5.2, name="head")
profile.line(dy=1.2, name="head.neck")
profile.arc(x=0, dy=1.5, end_tangent=(-1, 0), name="tip")
profile.line(y=0, name="axis")


def build_solid() -> cq.Workplane:
    return revolve_profile(profile)


if __name__ == "__main__":
    import cadquery as cq

    cq.exporters.export(build_solid(), "bishop.stl")
