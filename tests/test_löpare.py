import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from chess_pieces_3d import Arc
from chess_pieces_3d.cli import load_profile

ROOT = Path(__file__).resolve().parents[1]


class SpreadsheetPortTests(unittest.TestCase):
    def test_upper_profile_matches_spreadsheet(self) -> None:
        with ZipFile(ROOT / "löpare.xlsx") as workbook:
            sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        values: dict[str, float] = {}
        for cell in sheet.findall(".//m:c", namespace):
            value = cell.find("m:v", namespace)
            if cell.get("t") != "s" and value is not None and value.text is not None:
                values[cell.attrib["r"]] = float(value.text)

        profile = load_profile(ROOT / "examples/löpare.py")
        # The edited base shifts the unchanged upper constructions down by 0.25.
        # Reverse traversal; rows 5 and 10 are degenerate, and the tip was edited.
        rows = [4, 6, 7, 8, 9, 11, 12, 13, 14]
        previous_rows = [3, *rows[:-1]]
        height = 38.25
        self.assertEqual(len(profile.segments), 16)
        for segment, row, previous in zip(
            profile.segments[5:-2], reversed(rows), reversed(previous_rows), strict=True
        ):
            with self.subTest(row=row, segment=segment.name):
                self.assertAlmostEqual(segment.start[0], values[f"B{row}"], places=9)
                self.assertAlmostEqual(segment.start[1], values[f"C{row}"] + height, places=9)
                self.assertAlmostEqual(segment.end[0], values[f"B{previous}"], places=9)
                self.assertAlmostEqual(segment.end[1], values[f"C{previous}"] + height, places=9)
                self.assertGreater(segment.end[1], segment.start[1])
                if isinstance(segment, Arc):
                    self.assertAlmostEqual(segment.radius, values[f"D{row}"], places=9)
                    self.assertAlmostEqual(segment.center[0], values[f"E{row}"], places=9)
                    self.assertAlmostEqual(segment.center[1], values[f"F{row}"] + height, places=9)
                    self.assertEqual(segment.turn, "ccw" if values[f"A{row}"] == 3 else "cw")
        self.assertEqual(profile.start, (0, 0))
        self.assertEqual(profile.segments[0].end, (10, 0))
        self.assertAlmostEqual(profile.segments[-1].start[1], height - 0.5)
        self.assertEqual(profile.end, profile.start)

    def test_edited_dimensions_are_preserved(self) -> None:
        profile = load_profile(ROOT / "examples/löpare.py")
        bottom, wall, first, second, rim = profile.segments[:5]
        self.assertEqual(bottom.end, (10, 0))
        self.assertEqual(wall.end, (10, 1.75))
        self.assertEqual(second.end, (8, 4.75))
        self.assertEqual(rim.end, (8, 6.25))
        self.assertIsInstance(first, Arc)
        self.assertIsInstance(second, Arc)
        assert isinstance(first, Arc) and isinstance(second, Arc)
        self.assertAlmostEqual(first.radius, 13 / 6)
        self.assertAlmostEqual(second.radius, 13 / 12)
        self.assertAlmostEqual(first.end[0], 26 / 3)
        self.assertAlmostEqual(first.end[1], 3.75)
        tip = profile.segments[-2]
        assert isinstance(tip, Arc)
        self.assertAlmostEqual(tip.end[1], 37.75)
        self.assertAlmostEqual(tip.end[1] - tip.start[1], 1.5)
        self.assertAlmostEqual(tip.radius, 17 / 6)


if __name__ == "__main__":
    unittest.main()
