import math
import random
import unittest

from test_geometry import endpoint, rotate

from chess_pieces_3d import TANGENT_Y, GeometryError, Point, Profile, Turn


class ConstructionTests(unittest.TestCase):
    def assertPoint(self, actual: Point, expected: Point) -> None:
        self.assertAlmostEqual(actual[0], expected[0], places=8)
        self.assertAlmostEqual(actual[1], expected[1], places=8)

    def test_arc_line(self) -> None:
        profile = Profile(start=(6.5, 20.25))
        arc, line = profile.arc_line(
            x=3.4, dy=2.5, radius=2, turn="ccw", start_tangent=TANGENT_Y, name="collar"
        )
        self.assertPoint(arc.center, (4.5, 20.25))
        self.assertPoint(arc.end, (5.15690852799854, 22.1390397523194))
        self.assertPoint(line.end, (3.4, 22.75))
        self.assertPoint(arc.end_tangent, line.start_tangent)
        self.assertEqual(profile.segments, (arc, line))
        self.assertEqual((arc.name, line.name), ("collar.arc", "collar.line"))

    def test_arc_line_inherits_tangent(self) -> None:
        profile = Profile(start=(6.5, 19.25))
        profile.line(dy=1)
        arc, _ = profile.arc_line(dx=-3.1, dy=2.5, radius=2, turn="ccw")
        self.assertPoint(arc.start_tangent, TANGENT_Y)

    def test_generated_arc_lines(self) -> None:
        rng = random.Random(42)
        for _ in range(100):
            start = (rng.uniform(-10, 10), rng.uniform(-10, 10))
            tangent = rotate((1, 0), rng.uniform(-math.pi, math.pi))
            radius = rng.uniform(0.5, 10)
            angle = rng.choice((-1, 1)) * rng.uniform(0.1, 3)
            contact = endpoint(start, tangent, radius, angle)
            arrival = rotate(tangent, angle)
            length = rng.uniform(0.5, 10)
            end = (contact[0] + length * arrival[0], contact[1] + length * arrival[1])
            turn: Turn = "ccw" if angle > 0 else "cw"
            with self.subTest(angle=angle, radius=radius):
                arc, line = Profile(start).arc_line(
                    x=end[0], y=end[1], radius=radius, start_tangent=tangent, turn=turn
                )
                self.assertPoint(arc.end, contact)
                self.assertPoint(line.end, end)
                self.assertAlmostEqual(arc.radius, radius)
                self.assertAlmostEqual(arc.sweep, abs(angle))
                self.assertPoint(arc.end_tangent, line.start_tangent)

    def test_extreme_without_fillets(self) -> None:
        profile = Profile(start=(3.4, 22.75))
        before, after = profile.arc_via_extreme(x=2.5, dy=12.3, extreme_x=5.2, name="head")
        self.assertPoint(before.end, (5.2, 28.35927010041785))
        self.assertPoint(before.center, (-4.43997529428936, 28.35927010041785))
        self.assertPoint(before.center, after.center)
        self.assertAlmostEqual(before.radius, 9.63997529428936)
        self.assertPoint(after.end, (2.5, 35.05))
        self.assertEqual((before.name, after.name), ("head.before_extreme", "head.after_extreme"))

    def test_symmetric_extreme_uses_linear_solution(self) -> None:
        profile = Profile(start=(2.5, -math.sqrt(18.75)))
        before, after = profile.arc_via_extreme(x=2.5, y=math.sqrt(18.75), extreme_x=5)
        self.assertPoint(before.end, (5, 0))
        self.assertPoint(before.center, (0, 0))
        self.assertAlmostEqual(before.radius, 5)
        self.assertAlmostEqual(before.radius, after.radius)

    def test_generated_extremes_with_optional_fillets(self) -> None:
        rng = random.Random(11)
        for _ in range(100):
            radius = rng.uniform(5, 15)
            start_radius, end_radius = rng.choice((0, 1)), rng.choice((0, 2))
            start_x, end_x = -radius * rng.uniform(0.3, 0.7), -radius * rng.uniform(0.3, 0.7)
            start = (
                start_x,
                -math.sqrt((radius + start_radius) ** 2 - (start_x - start_radius) ** 2),
            )
            end = (end_x, math.sqrt((radius + end_radius) ** 2 - (end_x - end_radius) ** 2))
            reflect_x, reflect_y = rng.choice((-1, 1)), rng.choice((-1, 1))
            origin = (rng.uniform(-10, 10), rng.uniform(-10, 10))

            start, end, extreme = (
                (origin[0] + reflect_x * point[0], origin[1] + reflect_y * point[1])
                for point in (start, end, (-radius, 0))
            )
            with self.subTest(start_radius=start_radius, end_radius=end_radius, origin=origin):
                profile = Profile(start)
                arcs = profile.arc_via_extreme(
                    x=end[0],
                    y=end[1],
                    extreme_x=extreme[0],
                    start_radius=start_radius,
                    end_radius=end_radius,
                )
                middle = arcs[1:3] if start_radius else arcs[:2]
                self.assertEqual(len(arcs), 2 + bool(start_radius) + bool(end_radius))
                self.assertPoint(arcs[0].start, start)
                self.assertPoint(arcs[-1].end, end)
                self.assertPoint(middle[0].end, extreme)
                for arc in middle:
                    self.assertPoint(arc.center, origin)
                    self.assertAlmostEqual(arc.radius, radius)
                for a, b in zip(arcs[:-1], arcs[1:], strict=True):
                    self.assertPoint(a.end, b.start)
                    self.assertPoint(a.end_tangent, b.start_tangent)
                if start_radius:
                    self.assertAlmostEqual(arcs[0].radius, start_radius)
                    self.assertPoint(arcs[0].start_tangent, (0, reflect_y))
                if end_radius:
                    self.assertAlmostEqual(arcs[-1].radius, end_radius)
                    self.assertPoint(arcs[-1].end_tangent, (0, reflect_y))

    def test_filleted_extreme_checks_incoming_tangent(self) -> None:
        profile = Profile(start=(7, 0))
        profile.line(x=8)
        before = profile.segments
        with self.assertRaisesRegex(GeometryError, "vertical incoming"):
            profile.arc_via_extreme(x=6.5, dy=14, extreme_x=4, start_radius=1, end_radius=2)
        self.assertEqual(profile.segments, before)

    def test_extreme_without_start_fillet_allows_corner(self) -> None:
        profile = Profile(start=(2.4, 22.75))
        profile.line(dx=1)
        profile.arc_via_extreme(x=2.5, dy=12.3, extreme_x=5.2)
        self.assertPoint(profile.end, (2.5, 35.05))

    def test_invalid_constructions_are_atomic(self) -> None:
        profile = Profile(start=(8, 0))
        for radius in (-1, math.inf, math.nan):
            with self.subTest(radius=radius), self.assertRaises(GeometryError):
                profile.arc_via_extreme(x=6.5, dy=14, extreme_x=4, start_radius=radius)
            self.assertEqual(profile.segments, ())
        for extreme_x in (math.inf, math.nan, 8, 7):
            with self.subTest(extreme_x=extreme_x), self.assertRaises(GeometryError):
                profile.arc_via_extreme(x=6.5, dy=14, extreme_x=extreme_x)
            self.assertEqual(profile.segments, ())
        with self.assertRaises(GeometryError):
            profile.arc_via_extreme(x=6.5, extreme_x=4)
        with self.assertRaises(GeometryError):
            profile.arc_via_extreme(x=6.5, dx=1, dy=14, extreme_x=4)
        self.assertEqual(profile.segments, ())

        for radius in (0, -1, math.inf, math.nan):
            with self.subTest(radius=radius), self.assertRaises(GeometryError):
                profile.arc_line(dx=-1, dy=1, radius=radius, turn="ccw", start_tangent=TANGENT_Y)
            self.assertEqual(profile.segments, ())
        with self.assertRaisesRegex(GeometryError, "outside"):
            profile.arc_line(dx=-2, radius=2, turn="ccw", start_tangent=TANGENT_Y)
        with self.assertRaisesRegex(GeometryError, "no tangent"):
            profile.arc_line(dx=-3, dy=2.5, radius=2, turn="ccw")
        self.assertEqual(profile.segments, ())

    def test_compound_names_and_failed_name_reuse(self) -> None:
        profile = Profile(start=(8, 0))
        with self.assertRaises(GeometryError):
            profile.arc_via_extreme(x=6.5, dy=14, extreme_x=7, name="stem")
        arcs = profile.arc_via_extreme(
            x=6.5, dy=14, extreme_x=4, start_radius=1, end_radius=2, name="stem"
        )
        for label in ("stem", *(arc.name for arc in arcs)):
            with self.subTest(label=label), self.assertRaisesRegex(GeometryError, "duplicate"):
                profile.line(dx=1, name=label)
        profile.line(dx=1, name="collar.line")
        before = profile.segments
        with self.assertRaisesRegex(GeometryError, "duplicate"):
            profile.arc_line(dx=-3, dy=2.5, radius=2, turn="ccw", name="collar")
        self.assertEqual(profile.segments, before)


if __name__ == "__main__":
    unittest.main()
