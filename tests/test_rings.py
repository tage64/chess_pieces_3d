import importlib.util
import math
import subprocess
import sys
import unittest
from collections import defaultdict
from typing import TYPE_CHECKING

from chess_pieces_3d import GeometryError, Profile, SandPatch, ring_sand

if TYPE_CHECKING:
    import cadquery as cq


def cylinder_profile() -> Profile:
    profile = Profile(start=(4 / math.pi, 0))
    profile.line(y=2 * math.sqrt(3))
    return profile


def centers(patch: SandPatch) -> list[tuple[float, float, float]]:
    return [ball.Center().toTuple() for ball in patch.balls]


@unittest.skipUnless(importlib.util.find_spec("OCP"), "OCP is unavailable")
class RingSandTests(unittest.TestCase):
    def assertSingleSolid(self, shape: cq.Shape) -> None:
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()), 1)

    def test_full_cylinder_is_staggered_without_duplicate_seam_balls(self) -> None:
        profile = cylinder_profile()
        patch = ring_sand(profile, profile.start, profile.end, spacing=1)
        self.assertEqual(patch.count, 32)
        self.assertEqual(patch.count, len(patch.balls))
        self.assertAlmostEqual(patch.area, 16 * math.sqrt(3))
        self.assertAlmostEqual(patch.density_per_cm2, 100 / (math.sqrt(3) / 2))
        rings: dict[float, list[float]] = defaultdict(list)
        points = centers(patch)
        for x, y, z in points:
            self.assertAlmostEqual(math.hypot(x, y), 4 / math.pi)
            rings[round(z, 8)].append(math.atan2(y, x) % math.tau)
        self.assertEqual(len(rings), 4)
        for row, (z, angles) in enumerate(sorted(rings.items())):
            self.assertEqual(len(angles), 8)
            self.assertAlmostEqual(z, (row + 0.5) * math.sqrt(3) / 2)
            for column, theta in enumerate(angles):
                expected = (column + 0.5 * (row % 2)) * math.tau / 8
                self.assertAlmostEqual(math.remainder(theta - expected, math.tau), 0)
        for index, point in enumerate(points):
            for other in points[index + 1 :]:
                self.assertGreater(math.dist(point, other), 0.4)
        for ball in patch.balls:
            self.assertTrue(ball.isValid())
            self.assertAlmostEqual(ball.Volume(), 4 * math.pi * 0.2**3 / 3)

    def test_partial_angle_and_rotated_start(self) -> None:
        profile = cylinder_profile()
        patch = ring_sand(profile, profile.start, profile.end, 90, start_angle=30, spacing=1)
        self.assertEqual(patch.count, 8)
        self.assertAlmostEqual(patch.area, 4 * math.sqrt(3))
        self.assertAlmostEqual(patch.density_per_cm2, 100 / (math.sqrt(3) / 2))
        rings: dict[float, list[float]] = defaultdict(list)
        for x, y, z in centers(patch):
            theta = math.degrees(math.atan2(y, x))
            self.assertGreater(theta, 30)
            self.assertLess(theta, 120)
            rings[round(z, 8)].append(theta)
        for row, angles in enumerate(rings.values()):
            for column, theta in enumerate(angles):
                self.assertAlmostEqual(theta, 30 + (column + 0.25 + 0.5 * (row % 2)) * 45)

    def test_angle_can_cross_zero_degrees(self) -> None:
        profile = cylinder_profile()
        patch = ring_sand(profile, profile.start, profile.end, 30, start_angle=350)
        for x, y, _ in centers(patch):
            local_angle = (math.degrees(math.atan2(y, x)) - 350) % 360
            self.assertGreater(local_angle, 0)
            self.assertLess(local_angle, 30)

    def test_variable_circumference_and_interior_line_points(self) -> None:
        profile = Profile(start=(2, 0))
        profile.line(x=6, y=8)
        patch = ring_sand(profile, (3, 2), (5, 6), spacing=1)
        self.assertAlmostEqual(patch.area, math.tau * 4 * math.sqrt(20))
        rings: dict[float, int] = defaultdict(int)
        for x, y, z in centers(patch):
            self.assertGreater(z, 2)
            self.assertLess(z, 6)
            r = math.hypot(x, y)
            self.assertAlmostEqual(r, 2 + z / 2)
            rings[round(z, 8)] += 1
        self.assertGreater(len(set(rings.values())), 1)
        for z, count in rings.items():
            self.assertEqual(count, math.floor(math.tau * (2 + z / 2) + 0.5))
        heights = sorted(rings)
        gaps = [b - a for a, b in zip(heights[:-1], heights[1:], strict=True)]
        self.assertLess(max(gaps) - min(gaps), 1e-7)

    def test_exact_spherical_band_area_with_interior_arc_points(self) -> None:
        profile = Profile(start=(5, 0))
        profile.arc(x=0, y=5, start_tangent=(0, 1))
        start = (5 * math.cos(math.pi / 6), 2.5)
        end = (2.5, 5 * math.sin(math.pi / 3))
        patch = ring_sand(profile, start, end, 120)
        expected = math.radians(120) * 25 * (math.sin(math.pi / 3) - 0.5)
        self.assertAlmostEqual(patch.area, expected)
        for x, y, z in centers(patch):
            self.assertAlmostEqual(math.sqrt(x * x + y * y + z * z), 5)
            self.assertGreater(z, start[1])
            self.assertLess(z, end[1])

    def test_clockwise_arc_and_reversed_traversal_have_same_area(self) -> None:
        profile = Profile(start=(0, 5))
        profile.arc(x=5, y=0, start_tangent=(1, 0))
        patch = ring_sand(profile, profile.start, profile.end)
        self.assertAlmostEqual(patch.area, 50 * math.pi)
        for x, y, z in centers(patch):
            self.assertAlmostEqual(math.sqrt(x * x + y * y + z * z), 5)

    def test_arc_length_sampling_continues_across_segment_boundaries(self) -> None:
        profile = Profile(start=(5, 0))
        profile.arc(x=3, y=4, start_tangent=(0, 1))
        profile.arc(x=0, y=5)
        patch = ring_sand(profile, profile.start, profile.end)
        self.assertAlmostEqual(patch.area, 50 * math.pi)
        rings = sorted({round(z, 9) for _, _, z in centers(patch)})
        distances = [5 * math.asin(z / 5) for z in rings]
        for a, b in zip(distances[:-1], distances[1:], strict=True):
            self.assertAlmostEqual(b - a, distances[1] - distances[0], places=7)
        joint_patch = ring_sand(profile, (3, 4), (0, 5))
        self.assertAlmostEqual(joint_patch.area, 10 * math.pi)

    def test_fractional_bounds_use_whole_interval_arc_length(self) -> None:
        profile = Profile(start=(5, 0))
        profile.arc(x=3, y=4, start_tangent=(0, 1))
        profile.arc(x=0, y=5)
        patch = ring_sand(profile, profile.point_at(0.2), profile.point_at(0.85))
        start_angle, end_angle = 0.2 * math.pi / 2, 0.85 * math.pi / 2
        expected = 50 * math.pi * (math.sin(end_angle) - math.sin(start_angle))
        self.assertAlmostEqual(patch.area, expected)
        for x, y, z in centers(patch):
            self.assertAlmostEqual(math.sqrt(x * x + y * y + z * z), 5)
            self.assertGreater(z, 5 * math.sin(start_angle))
            self.assertLess(z, 5 * math.sin(end_angle))

    def test_flat_annulus_area(self) -> None:
        profile = Profile(start=(1, 0))
        profile.line(x=3)
        patch = ring_sand(profile, profile.start, profile.end)
        self.assertAlmostEqual(patch.area, 8 * math.pi)
        for x, y, z in centers(patch):
            self.assertAlmostEqual(z, 0)
            self.assertGreater(math.hypot(x, y), 1)
            self.assertLess(math.hypot(x, y), 3)

    def test_closed_profile_includes_both_disks_but_skips_axis(self) -> None:
        profile = Profile()
        profile.line(x=2)
        profile.line(y=3)
        profile.line(x=0)
        profile.line(y=0)
        patch = ring_sand(profile, profile.start, profile.end)
        self.assertAlmostEqual(patch.area, 20 * math.pi)
        self.assertTrue(all(math.hypot(x, y) > 0 for x, y, _ in centers(patch)))

    def test_balls_can_be_fused_to_a_partially_revolved_solid(self) -> None:
        import cadquery as cq

        profile = cylinder_profile()
        patch = ring_sand(profile, profile.start, profile.end, 90)
        base = cq.Solid.makeCylinder(4 / math.pi, 2 * math.sqrt(3), angleDegrees=90)
        result = base.fuse(*patch.balls)
        self.assertSingleSolid(result)
        self.assertGreater(result.Volume(), base.Volume())
        self.assertAlmostEqual(base.cut(result).Volume(), 0, places=7)

    def test_pole_region_fuses_without_duplicate_axis_balls(self) -> None:
        import cadquery as cq

        profile = Profile(start=(5, 0))
        profile.arc(x=0, y=5, start_tangent=(0, 1))
        patch = ring_sand(profile, profile.start, profile.end, spacing=1)
        points = centers(patch)
        self.assertEqual(len(points), len(set(points)))
        self.assertTrue(all(math.hypot(x, y) > 0 for x, y, _ in points))
        base = cq.Solid.makeSphere(5)  # Upper hemisphere.
        result = base.fuse(*patch.balls)
        self.assertSingleSolid(result)
        self.assertGreater(result.Volume(), base.Volume())


