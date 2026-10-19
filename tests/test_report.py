import unittest

from chess_pieces_3d import Profile, format_profile


class ReportTests(unittest.TestCase):
    def test_names_do_not_change_geometry_column_positions(self) -> None:
        short = Profile()
        short.line(x=10, name="short")
        long = Profile()
        long.line(x=10, name="a_much_longer_name_than_any_other_column")
        short_rows, long_rows = (
            format_profile(short).splitlines(),
            format_profile(long).splitlines(),
        )
        self.assertEqual(short_rows[0], long_rows[0])
        self.assertEqual(short_rows[1], long_rows[1])
        self.assertEqual(short_rows[2].removesuffix("short"), long_rows[2].split("a_much_")[0])

    def test_arc_columns_and_rounding(self) -> None:
        profile = Profile()
        arc = profile.arc(x=2.5, y=-2, start_tangent=(1, 0), name="tip")
        row = format_profile(profile).splitlines()[-1]
        self.assertIn("arc(cw)", row)
        self.assertIn("(2.5, -2)  tip  r=2.56 centre=(0, -2.56)", row)
        self.assertNotIn("-0", row)
        self.assertAlmostEqual(arc.radius, 2.5625)

    def test_trims_zeros_after_rounding(self) -> None:
        profile = Profile(start=(-0.001, 0))
        profile.line(x=10, y=1.999, name="rounded")
        rows = format_profile(profile).splitlines()
        self.assertIn("(0, 0)", rows[1])
        self.assertIn("(10, 2)", rows[2])
        self.assertNotIn("-0", "\n".join(rows))

    def test_empty_profile(self) -> None:
        self.assertEqual(len(format_profile(Profile()).splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
