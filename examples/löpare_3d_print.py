"""Magnet-cut bishop with a 90° sanded sector from 20% to 85% along its head."""

from typing import TYPE_CHECKING

import löpare

from chess_pieces_3d import ring_sand

if TYPE_CHECKING:
    import cadquery as cq


def build_solid(*, report: bool = False) -> cq.Shape:
    from shared import chess_piece_magnet

    with_cut_magnet = löpare.build_solid().cut(chess_piece_magnet)
    patch = ring_sand(
        löpare.profile,
        start=löpare.head.point_at(0.2),
        end=löpare.head.point_at(0.85),
        angle=90,
        start_angle=-45,
        spacing=0.8,
        radius=0.2,
    )
    textured = with_cut_magnet.fuse(*patch.balls) if patch.balls else with_cut_magnet
    if (
        len(textured.Solids()) != 1
        or not textured.isValid()
        or textured.Volume() < with_cut_magnet.Volume() - 1e-7
    ):
        raise RuntimeError("surface texture did not fuse into a single valid solid")
    if report:
        area_cm2 = f"{patch.area / 100:.2f}".rstrip("0").rstrip(".")
        density = f"{patch.density_per_cm2:.2f}".rstrip("0").rstrip(".")
        print(
            f"Sand texture: {patch.count} balls; {density} balls/cm² "
            f"(surface patch: {area_cm2} cm²)."
        )
    return textured


if __name__ == "__main__":
    import cadquery as cq

    cq.exporters.export(
        build_solid(report=True), "löpare_3d_print.stl", tolerance=0.02, angularTolerance=0.15
    )