class RingValidationTests(unittest.TestCase):
    def test_invalid_parameters(self) -> None:
        profile = cylinder_profile()
        for angle in (0, -1, 361, math.nan, math.inf):
            with self.subTest(angle=angle), self.assertRaises(GeometryError):
                ring_sand(profile, profile.start, profile.end, angle)
        for value in (0, -1, math.nan, math.inf):
            with self.subTest(spacing=value), self.assertRaises(GeometryError):
                ring_sand(profile, profile.start, profile.end, spacing=value)
            with self.subTest(radius=value), self.assertRaises(GeometryError):
                ring_sand(profile, profile.start, profile.end, radius=value)
        with self.assertRaisesRegex(GeometryError, "diameter"):
            ring_sand(profile, profile.start, profile.end, spacing=0.4)
        with self.assertRaisesRegex(GeometryError, "start_angle"):
            ring_sand(profile, profile.start, profile.end, start_angle=math.inf)

    def test_off_profile_reversed_empty_and_nonfinite_points(self) -> None:
        profile = cylinder_profile()
        for start, end in (
            ((9, 0), profile.end),
            (profile.start, (9, 1)),
            (profile.end, profile.start),
            (profile.start, profile.start),
            ((math.nan, 0), profile.end),
        ):
            with self.subTest(start=start, end=end), self.assertRaises(GeometryError):
                ring_sand(profile, start, end)
        with self.assertRaises(GeometryError):
            ring_sand(Profile(), (0, 0), (1, 1))

    def test_rejects_ambiguous_points(self) -> None:
        profile = Profile(start=(1, 0))
        profile.line(x=3, y=2)
        profile.line(x=1)
        profile.line(x=3, y=0)
        with self.assertRaisesRegex(GeometryError, "ambiguous"):
            ring_sand(profile, (2, 1), profile.end)

    def test_rejects_axis_only_and_negative_radius_regions(self) -> None:
        axis = Profile()
        axis.line(y=2)
        with self.assertRaisesRegex(GeometryError, "no revolved surface area"):
            ring_sand(axis, axis.start, axis.end)
        negative = Profile(start=(-1, 0))
        negative.line(y=2)
        with self.assertRaisesRegex(GeometryError, "negative X"):
            ring_sand(negative, negative.start, negative.end)
        crossing = Profile(start=(0, math.sqrt(3)))
        crossing.arc(x=0, y=-math.sqrt(3), start_tangent=(-math.sqrt(3), -1))
        with self.assertRaisesRegex(GeometryError, "negative X"):
            ring_sand(crossing, crossing.start, crossing.end)

    def test_import_and_validation_do_not_load_cad(self) -> None:
        code = (
            "import sys\n"
            "from chess_pieces_3d import Profile, SandPatch, ring_sand, GeometryError\n"
            "p = Profile()\n"
            "p.line(x=2)\n"
            "try: ring_sand(p, p.start, p.end, 0)\n"
            "except GeometryError: pass\n"
            "else: raise AssertionError('invalid angle accepted')\n"
            "assert 'cadquery' not in sys.modules\n"
            "assert 'OCP' not in sys.modules\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
