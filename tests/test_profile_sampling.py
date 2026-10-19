import math
import unittest

from chess_pieces_3d import GeometryError, Point, Profile, ProfilePath


class ProfileSamplingTests(unittest.TestCase):
    def assertPoint(self, actual: Point, expected: Point) -> None:
        self.assertAlmostEqual(actual[0], expected[0], places=8)
        self.assertAlmostEqual(actual[1], expected[1], places=8)

    def test_line_fraction_and_length(self) -> None:
        line = Profile(start=(1, 2)).line(dx=3, dy=4)
        self.assertAlmostEqual(line.length, 5)
        self.assertPoint(line.point_at(0.3), (1.9, 3.2))
        self.assertIs(line.point_at(0), line.start)
        self.assertIs(line.point_at(1), line.end)

    def test_arc_fractions_follow_arc_not_chord(self) -> None:
        ccw = Profile(start=(2, 0)).arc(x=0, y=2, start_tangent=(0, 1))
        cw = Profile(start=(0, 2)).arc(x=2, y=0, start_tangent=(1, 0))
        for fraction in (0.2, 0.3, 0.5, 0.85):
            angle = fraction * math.pi / 2
            self.assertPoint(ccw.point_at(fraction), (2 * math.cos(angle), 2 * math.sin(angle)))
            self.assertPoint(cw.point_at(fraction), (2 * math.sin(angle), 2 * math.cos(angle)))
        for arc in (cw, ccw):
            self.assertAlmostEqual(arc.length, math.pi)
            self.assertIs(arc.point_at(0), arc.start)
            self.assertIs(arc.point_at(1), arc.end)

    def test_profile_and_path_weight_segments_by_length(self) -> None:
        profile = Profile()
        first = profile.line(x=1)
        second = profile.line(y=3)
        path = ProfilePath((first, second))
        self.assertEqual(path, (first, second))
        self.assertEqual(tuple(path), profile.segments)
        self.assertIs(path[0], first)
        self.assertIs(path[-1], second)
        self.assertEqual(profile.length, 4)
        self.assertEqual(path.length, 4)
        for target in (profile, path):
            self.assertIs(target.point_at(0), target.start)
            self.assertIs(target.point_at(1), target.end)
            self.assertPoint(target.point_at(0.25), (1, 0))
            self.assertPoint(target.point_at(0.5), (1, 1))
            self.assertPoint(target.point_at(0.85), (1, 2.4))
        profile.line(x=2)
        self.assertEqual(path.length, 4)  # Snapshot, not a view of the builder.
        self.assertEqual(profile.length, 5)

    def test_mixed_line_arc_path(self) -> None:
        profile = Profile()
        line = profile.line(x=2)
        arc = profile.arc(x=3, y=1)
        path = ProfilePath((line, arc))
        self.assertAlmostEqual(path.length, 2 + math.pi / 2)
        self.assertPoint(path.point_at(2 / path.length), line.end)
        distance_on_arc = 0.85 * path.length - line.length
        self.assertPoint(
            path.point_at(0.85), (2 + math.sin(distance_on_arc), 1 - math.cos(distance_on_arc))
        )

    def test_arc_pair_sampling(self) -> None:
        pair = Profile(start=(10, 2)).arc_pair(
            x=8,
            dy=2.5,
            start_tangent=(0, 1),
            end_tangent=(0, 1),
            turns=("ccw", "cw"),
            radius_ratio=2,
        )
        self.assertAlmostEqual(pair.length, pair.first.length + pair.second.length)
        self.assertPoint(pair.point_at(pair.first.length / pair.length), pair.first.end)
        self.assertIs(pair.point_at(0), pair.start)
        self.assertIs(pair.point_at(1), pair.end)

    def test_head_construction_returns_sampleable_path(self) -> None:
        profile = Profile(start=(3.4, 22.75))
        head = profile.arc_via_extreme(x=2.5, dy=12.3, extreme_x=5.2, name="head")
        self.assertIsInstance(head, ProfilePath)
        self.assertEqual(head, profile.segments)
        self.assertPoint(head.point_at(0.2), (4.637160988365793, 25.113546670947212))
        self.assertPoint(head.point_at(0.85), (3.733209623301767, 33.470842459034145))
        for fraction in (0.2, 0.5, 0.85):
            self.assertPoint(head.point_at(fraction), profile.point_at(fraction))

    def test_invalid_fractions_are_rejected_by_geometry(self) -> None:
        profile = Profile()
        line = profile.line(x=2)
        arc = profile.arc(x=3, y=1)
        path = ProfilePath((line, arc))
        pair = Profile(start=(10, 2)).arc_pair(
            x=8,
            dy=2.5,
            start_tangent=(0, 1),
            end_tangent=(0, 1),
            turns=("ccw", "cw"),
            radius_ratio=2,
        )
        for target in (line, arc, profile, path, pair):
            for fraction in (-0.01, 1.01, math.nan, math.inf):
                with self.subTest(target=type(target).__name__, fraction=fraction):
                    with self.assertRaisesRegex(GeometryError, "fraction"):
                        target.point_at(fraction)

    def test_empty_and_disconnected_paths(self) -> None:
        self.assertEqual(Profile().length, 0)
        with self.assertRaises(GeometryError):
            Profile().point_at(0.5)
        with self.assertRaises(GeometryError):
            ProfilePath(())
        first = Profile().line(x=1)
        second = Profile(start=(9, 0)).line(x=10)
        with self.assertRaisesRegex(GeometryError, "connected"):
            ProfilePath((first, second))
        with self.assertRaises(AttributeError):
            object.__setattr__(ProfilePath((first,)), "extra", 1)


if __name__ == "__main__":
    unittest.main()
