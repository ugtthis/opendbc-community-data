import unittest
import json
from pathlib import Path

from markdown_to_json import build_model_variant_list, split_model_and_variant


class MarkdownToJsonTest(unittest.TestCase):
  def test_comma_variant_becomes_list_items(self):
    self.assertEqual(
      split_model_and_variant("GV70 (2.5T Trim, without HDA II) 2022-24"),
      (
        "GV70",
        "(2.5T Trim, without HDA II)",
        ["2.5T Trim", "without HDA II"],
      ),
    )

  def test_multi_region_variant_becomes_separate_region_items(self):
    self.assertEqual(
      build_model_variant_list(["Southeast Asia and Europe only"]),
      ["Southeast Asia only", "Europe only"],
    )

  def test_single_region_variant_stays_as_one_item(self):
    self.assertEqual(
      build_model_variant_list(["Korea only"]),
      ["Korea only"],
    )

  def test_feature_and_region_variant_become_separate_items(self):
    self.assertEqual(
      build_model_variant_list(["with HDA II, Korea only"]),
      ["with HDA II", "Korea only"],
    )

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


if __name__ == "__main__":
  unittest.main()
