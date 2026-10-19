"""Magnet-cut bishop with four sanding samples and a Ø2 mm top knob."""

from typing import TYPE_CHECKING

import löpare

from chess_pieces_3d import ring_sand

if TYPE_CHECKING:
    import cadquery as cq

# Start angle (degrees), ball radius (mm), nominal centre spacing (mm).
SAND_PATCHES = ((0, 0.2, 0.7), (90, 0.2, 0.9), (180, 0.3, 0.8), (270, 0.3, 1.0))


def build_solid(*, report: bool = False) -> cq.Shape:
    import cadquery as cq
    from shared import chess_piece_magnet

    with_cut_magnet = löpare.build_solid().cut(chess_piece_magnet)
    patches = tuple(
        ring_sand(
            löpare.profile,
            start=löpare.head.point_at(0.2),
            end=löpare.head.point_at(0.85),
            angle=90,
            start_angle=start_angle,
            spacing=spacing,
            radius=radius,
        )
        for start_angle, radius, spacing in SAND_PATCHES
    )
    balls = tuple(ball for patch in patches for ball in patch.balls)
    # Embed the knob's base into the rounded tip; 2 mm remains above the old tip.
    overlap = 0.25
    knob = cq.Solid.makeCylinder(
        radius=1, height=2 + overlap, pnt=(0, 0, löpare.tip.end[1] - overlap)
    )
    textured = with_cut_magnet.fuse(knob, *balls)
    if (
        len(textured.Solids()) != 1
        or not textured.isValid()
        or textured.Volume() < with_cut_magnet.Volume() - 1e-7
    ):
        raise RuntimeError("print additions did not fuse into a single valid solid")
    if report:
        for (start_angle, radius, spacing), patch in zip(SAND_PATCHES, patches, strict=True):
            area_cm2 = f"{patch.area / 100:.2f}".rstrip("0").rstrip(".")
            density = f"{patch.density_per_cm2:.2f}".rstrip("0").rstrip(".")
            print(
                f"Sand {start_angle}–{start_angle + 90}°: r={radius:g} mm, "
                f"spacing={spacing:g} mm; {patch.count} balls; {density} balls/cm² "
                f"(surface patch: {area_cm2} cm²)."
            )
        print(f"Total: {len(balls)} balls. Knob: Ø2 mm, 2 mm above the original tip.")
    return textured


if __name__ == "__main__":
    import cadquery as cq

    cq.exporters.export(
        build_solid(report=True), "löpare_3d_print.stl", tolerance=0.02, angularTolerance=0.15
    )
