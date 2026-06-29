#!/usr/bin/env python3
import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from car_normalize import (
  build_output,
  build_supported_package_list,
  extract_years,
  format_years_abbreviated,
  normalize_whitespace,
  split_model_and_variant,
)

BASE_DIR = Path(__file__).parent
WIP_DIR = BASE_DIR / "data" / "wip"
OUTPUT_PATH = BASE_DIR / "data" / "wip.json"
SOURCE_NAME = "wip"
SOURCE_URL = "data/wip"
REQUIRED_TEXT_FIELDS = (
  "make",
  "model",
  "hardware_needed",
  "supported_package",
  "acc",
  "no_acc_below",
  "no_alc_below",
  "branch_name",
  "branch_url",
  "branch_desc",
  "wiki_url",
  "discord_url",
)
REQUIRED_BOOL_FIELDS = ("auto_resume_available",)
REQUIRED_CONTRIBUTOR_NAME_FIELDS = ("discord_names", "x_names")
EXAMPLE_FILENAMES = {"example.toml"}
KEY_SANITIZE_PATTERN = re.compile(r"[^a-z0-9]+")
NA_SENTINEL = "N/A"


def discover_toml_files(wip_dir: Path) -> list[Path]:
  return sorted(
    path
    for path in wip_dir.glob("*.toml")
    if path.is_file() and path.name not in EXAMPLE_FILENAMES
  )


def slugify(value: str) -> str:
  lowered = value.lower()
  slug = KEY_SANITIZE_PATTERN.sub("-", lowered).strip("-")
  return slug or "unknown"


def is_na(value: str) -> bool:
  return value.strip().upper() == NA_SENTINEL


def parse_github_user(url: str) -> str:
  parsed = urlparse(url.strip())
  if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
    raise ValueError("branch_url must be an http(s) github.com URL")
  path_parts = parsed.path.strip("/").split("/")
  if len(path_parts) < 2 or not path_parts[0]:
    raise ValueError("branch_url must include github user/org and repository path")
  return path_parts[0]


def build_car_key_parts(
  name: str,
  branch_name: str,
  branch_url: str,
  discord_names: list[str] | None,
  x_names: list[str] | None,
) -> list[str]:
  branch_metadata_unavailable = is_na(branch_url) and is_na(branch_name)
  if branch_metadata_unavailable:
    fallback_contributor_names = " ".join((discord_names or []) + (x_names or []))
    return [slugify(name), slugify(fallback_contributor_names)]
  github_user = parse_github_user(branch_url)
  return [slugify(name), slugify(github_user), slugify(branch_name)]


def validate_branch_fields(branch_name: str, branch_url: str) -> None:
  if is_na(branch_url) != is_na(branch_name):
    raise ValueError(f"branch_name and branch_url must both be {NA_SENTINEL} or both be non-{NA_SENTINEL}")


def normalize_text_or_none(car_data: dict, field: str) -> str | None:
  value = car_data.get(field)
  if not isinstance(value, str):
    return None
  normalized = normalize_whitespace(value)
  return normalized or None


def normalize_notes_or_none(value: object) -> list[str] | None:
  if value is None:
    return None
  if not isinstance(value, list):
    raise ValueError("important_notes must be a list of strings")
  notes: list[str] = []
  for note in value:
    if not isinstance(note, str):
      continue
    normalized_note = normalize_whitespace(note)
    if normalized_note:
      notes.append(normalized_note)
  return notes or None


def normalize_contributor_names(value: object) -> list[str] | None:
  if not isinstance(value, list):
    return None

  clean_names = []
  for name in value:
    if not isinstance(name, str):
      return None
    clean_name = normalize_whitespace(name)
    if not clean_name or clean_name != name:
      return None
    clean_names.append(clean_name)

  return clean_names


def is_missing_required_text_field(car_data: dict, field: str) -> bool:
  value = car_data.get(field)
  if not isinstance(value, str):
    return True
  return not bool(normalize_whitespace(value))


def missing_required_fields(car_data: dict) -> list[str]:
  missing = []

  for field in REQUIRED_TEXT_FIELDS:
    if is_missing_required_text_field(car_data, field):
      missing.append(field)

  for field in REQUIRED_BOOL_FIELDS:
    if not isinstance(car_data.get(field), bool):
      missing.append(field)

  for field in REQUIRED_CONTRIBUTOR_NAME_FIELDS:
    if field not in car_data:
      missing.append(field)

  return missing


def validate_make_matches_file(make: str, path: Path) -> None:
  if path.name in EXAMPLE_FILENAMES:
    return
  expected = slugify(path.stem)
  actual = slugify(make)
  if actual != expected:
    raise ValueError(f"make '{make}' does not match filename '{path.stem}.toml'")


