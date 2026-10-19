import importlib.util
import math
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

from chess_pieces_3d import GeometryError, Profile, revolve_profile

ROOT = Path(__file__).resolve().parents[1]


def cylinder_profile() -> Profile:
    profile = Profile()
    profile.line(x=2)
    profile.line(y=3)
    profile.line(x=0)
    profile.line(y=0)
    return profile


def hemisphere_profile() -> Profile:
    profile = Profile()
    profile.line(x=2)
    profile.arc(x=0, y=2, start_tangent=(0, 1))
    profile.line(y=0)
    return profile


class CadConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workplane = MagicMock()
        for method in ("moveTo", "lineTo", "threePointArc", "close", "revolve"):
            getattr(self.workplane, method).return_value = self.workplane
        self.workplane.findSolid.return_value.Solids.return_value = [object()]
        self.workplane.findSolid.return_value.isValid.return_value = True
        self.backend = SimpleNamespace(Workplane=Mock(return_value=self.workplane))

    def test_revolves_in_xz_plane_about_vertical_axis(self) -> None:
        profile = cylinder_profile()
        with patch.dict(sys.modules, cadquery=self.backend):
            result = revolve_profile(profile)
        self.assertIs(result, self.workplane)
        self.backend.Workplane.assert_called_once_with("XZ")
        self.workplane.moveTo.assert_called_once_with(0, 0)
        self.assertEqual(
            self.workplane.lineTo.call_args_list,
            [call(2, 0), call(2, 3), call(0, 3), call(0, 0)],
        )
        self.workplane.close.assert_called_once_with()
        self.workplane.revolve.assert_called_once_with(360, (0, 0), (0, 1))
        self.assertEqual(profile.end, profile.start)

    def test_preserves_ccw_and_cw_arcs(self) -> None:
        for clockwise in (False, True):
            with self.subTest(clockwise=clockwise):
                self.workplane.reset_mock()
                profile = Profile()
                if clockwise:
                    profile.line(y=2)
                    arc = profile.arc(x=2, y=0, start_tangent=(1, 0))
                    profile.line(x=0)
                else:
                    profile.line(x=2)
                    arc = profile.arc(x=0, y=2, start_tangent=(0, 1))
                    profile.line(y=0)
                with patch.dict(sys.modules, cadquery=self.backend):
                    revolve_profile(profile)
                self.workplane.threePointArc.assert_called_once()
                midpoint, end = self.workplane.threePointArc.call_args.args
                self.assertAlmostEqual(midpoint[0], math.sqrt(2))
                self.assertAlmostEqual(midpoint[1], math.sqrt(2))
                self.assertEqual(end, arc.end)
                self.assertAlmostEqual(math.dist(midpoint, arc.center), arc.radius)

    def test_empty_and_open_profiles_fail_before_cad_import(self) -> None:
        empty = Profile()
        open_profile = Profile()
        open_profile.line(x=2)
        for profile in (empty, open_profile):
            with self.subTest(profile=profile), patch.dict(sys.modules, cadquery=self.backend):
                with self.assertRaises(GeometryError):
                    revolve_profile(profile)
        self.backend.Workplane.assert_not_called()

    def test_rejects_negative_endpoint_radii(self) -> None:
        profile = Profile()
        profile.line(x=-1, name="negative")
        profile.line(y=2)
        profile.line(x=0, y=0)
        with patch.dict(sys.modules, cadquery=self.backend):
            with self.assertRaisesRegex(GeometryError, "negative: X must be nonnegative"):
                revolve_profile(profile)
        self.backend.Workplane.assert_not_called()

    def test_rejects_arc_crossing_axis_between_nonnegative_endpoints(self) -> None:
        profile = Profile(start=(0, math.sqrt(3)))
        profile.arc(x=0, y=-math.sqrt(3), start_tangent=(-math.sqrt(3), -1), name="crossing")
        profile.line(y=math.sqrt(3))
        with patch.dict(sys.modules, cadquery=self.backend):
            with self.assertRaisesRegex(GeometryError, "crossing: the arc crosses"):
                revolve_profile(profile)
        self.backend.Workplane.assert_not_called()

    def test_allows_circle_center_left_of_axis_when_arc_stays_positive(self) -> None:
        profile = Profile(start=(2.5, -2))
        arc = profile.arc(x=2.5, y=2, start_tangent=(2, 3))
        self.assertLess(arc.center[0], 0)
        profile.line(x=0)
        profile.line(y=-2)
        profile.line(x=2.5)
        with patch.dict(sys.modules, cadquery=self.backend):
            revolve_profile(profile)
        self.workplane.revolve.assert_called_once()

    def test_rejects_invalid_or_multiple_solids(self) -> None:
        shape = self.workplane.findSolid.return_value
        for solids, valid in (([], True), ([object(), object()], True), ([object()], False)):
            with self.subTest(solids=len(solids), valid=valid):
                shape.Solids.return_value = solids
                shape.isValid.return_value = valid
                with patch.dict(sys.modules, cadquery=self.backend):
                    with self.assertRaisesRegex(GeometryError, "single valid solid"):
                        revolve_profile(cylinder_profile())

    def test_example_build_function_is_explicit(self) -> None:
        namespace = runpy.run_path(str(ROOT / "examples/löpare.py"))
        self.backend.Workplane.assert_not_called()
        with patch.dict(sys.modules, cadquery=self.backend):
            self.assertIs(namespace["build_solid"](), self.workplane)
        self.workplane.revolve.assert_called_once()
        self.workplane.threePointArc.assert_called()

    def test_imports_and_report_do_not_load_cadquery(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys\n"
                "from pathlib import Path\n"
                "from chess_pieces_3d import revolve_profile\n"
                "from chess_pieces_3d.cli import load_profile\n"
                "from chess_pieces_3d.cad import revolve_profile\n"
                f"load_profile(Path({str(ROOT / 'examples/löpare.py')!r}))\n"
                "assert 'cadquery' not in sys.modules\n"
                "assert 'chess_pieces_3d.bishop' not in sys.modules\n"
                "import chess_pieces_3d.bishop\n"
                "assert 'cadquery' not in sys.modules\n",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(
    importlib.util.find_spec("OCP"), "CadQuery's native OCP backend is unavailable"
)
class CadIntegrationTests(unittest.TestCase):
    def test_exact_cylinder_and_hemisphere(self) -> None:
        for profile, volume, height in (
            (cylinder_profile(), 12 * math.pi, 3),
            (hemisphere_profile(), 16 * math.pi / 3, 2),
        ):
            with self.subTest(volume=volume):
                shape = revolve_profile(profile).findSolid()
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids()), 1)
                self.assertAlmostEqual(shape.Volume(), volume)
                box = shape.BoundingBox()
                self.assertAlmostEqual(box.xlen, 4)
                self.assertAlmostEqual(box.ylen, 4)
                self.assertAlmostEqual(box.zmin, 0)
                self.assertAlmostEqual(box.zmax, height)

    def test_example_solid_and_stl_export(self) -> None:
        import cadquery as cq

        namespace = runpy.run_path(str(ROOT / "examples/löpare.py"))
        solid = namespace["build_solid"]()
        shape = solid.findSolid()
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()), 1)
        self.assertGreater(shape.Volume(), 0)
        self.assertAlmostEqual(shape.BoundingBox().zmax, 37.75)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bishop.stl"
            cq.exporters.export(solid, str(path))
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
