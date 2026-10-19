"""Original rounded-coordinate model, retained for the legacy STL exporter."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq


def build_solid() -> cq.Workplane:
    import cadquery as cq

    return (
        cq.Workplane("XZ")
        .moveTo(0, 0)
        .lineTo(10, 0)
        .lineTo(10, 1.67)
        .radiusArc((8.67, 3.56), -2)
        .radiusArc((8, 4.5), 1)
        .lineTo(8, 6.5)
        .radiusArc((7.55, 7.34), -1)
        .radiusArc((4, 13.93), 7.89)
        .radiusArc((5.99, 19.17), 7.89)
        .radiusArc((6.5, 20.5), -2)
        .radiusArc((5.16, 22.39), -2)
        .lineTo(3.4, 23)
        .radiusArc((5.2, 28.61), -9.64)
        .radiusArc((2.5, 35.3), -9.64)
        .lineTo(2.5, 36.5)
        .radiusArc((0, 38.5), -2.56)
        .close()
        .revolve(360, (0, 0), (0, 1))
        .cut(cq.Solid.makeCylinder(3.15, 6.1, (0, 0, 1), (0, 0, 1)))
    )


def main() -> None:
    import cadquery as cq

    cq.exporters.export(build_solid(), "bishop.stl")
