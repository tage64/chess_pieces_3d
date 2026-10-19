import math
import random
import unittest

from chess_pieces_3d import (
    TANGENT_X,
    TANGENT_Y,
    Arc,
    GeometryError,
    Point,
    Profile,
    Turn,
    Vector,
)


def rotate(vector: Vector, angle: float) -> Vector:
    x, y = vector
    return (
        x * math.cos(angle) - y * math.sin(angle),
        x * math.sin(angle) + y * math.cos(angle),
    )


def endpoint(start: Point, tangent: Vector, radius: float, angle: float) -> Point:
    sign = 1 if angle > 0 else -1
    center = start[0] - sign * radius * tangent[1], start[1] + sign * radius * tangent[0]
    radial = rotate((start[0] - center[0], start[1] - center[1]), angle)
    return center[0] + radial[0], center[1] + radial[1]


class GeometryTests(unittest.TestCase):
    def assertPoint(self, actual: Point, expected: Point) -> None:
        self.assertAlmostEqual(actual[0], expected[0], places=7)
        self.assertAlmostEqual(actual[1], expected[1], places=7)

    def test_lines(self) -> None:
        profile = Profile(start=(1, 2))
        bottom = profile.line(x=10)
        rim = profile.line(dy=2)
        diagonal = profile.line(dx=-3, y=8, name="diagonal")
        self.assertPoint(bottom.end, (10, 2))
        self.assertPoint(rim.end, (10, 4))
        self.assertPoint(diagonal.end, (7, 8))
        self.assertPoint(profile.last_tangent, (-0.6, 0.8))
        self.assertEqual([s.name for s in profile.segments], ["line_1", "line_2", "diagonal"])
        self.assertPoint(profile.start, (1, 2))
        self.assertPoint(profile.end, diagonal.end)

    def test_invalid_lines_do_not_change_profile(self) -> None:
        profile = Profile()
        for kwargs in ({}, {"dx": 0}, {"x": 1, "dx": 2}, {"y": 1, "dy": 2}, {"x": math.inf}):
            with self.subTest(kwargs=kwargs), self.assertRaises(GeometryError):
                profile.line(
                    x=kwargs.get("x"),
                    dx=kwargs.get("dx"),
                    y=kwargs.get("y"),
                    dy=kwargs.get("dy"),
                )
            self.assertEqual(profile.segments, ())
        with self.assertRaisesRegex(GeometryError, "no tangent"):
            _ = profile.last_tangent
        with self.assertRaises(GeometryError):
            Profile(start=(math.nan, 0))

    def test_arc_from_start_tangent(self) -> None:
        profile = Profile()
        arc = profile.arc(x=2, y=2, start_tangent=(4, 0))
        self.assertPoint(arc.center, (0, 2))
        self.assertAlmostEqual(arc.radius, 2)
        self.assertAlmostEqual(arc.sweep, math.pi / 2)
        self.assertEqual(arc.turn, "ccw")
        self.assertPoint(arc.start_tangent, TANGENT_X)
        self.assertPoint(arc.end_tangent, TANGENT_Y)
        self.assertPoint(profile.last_tangent, TANGENT_Y)

    def test_arc_from_end_tangent_does_not_constrain_start(self) -> None:
        profile = Profile(start=(-1, 0))
        profile.line(x=0)
        arc = profile.arc(x=2, y=2, end_tangent=TANGENT_X)
        self.assertPoint(arc.center, (2, 0))
        self.assertPoint(arc.start_tangent, TANGENT_Y)
        self.assertPoint(arc.end_tangent, TANGENT_X)
        self.assertEqual(arc.turn, "cw")

    def test_arc_inherits_tangent_and_holds_omitted_axis_without_radius(self) -> None:
        profile = Profile()
        profile.line(dx=1, dy=1)
        arc = profile.arc(x=3)
        self.assertPoint(arc.end, (3, 1))
        self.assertPoint(arc.start_tangent, (math.sqrt(0.5), math.sqrt(0.5)))

    def test_radius_and_one_coordinate(self) -> None:
        arc = Profile().arc(dx=-2, radius=3, start_tangent=TANGENT_Y)
        self.assertPoint(arc.end, (-2, math.sqrt(8)))
        self.assertPoint(arc.center, (-3, 0))
        self.assertAlmostEqual(arc.radius, 3)
        arc = Profile().arc(dy=-2, radius=3, start_tangent=TANGENT_X)
        self.assertPoint(arc.end, (math.sqrt(8), -2))
        self.assertEqual(arc.turn, "cw")
        arc = Profile().arc(x=2, radius=3, end_tangent=TANGENT_Y)
        self.assertPoint(arc.end, (2, math.sqrt(8)))
        self.assertPoint(arc.center, (-1, math.sqrt(8)))
        arc = Profile().arc(y=2, radius=3, end_tangent=TANGENT_X)
        self.assertPoint(arc.end, (math.sqrt(8), 2))
        self.assertPoint(arc.center, (math.sqrt(8), -1))

    def test_arc_checks_extra_constraints(self) -> None:
        arc = Profile().arc(
            x=2, y=2, radius=2, start_tangent=TANGENT_X, end_tangent=TANGENT_Y, turn="ccw"
        )
        self.assertAlmostEqual(arc.radius, 2)
        with self.assertRaises(GeometryError):
            Profile().arc(x=2, y=2, radius=3, start_tangent=TANGENT_X)
        with self.assertRaises(GeometryError):
            Profile().arc(x=2, y=2, start_tangent=TANGENT_X, end_tangent=TANGENT_X)
        with self.assertRaises(GeometryError):
            Profile().arc(x=2, y=2, start_tangent=TANGENT_X, turn="cw")

    def test_ambiguous_radius_arc_requires_more_information(self) -> None:
        with self.assertRaisesRegex(GeometryError, "ambiguous"):
            Profile().arc(dx=1, radius=2, start_tangent=TANGENT_X, turn="ccw")

    def test_impossible_and_degenerate_arcs(self) -> None:
        for radius in (0, -1, math.inf, math.nan):
            with self.subTest(radius=radius), self.assertRaises(GeometryError):
                Profile().arc(x=2, y=2, radius=radius, start_tangent=TANGENT_X)
        with self.assertRaisesRegex(GeometryError, "at least one"):
            Profile().arc(radius=2, start_tangent=TANGENT_X)
        with self.assertRaises(GeometryError):
            Profile().arc(x=2, start_tangent=TANGENT_X)
        with self.assertRaises(GeometryError):
            Profile().arc(x=2, y=2, start_tangent=(0, 0))
        with self.assertRaises(GeometryError):
            Profile().arc(x=2, y=2, start_tangent=(math.nan, 0))
        with self.assertRaises(GeometryError):
            Profile().arc(x=2, y=2)
        with self.assertRaises(GeometryError):
            Profile().arc(y=2, start_tangent=TANGENT_X)  # Semicircle.
        with self.assertRaises(GeometryError):
            Profile().arc(x=-1, y=1, start_tangent=TANGENT_X)  # Major arc.
        with self.assertRaises(GeometryError):
            Profile().arc(x=-8, radius=3, start_tangent=TANGENT_Y)

    def test_arc_pair_example(self) -> None:
        profile = Profile()
        profile.line(x=10)
        profile.line(dy=2)
        pair = profile.arc_pair(
            x=8,
            dy=2.5,
            end_tangent=TANGENT_Y,
            turns=("ccw", "cw"),
            radius_ratio=2,
            name="base_transition",
        )
        self.assertPoint(pair.start, (10, 2))
        self.assertPoint(pair.first.end, (26 / 3, 11 / 3))
        self.assertPoint(pair.end, (8, 4.5))
        self.assertAlmostEqual(pair.first.radius, 41 / 24)
        self.assertAlmostEqual(pair.second.radius, 41 / 48)
        self.assertPoint(pair.first.center, (199 / 24, 2))
        self.assertPoint(pair.second.center, (425 / 48, 4.5))
        self.assertPoint(pair.first.end_tangent, pair.second.start_tangent)
        self.assertPoint(pair.start_tangent, TANGENT_Y)
        self.assertPoint(pair.end_tangent, TANGENT_Y)
        self.assertEqual(profile.segments[-2:], (pair.first, pair.second))

    def test_failed_pair_is_atomic_and_does_not_reserve_name(self) -> None:
        profile = Profile(start=(10, 2))
        with self.assertRaisesRegex(GeometryError, "base_transition"):
            profile.arc_pair(
                x=8,
                dy=2.5,
                start_tangent=TANGENT_Y,
                end_tangent=TANGENT_Y,
                turns=("cw", "ccw"),
                radius_ratio=2,
                name="base_transition",
            )
        self.assertEqual(profile.segments, ())
        self.assertPoint(profile.end, (10, 2))
        profile.arc_pair(
            x=8,
            dy=2.5,
            start_tangent=TANGENT_Y,
            end_tangent=TANGENT_Y,
            turns=("ccw", "cw"),
            radius_ratio=2,
            name="base_transition",
        )
        with self.assertRaisesRegex(GeometryError, "duplicate"):
            profile.line(dx=1, name="base_transition.1")
        with self.assertRaisesRegex(GeometryError, "duplicate"):
            profile.line(dx=1, name="base_transition")

    def test_invalid_pair_constraints(self) -> None:
        for ratio in (0, -1, math.inf, math.nan):
            with self.subTest(ratio=ratio), self.assertRaises(GeometryError):
                Profile().arc_pair(
                    x=-2,
                    y=2.5,
                    start_tangent=TANGENT_Y,
                    end_tangent=TANGENT_Y,
                    turns=("ccw", "cw"),
                    radius_ratio=ratio,
                )
        with self.assertRaisesRegex(GeometryError, "opposite"):
            Profile().arc_pair(
                x=-2,
                y=2.5,
                start_tangent=TANGENT_Y,
                end_tangent=TANGENT_Y,
                turns=("ccw", "ccw"),
                radius_ratio=2,
            )

    def test_names(self) -> None:
        profile = Profile()
        profile.line(x=1, name="line_2")
        self.assertEqual(profile.line(x=2).name, "line_1")
        self.assertEqual(profile.line(x=3).name, "line_3")
        for name in ("line_2", "", "  ", "a\nb", "a\tb"):
            with self.subTest(name=name), self.assertRaises(GeometryError):
                profile.line(x=4, name=name)
        profile.line(x=4, name="pair.1")
        with self.assertRaisesRegex(GeometryError, "duplicate"):
            profile.arc_pair(
                x=0,
                y=2,
                end_tangent=TANGENT_Y,
                turns=("ccw", "cw"),
                radius_ratio=2,
                name="pair",
            )

    def test_generated_single_arcs(self) -> None:
        rng = random.Random(29)
        for _ in range(100):
            start = (rng.uniform(-10, 10), rng.uniform(-10, 10))
            angle = rng.choice((-1, 1)) * rng.uniform(0.1, 3)
            tangent = rotate(TANGENT_X, rng.uniform(-math.pi, math.pi))
            radius = rng.uniform(0.5, 10)
            end = endpoint(start, tangent, radius, angle)
            arrival = rotate(tangent, angle)
            for from_start in (True, False):
                with self.subTest(start=start, angle=angle, from_start=from_start):
                    arc = Profile(start).arc(
                        x=end[0],
                        y=end[1],
                        start_tangent=tangent if from_start else None,
                        end_tangent=None if from_start else arrival,
                    )
                    self.assertAlmostEqual(arc.radius, radius, places=7)
                    self.assertAlmostEqual(arc.sweep, abs(angle), places=7)
                    self.assertPoint(arc.start_tangent, tangent)
                    self.assertPoint(arc.end_tangent, arrival)

    def test_generated_arc_pairs(self) -> None:
        rng = random.Random(73)
        for _ in range(100):
            start = (rng.uniform(-10, 10), rng.uniform(-10, 10))
            tangent = rotate(TANGENT_X, rng.uniform(-math.pi, math.pi))
            first_radius, second_radius = rng.uniform(0.5, 10), rng.uniform(0.5, 10)
            angle1 = rng.choice((-1, 1)) * rng.uniform(0.1, 2.8)
            angle2 = -math.copysign(rng.uniform(0.1, 2.8), angle1)
            join = endpoint(start, tangent, first_radius, angle1)
            join_tangent = rotate(tangent, angle1)
            end = endpoint(join, join_tangent, second_radius, angle2)
            end_tangent = rotate(join_tangent, angle2)
            turns: tuple[Turn, Turn] = ("ccw", "cw") if angle1 > 0 else ("cw", "ccw")
            with self.subTest(start=start, angle1=angle1, angle2=angle2):
                pair = Profile(start).arc_pair(
                    x=end[0],
                    y=end[1],
                    start_tangent=tangent,
                    end_tangent=end_tangent,
                    turns=turns,
                    radius_ratio=first_radius / second_radius,
                )
                self.assertAlmostEqual(pair.first.radius, first_radius, places=7)
                self.assertAlmostEqual(pair.second.radius, second_radius, places=7)
                self.assertPoint(pair.first.end, join)
                self.assertPoint(pair.end_tangent, end_tangent)
                self.assertPoint(pair.first.end_tangent, pair.second.start_tangent)

    def test_direct_arc_validation(self) -> None:
        with self.assertRaises(GeometryError):
            Arc((0, 0), (2, 2), (0, 1), "cw", "invalid")


if __name__ == "__main__":
    unittest.main()
