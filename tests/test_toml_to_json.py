import json
import tempfile
import unittest
from pathlib import Path

from toml_to_json import build_wip_json


class TomlToJsonTest(unittest.TestCase):
  def test_only_example_toml_is_ignored_and_emits_empty_output(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      wip_dir = temp_path / "wip"
      wip_dir.mkdir()
      output_path = temp_path / "wip.json"
      (wip_dir / "example.toml").write_text(
        """
[[cars]]
make = "Hyundai"
model = "Ioniq 6 2023-24"
hardware_needed = "comma four"
supported_package = "Highway Driving Assist"
acc = "Stock"
no_acc_below = "0 mph"
no_alc_below = "0 mph"
auto_resume_available = true
branch_name = "hyundai-ioniq6-wip"
branch_url = "https://github.com/example/opendbc/tree/hyundai-ioniq6-wip"
branch_desc = "Active branch"
wiki_url = "https://github.com/commaai/openpilot/wiki/Hyundai"
discord_url = "https://discord.com/channels/example"
discord_name = "example-user"
        """.strip(),
        encoding="utf-8",
      )

      total = build_wip_json(wip_dir, output_path)
      payload = json.loads(output_path.read_text(encoding="utf-8"))

      self.assertEqual(total, 0)
      self.assertEqual(payload["_metadata"]["total"], "0 cars")
      self.assertEqual(payload["cars"], [])

  def test_build_wip_json_generates_expected_shape(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      wip_dir = temp_path / "wip"
      wip_dir.mkdir()
      output_path = temp_path / "wip.json"
      (wip_dir / "hyundai.toml").write_text(
        """
[[cars]]
make = "Hyundai"
model = "Ioniq 6 2023-24"
supported_package = "Highway Driving Assist"
hardware_needed = "comma four"
acc = "Stock"
no_acc_below = "0 mph"
no_alc_below = "0 mph"
auto_resume_available = true
branch_name = "hyundai-ioniq6-wip"
branch_url = "https://github.com/example/opendbc/tree/hyundai-ioniq6-wip"
branch_desc = "Active branch"
wiki_url = "https://github.com/commaai/openpilot/wiki/Hyundai"
extra_resource_url = "https://github.com/example/opendbc/pull/123"
important_notes = ["Needs more logs"]
discord_url = "https://discord.com/channels/example"
discord_name = "example-user"
        """.strip(),
        encoding="utf-8",
      )

      total = build_wip_json(wip_dir, output_path)
      payload = json.loads(output_path.read_text(encoding="utf-8"))

      self.assertEqual(total, 1)
      self.assertEqual(payload["_metadata"]["generator"], "toml_to_json.py")
      self.assertEqual(payload["_metadata"]["source"], "wip")
      self.assertEqual(payload["_metadata"]["url"], "data/wip")
      self.assertEqual(len(payload["cars"]), 1)

      car = payload["cars"][0]
      self.assertEqual(car["make"], "Hyundai")
      self.assertEqual(car["model"], "Ioniq 6")
      self.assertEqual(car["year_list"], [2023, 2024])
      self.assertEqual(car["supported_package_list"], ["Highway Driving Assist"])
      self.assertEqual(car["branch_name"], "hyundai-ioniq6-wip")
      self.assertEqual(car["branch_url"], "https://github.com/example/opendbc/tree/hyundai-ioniq6-wip")
      self.assertEqual(car["branch_desc"], "Active branch")
      self.assertEqual(car["wiki_url"], "https://github.com/commaai/openpilot/wiki/Hyundai")
      self.assertEqual(car["extra_resource_url"], "https://github.com/example/opendbc/pull/123")
      self.assertEqual(car["important_notes"], ["Needs more logs"])
      self.assertEqual(car["discord_name"], "example-user")
      self.assertEqual(car["discord_url"], "https://discord.com/channels/example")
      self.assertTrue(car["key"])

  def test_make_mismatch_filename_is_rejected(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      wip_dir = temp_path / "wip"
      wip_dir.mkdir()
      output_path = temp_path / "wip.json"
      (wip_dir / "toyota.toml").write_text(
        """
[[cars]]
make = "Honda"
model = "Civic 2022"
hardware_needed = "comma four"
supported_package = "All"
acc = "Stock"
no_acc_below = "0 mph"
no_alc_below = "0 mph"
auto_resume_available = true
branch_name = "civic"
branch_url = "https://github.com/example/opendbc/tree/civic"
branch_desc = "Active branch"
wiki_url = "https://github.com/commaai/openpilot/wiki/Honda"
discord_url = "https://discord.com/channels/example"
discord_name = "example-user"
        """.strip(),
        encoding="utf-8",
      )

      with self.assertRaisesRegex(ValueError, "does not match filename"):
        build_wip_json(wip_dir, output_path)

  def test_missing_required_fields_are_rejected(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      wip_dir = temp_path / "wip"
      wip_dir.mkdir()
      output_path = temp_path / "wip.json"
      (wip_dir / "hyundai.toml").write_text(
        """
[[cars]]
make = "Hyundai"
model = "Ioniq 6 2023-24"
supported_package = "Highway Driving Assist"
acc = "Stock"
no_acc_below = "0 mph"
no_alc_below = "0 mph"
auto_resume_available = true
branch_desc = "Missing required hardware"
        """.strip(),
        encoding="utf-8",
      )

      with self.assertRaisesRegex(
        ValueError,
        "missing required field\\(s\\): hardware_needed, branch_name, branch_url, wiki_url, discord_url, discord_name",
      ):
        build_wip_json(wip_dir, output_path)

  def test_model_years_must_be_after_variant(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      wip_dir = temp_path / "wip"
      wip_dir.mkdir()
      output_path = temp_path / "wip.json"
      (wip_dir / "tesla.toml").write_text(
        """
[[cars]]
make = "Tesla"
model = "Cybertruck 2077 (with hw10)"
hardware_needed = "comma X"
supported_package = "All"
acc = "openpilot"
no_acc_below = "0 mph"
no_alc_below = "0 mph"
auto_resume_available = true
branch_name = "the-cybertruck"
branch_url = "https://github.com/elon/openpilot/tree/the-cybertruck"
branch_desc = "Active branch"
wiki_url = "https://github.com/commaai/openpilot/wiki/Tesla"
discord_url = "https://discord.com/channels/example"
discord_name = "example-user"
        """.strip(),
        encoding="utf-8",
      )

      with self.assertRaisesRegex(
        ValueError,
        "Tesla Cybertruck 2077 \\(with hw10\\): model must include years at the end.*place years after the closing parenthesis",
      ):
        build_wip_json(wip_dir, output_path)


if __name__ == "__main__":
  unittest.main()
