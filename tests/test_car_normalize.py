import unittest

from car_normalize import (
  build_model_variant_list,
  build_output,
  build_supported_package_list,
  split_model_and_variant,
)


class CarNormalizeTest(unittest.TestCase):
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

  def test_supported_package_or_values_become_list_items(self):
    self.assertEqual(
      build_supported_package_list("AcuraWatch Plus or Advance Package"),
      ["AcuraWatch Plus", "Advance Package"],
    )

  def test_supported_package_keeps_ampersand_as_one_requirement(self):
    self.assertEqual(
      build_supported_package_list("Adaptive Cruise Control (ACC) & Lane Assist"),
      ["Adaptive Cruise Control (ACC) & Lane Assist"],
    )

  def test_supported_package_keeps_comma_without_clause_with_option(self):
    self.assertEqual(
      build_supported_package_list(
        "Premier or Premier Redline Trim, without Super Cruise Package"
      ),
      ["Premier", "Premier Redline Trim, without Super Cruise Package"],
    )

  def test_supported_package_keeps_except_clause_as_one_requirement(self):
    self.assertEqual(
      build_supported_package_list("All except Type S"),
      ["All except Type S"],
    )

  def test_build_output_keeps_footnotes_before_cars(self):
    output = build_output(
      [{"name": "foo"}],
      "openpilot",
      "https://example.com/CARS.md",
      {1: "Example footnote"},
      generator="markdown_to_json.py",
      include_footnote_definitions=True,
    )
    self.assertEqual(list(output.keys()), ["_metadata", "footnote_definitions", "cars"])
    self.assertEqual(output["footnote_definitions"], {1: "Example footnote"})

  def test_build_output_can_omit_footnote_definitions(self):
    output = build_output(
      [{"name": "foo"}],
      "wip",
      "data/wip",
      {},
      generator="toml_to_json.py",
      include_footnote_definitions=False,
    )
    self.assertNotIn("footnote_definitions", output)


if __name__ == "__main__":
  unittest.main()
