import unittest
import json
from pathlib import Path

from markdown_to_json import (
  find_first_compatible_table_header,
  parse_car_row,
)


class MarkdownToJsonTest(unittest.TestCase):
  def test_rows_with_extra_unmapped_columns_still_parse(self):
    headers = [
      "Make",
      "Model",
      "Supported Package",
      "ACC",
      "No ACC accel below",
      "No ALC below",
      "Hardware Needed",
      "Resume from stop",
      "Extra",
    ]
    row = [
      "Honda",
      "Civic 2022",
      "All",
      "Stock",
      "0 mph",
      "0 mph",
      "comma four",
      "[![star](assets/icon-star-full.svg)](##)",
      "ignored",
    ]

    col_map, _ = find_first_compatible_table_header([
      "|" + "|".join(headers) + "|",
      "|" + "|".join(["---"] * len(headers)) + "|",
    ])
    car, missing_required_fields = parse_car_row(row, col_map)

    self.assertEqual(missing_required_fields, ())
    self.assertEqual(car["make"], "Honda")
    self.assertEqual(car["model"], "Civic")

  def test_generated_cars_have_consistent_variant_list(self):
    for json_path in sorted(Path("data").glob("*.json")):
      payload = json.loads(json_path.read_text(encoding="utf-8"))
      if not isinstance(payload, dict) or not isinstance(payload.get("cars"), list):
        continue

      for index, car in enumerate(payload["cars"]):
        with self.subTest(file=json_path.name, row=index):
          self.assertIn("model_variant_list", car)
          self.assertIsInstance(car["model_variant_list"], list)
          has_valid_items = all(
            isinstance(item, str) and item.strip()
            for item in car["model_variant_list"]
          )
          self.assertTrue(has_valid_items)

          variant = car.get("model_variant")
          if not variant:
            self.assertEqual(car["model_variant_list"], [])
          else:
            self.assertGreater(len(car["model_variant_list"]), 0)

  def test_generated_cars_have_consistent_supported_package_list(self):
    for json_path in sorted(Path("data").glob("*.json")):
      payload = json.loads(json_path.read_text(encoding="utf-8"))
      if not isinstance(payload, dict) or not isinstance(payload.get("cars"), list):
        continue

      for index, car in enumerate(payload["cars"]):
        with self.subTest(file=json_path.name, row=index):
          self.assertIn("supported_package_list", car)
          self.assertIsInstance(car["supported_package_list"], list)
          self.assertTrue(car["supported_package_list"])


if __name__ == "__main__":
  unittest.main()