def parse_car_entry(path: Path, car_data: dict) -> dict:
  missing_fields = missing_required_fields(car_data)
  if missing_fields:
    raise ValueError(f"missing required field(s): {', '.join(missing_fields)}")

  clean_make = normalize_whitespace(car_data["make"])
  clean_model = normalize_whitespace(car_data["model"])
  validate_make_matches_file(clean_make, path)
  hardware_needed = normalize_whitespace(car_data["hardware_needed"])
  supported_package = normalize_whitespace(car_data["supported_package"])
  acc = normalize_whitespace(car_data["acc"])
  no_acc_below = normalize_whitespace(car_data["no_acc_below"])
  no_alc_below = normalize_whitespace(car_data["no_alc_below"])
  branch_name = normalize_whitespace(car_data["branch_name"])
  branch_url = normalize_whitespace(car_data["branch_url"])
  branch_desc = normalize_whitespace(car_data["branch_desc"])
  wiki_url = normalize_whitespace(car_data["wiki_url"])
  discord_url = normalize_whitespace(car_data["discord_url"])
  discord_names = normalize_contributor_names(car_data["discord_names"])
  x_names = normalize_contributor_names(car_data["x_names"])
  if discord_names is None:
    raise ValueError("discord_names must be a list of names, with no blank entries or extra whitespace")
  if x_names is None:
    raise ValueError("x_names must be a list of names, with no blank entries or extra whitespace")
  if not discord_names and not x_names:
    raise ValueError("at least one contributor is required in discord_names or x_names")
  validate_branch_fields(branch_name, branch_url)

  model, model_variant, model_variant_list = split_model_and_variant(clean_model)
  year_list = extract_years(clean_model)
  if not year_list:
    raise ValueError(
      "model must include years at the end (example: 'Model (variant) 2023-24'). "
      "If using parentheses/variant text, place years after the closing parenthesis."
    )
  years = format_years_abbreviated(year_list)
  model_name_for_display = " ".join(part for part in [model, model_variant, years] if part)
  name = f"{clean_make} {model_name_for_display}".strip()

  important_notes = normalize_notes_or_none(car_data.get("important_notes"))

  key = "-".join(build_car_key_parts(name, branch_name, branch_url, discord_names, x_names))

  return {
    "key": key,
    "name": name,
    "make": clean_make,
    "model": model,
    "model_variant": model_variant,
    "model_variant_list": model_variant_list,
    "years": years,
    "year_list": year_list,
    "hardware_needed": hardware_needed,
    "supported_package": supported_package,
    "supported_package_list": build_supported_package_list(supported_package),
    "acc": acc,
    "no_acc_below": no_acc_below,
    "no_alc_below": no_alc_below,
    "auto_resume_available": car_data["auto_resume_available"],
    "branch_name": branch_name,
    "branch_url": branch_url,
    "branch_desc": branch_desc,
    "wiki_url": wiki_url,
    "discord_url": discord_url,
    "discord_names": discord_names,
    "x_names": x_names,
    "extra_resource_url": normalize_text_or_none(car_data, "extra_resource_url"),
    "video": normalize_text_or_none(car_data, "video"),
    "setup_video": normalize_text_or_none(car_data, "setup_video"),
    "important_notes": important_notes,
  }


def parse_wip_toml(path: Path) -> list[dict]:
  payload = tomllib.loads(path.read_text(encoding="utf-8"))
  car_entries = payload.get("cars")
  if not isinstance(car_entries, list):
    raise ValueError("missing 'cars' list")

  cars: list[dict] = []
  errors: list[str] = []
  for index, car_payload in enumerate(car_entries, start=1):
    if not isinstance(car_payload, dict):
      errors.append(f"car {index}: expected table object")
      continue
    try:
      cars.append(parse_car_entry(path, car_payload))
    except ValueError as error:
      car_label = " ".join(
        value
        for value in (
          normalize_text_or_none(car_payload, "make"),
          normalize_text_or_none(car_payload, "model"),
        )
        if value
      ) or f"car {index}"
      errors.append(f"{car_label}: {error}")

  if errors:
    raise ValueError("\n".join(errors))
  return cars


def build_wip_json(wip_dir: Path, output_path: Path) -> int:
  toml_files = discover_toml_files(wip_dir)
  cars: list[dict] = []
  file_errors: list[str] = []

  for path in toml_files:
    try:
      cars.extend(parse_wip_toml(path))
    except (ValueError, tomllib.TOMLDecodeError) as error:
      try:
        display_path = path.relative_to(BASE_DIR)
      except ValueError:
        display_path = path
      file_errors.append(f"{display_path}: {error}")

  if file_errors:
    formatted = "\n".join(f"  - {error}" for error in file_errors)
    raise ValueError(f"invalid WIP TOML input:\n{formatted}")

  cars.sort(
    key=lambda car: (
      car["make"].lower(),
      car["model"].lower(),
      car["branch_name"].lower(),
    )
  )
  footnotes: dict[int, str] = {}
  output_data = build_output(
    cars,
    SOURCE_NAME,
    SOURCE_URL,
    footnotes,
    generator="toml_to_json.py",
    include_footnote_definitions=False, # WIP does not use footnotes
  )
  output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
  try:
    display_output_path = output_path.relative_to(BASE_DIR)
  except ValueError:
    display_output_path = output_path
  print(f"Processed {len(toml_files)} toml file(s): {len(cars)} cars -> {display_output_path}")
  return len(cars)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser()
  parser.add_argument("--wip-dir", type=Path, default=WIP_DIR)
  parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
  return parser.parse_args()


def main() -> None:
  args = parse_args()
  try:
    build_wip_json(args.wip_dir, args.output)
  except ValueError as error:
    print(f"Error: {error}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
