import contextlib
import importlib.util
import io
import math
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from chess_pieces_3d import SandPatch, ring_sand

if TYPE_CHECKING:
    import cadquery as cq

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("OCP"), "OCP is unavailable")
class PrintExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        import cadquery as cq

        self.cq = cq

    def assertSingleSolid(self, shape: cq.Shape) -> None:
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()), 1)

    def test_bishop_example_and_stl_export(self) -> None:
        import trimesh

        with patch.object(sys, "path", [str(ROOT / "examples"), *sys.path]):
            namespace = runpy.run_path(str(ROOT / "examples/löpare_3d_print.py"))
            build = namespace["build_solid"]
            spy = Mock(wraps=ring_sand)
            output = io.StringIO()
            with patch.dict(build.__globals__, ring_sand=spy), contextlib.redirect_stdout(output):
                result = build(report=True)
        for text in (
            "Sand 0–90°: r=0.2 mm, spacing=0.7 mm; 152 balls; 230.7 balls/cm²",
            "Sand 90–180°: r=0.2 mm, spacing=0.9 mm; 93 balls; 141.15 balls/cm²",
            "Sand 180–270°: r=0.3 mm, spacing=0.8 mm; 123 balls; 186.68 balls/cm²",
            "Sand 270–360°: r=0.3 mm, spacing=1 mm; 75 balls; 113.83 balls/cm²",
            "Total: 443 balls. Knob: Ø2 mm, 2 mm above the original tip.",
        ):
            self.assertIn(text, output.getvalue())
        expected = ((0, 0.2, 0.7), (90, 0.2, 0.9), (180, 0.3, 0.8), (270, 0.3, 1))
        self.assertEqual(spy.call_count, 4)
        for (start_angle, radius, spacing), actual in zip(
            expected, spy.call_args_list, strict=True
        ):
            self.assertIs(actual.args[0], namespace["löpare"].profile)
            self.assertEqual(actual.kwargs["angle"], 90)
            self.assertEqual(actual.kwargs["start_angle"], start_angle)
            self.assertEqual(actual.kwargs["radius"], radius)
            self.assertEqual(actual.kwargs["spacing"], spacing)
            self.assertEqual(actual.kwargs["start"], namespace["löpare"].head.point_at(0.2))
            self.assertEqual(actual.kwargs["end"], namespace["löpare"].head.point_at(0.85))
        magnet = runpy.run_path(str(ROOT / "examples/shared.py"))["chess_piece_magnet"]
        base = namespace["löpare"].build_solid().cut(magnet)
        self.assertGreater(result.Volume(), base.Volume())
        self.assertAlmostEqual(base.cut(result).Volume(), 0, places=7)
        self.assertSingleSolid(result)
        self.assertFalse(result.isInside(self.cq.Vector(0, 0, 3)))
        self.assertTrue(result.isInside(self.cq.Vector(0, 0, 0.3)))
        tip_height = namespace["löpare"].tip.end[1]
        self.assertAlmostEqual(result.BoundingBox().zmax, tip_height + 2, delta=1e-6)
        self.assertTrue(base.isInside(self.cq.Vector(1, 0, tip_height - 2)))
        for index in range(8):
            theta = index * math.pi / 4
            for r, inside in ((0.99, True), (1.01, False)):
                point = self.cq.Vector(r * math.cos(theta), r * math.sin(theta), tip_height + 1)
                self.assertEqual(result.isInside(point), inside)
        self.assertTrue(result.isInside(self.cq.Vector(0, 0, tip_height + 1.99)))
        self.assertFalse(result.isInside(self.cq.Vector(0, 0, tip_height + 2.01)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sand.stl"
            self.cq.exporters.export(result, str(path), tolerance=0.02, angularTolerance=0.15)
            self.assertGreater(path.stat().st_size, 0)
            # OCCT can emit zero-area triangles at sphere poles.
            mesh = trimesh.load_mesh(path, validate=True)
            self.assertTrue(mesh.is_watertight)
            self.assertTrue(mesh.is_winding_consistent)
            self.assertGreater(mesh.volume, 0)

    def test_build_is_quiet_unless_reporting_is_requested(self) -> None:
        with patch.object(sys, "path", [str(ROOT / "examples"), *sys.path]):
            namespace = runpy.run_path(str(ROOT / "examples/löpare_3d_print.py"))
            build = namespace["build_solid"]
            output = io.StringIO()
            with (
                patch.dict(build.__globals__, ring_sand=Mock(return_value=SandPatch((), 100))),
                contextlib.redirect_stdout(output),
            ):
                self.assertSingleSolid(build())
                self.assertEqual(output.getvalue(), "")
                build(report=True)
            self.assertIn("0 balls; 0 balls/cm²", output.getvalue())

    def test_importing_print_example_does_not_load_cad(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys\n"
                f"sys.path.insert(0, {str(ROOT / 'examples')!r})\n"
                "import löpare_3d_print\n"
                "assert 'cadquery' not in sys.modules\n"
                "assert 'OCP' not in sys.modules\n",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
