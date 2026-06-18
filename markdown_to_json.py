#!/usr/bin/env python3
import argparse
import json
import re
import sys
from html import unescape
from pathlib import Path

from car_normalize import (
  build_output,
  build_supported_package_list,
  extract_years,
  format_years_abbreviated,
  split_model_and_variant,
)

BASE_DIR = Path(__file__).parent
REF_DIR = BASE_DIR / "data" / "ref"
OUTPUT_DIR = BASE_DIR / "data"
SOURCES_FILE = BASE_DIR / "md_sources.json"

# Output keys -> acceptable markdown header aliases.
REQUIRED_COLUMNS = {
  "make": ["Make"],
  "model": ["Model"],
  "hardware_needed": ["Hardware Needed"],
  "supported_package": ["Supported Package"],
  "acc": ["ACC"],
  "no_acc_below": ["No ACC accel below"],
  "no_alc_below": ["No ALC below"],
  "auto_resume_available": ["Resume from stop"],
}
OPTIONAL_COLUMNS = {
  "video": ["Video"],
  "setup_video": ["Setup Video"],
}
HARDWARE_DEVICES = ("comma 3X", "comma four")

FOOTNOTE_PATTERN = re.compile(r"\[<sup>([^<]+)</sup>\]\(#footnotes\)", re.IGNORECASE)
FOOTNOTE_DEFINITION_PATTERN = re.compile(r"<sup>(\d+)</sup>\s*(.*?)\s*<br\s*/?>", re.IGNORECASE)
HREF_PATTERN = re.compile(r'href="([^"]+)"', re.IGNORECASE)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MULTISPACE_PATTERN = re.compile(r"\s+")


class RowValidationError(Exception):
  pass


def parse_row(text_line: str) -> list[str]:
  return [cell.strip() for cell in text_line.strip("|").split("|")]


def is_table_row(text_line: str) -> bool:
  return text_line.startswith("|") and "---" not in text_line


def map_columns(headers: list[str], column_spec: dict[str, list[str]]) -> dict[str, int]:
  normalized_headers = {
    normalize_header_text(header): index
    for index, header in enumerate(headers)
  }

  column_map = {}
  for key, aliases in column_spec.items():
    for alias in aliases:
      column_index = normalized_headers.get(normalize_header_text(alias))
      if column_index is not None:
        column_map[key] = column_index
        break
  return column_map


def get_cell(row: list[str], col_map: dict[str, int], key: str) -> str | None:
  column_index = col_map.get(key)
  if column_index is None or column_index >= len(row):
    return None
  value = row[column_index].strip()
  return value if value else None


def parse_footnotes(cell_text: str) -> list[int]:
  numbers: list[int] = []
  for match in FOOTNOTE_PATTERN.findall(cell_text):
    for token in match.split(","):
      token = token.strip()
      if token.isdigit():
        numbers.append(int(token))
  # Keep stable order while removing duplicates.
  return list(dict.fromkeys(numbers))


def parse_footnote_definitions(lines: list[str]) -> dict[int, str]:
  footnotes: dict[int, str] = {}
  in_footnotes_section = False

  for line in lines:
    stripped = line.strip()

    if not in_footnotes_section:
      if stripped == "### Footnotes":
        in_footnotes_section = True
      continue

    if stripped.startswith("#"):
      break

    match = FOOTNOTE_DEFINITION_PATTERN.search(line)
    if match:
      footnotes[int(match.group(1))] = clean_cell_text(match.group(2))

  return footnotes


def clean_cell_text(cell_text: str) -> str:
  remove_footnotes = FOOTNOTE_PATTERN.sub("", cell_text)
  remove_html_tags = HTML_TAG_PATTERN.sub("", remove_footnotes)
  decode_html_entities = unescape(remove_html_tags)
  remove_extra_whitespace = MULTISPACE_PATTERN.sub(" ", decode_html_entities)
  return remove_extra_whitespace.strip()


def normalize_header_text(header_text: str) -> str:
  return clean_cell_text(header_text).lower()


def detect_hardware_needed(cell_text: str | None) -> str:
  normalized_cell = clean_cell_text(cell_text or "").lower()
  for device in HARDWARE_DEVICES:
    if device.lower() in normalized_cell:
      return device
  return "N/A"


def parse_link(cell_text: str | None) -> str | None:
  match = HREF_PATTERN.search(cell_text or "")
  if not match:
    return None
  url = match.group(1).strip()
  return url or None


def find_first_compatible_table_header(lines: list[str]) -> tuple[dict[str, int], int]:
  required_keys = set(REQUIRED_COLUMNS.keys())
  for index, line in enumerate(lines):
    if not is_table_row(line):
      continue
    headers = parse_row(line)
    col_map = map_columns(headers, REQUIRED_COLUMNS)
    if set(col_map.keys()) == required_keys:
      col_map.update(map_columns(headers, OPTIONAL_COLUMNS))
      return col_map, index
  raise ValueError(
    "No CARS table found with required columns: "
    + ", ".join(sorted(REQUIRED_COLUMNS.keys()))
  )


def parse_car_row(row: list[str], col_map: dict[str, int]) -> tuple[dict | None, tuple[str, ...]]:
  raw_fields = {
    "make": get_cell(row, col_map, "make"),
    "model": get_cell(row, col_map, "model"),
    "hardware_needed": get_cell(row, col_map, "hardware_needed"),
    "supported_package": get_cell(row, col_map, "supported_package"),
    "acc": get_cell(row, col_map, "acc"),
    "no_acc_below": get_cell(row, col_map, "no_acc_below"),
    "no_alc_below": get_cell(row, col_map, "no_alc_below"),
    "auto_resume_available": get_cell(row, col_map, "auto_resume_available"),
    "video": get_cell(row, col_map, "video"),
    "setup_video": get_cell(row, col_map, "setup_video"),
  }

  missing_required_fields = tuple(
    key for key in REQUIRED_COLUMNS.keys() if not raw_fields.get(key)
  )
  if missing_required_fields:
    return None, missing_required_fields

  # make/model keep both clean values and footnote IDs scoped to that exact row.
  raw_make = raw_fields["make"] or ""
  raw_model = raw_fields["model"] or ""
  clean_make = clean_cell_text(raw_make)
  clean_model = clean_cell_text(raw_model)
  supported_package = clean_cell_text(raw_fields["supported_package"] or "")
  model, model_variant, model_variant_list = split_model_and_variant(clean_model)
  year_list = extract_years(clean_model)
  years = format_years_abbreviated(year_list)
  if years is None and clean_make.lower() == "comma" and model.lower() == "body":
    years = "N/A"
  # Keep display names clean since comma body does not have years.
  display_years = years if years and years != "N/A" else None
  model_name_for_display = " ".join(part for part in [model, model_variant, display_years] if part)

  return {
    "name": f"{clean_make} {model_name_for_display}",
    "make": clean_make,
    "model": model,
    "model_variant": model_variant,
    "model_variant_list": model_variant_list,
    "years": years,
    "year_list": year_list,
    "hardware_needed": detect_hardware_needed(raw_fields["hardware_needed"]),
    "supported_package": supported_package,
    "supported_package_list": build_supported_package_list(supported_package),
    "acc": clean_cell_text(raw_fields["acc"] or ""),
    "no_acc_below": clean_cell_text(raw_fields["no_acc_below"] or ""),
    "no_alc_below": clean_cell_text(raw_fields["no_alc_below"] or ""),
    "auto_resume_available": "icon-star-full.svg" in (raw_fields["auto_resume_available"] or ""),
    "video": parse_link(raw_fields["video"]),
    "setup_video": parse_link(raw_fields["setup_video"]),
    "footnotes": {
      "make": parse_footnotes(raw_make),
      "model": parse_footnotes(raw_model),
    },
  }, ()


def parse_cars_from_markdown(input_path: Path) -> tuple[list[dict], dict[int, str]]:
  lines = input_path.read_text(encoding="utf-8").splitlines()
  col_map, header_index = find_first_compatible_table_header(lines)
  footnote_definitions = parse_footnote_definitions(lines)

  cars: list[dict] = []
  row_validation_errors: list[str] = []

  for row_number, text_line in enumerate(lines[header_index + 1:], start=header_index + 2):
    if not text_line.startswith("|"):
      break
    if not is_table_row(text_line):
      continue

    row_cells = parse_row(text_line)
    car, missing_required_fields = parse_car_row(row_cells, col_map)
    if missing_required_fields:
      row_validation_errors.append(
        f"row {row_number} missing: {', '.join(missing_required_fields)}"
      )
      continue

    cars.append(car)

  if row_validation_errors:
    formatted_errors = "\n".join(f"  - {error}" for error in row_validation_errors)
    raise RowValidationError(
      "Each row must include make, model, hardware_needed, supported_package, acc, no_acc_below, no_alc_below, and auto_resume_available.\n"
      f"{formatted_errors}"
    )

  return cars, footnote_definitions


def load_source_urls() -> dict[str, str]:
  if not SOURCES_FILE.exists():
    raise ValueError(f"Missing source config file: {SOURCES_FILE}")
  source_configs = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
  return {
    config["source"].strip().lower(): config["url"]
    for config in source_configs
    if isinstance(config, dict) and config.get("source") and config.get("url")
  }


def find_input_markdown_files() -> list[Path]:
  return sorted(REF_DIR.glob("*.md"))


def output_path_for_input(input_path: Path) -> Path:
  source_name = input_path.stem.lower()
  return OUTPUT_DIR / f"{source_name}.json"


def process_markdown_file(input_path: Path, output_path: Path, source_urls: dict[str, str]) -> int:
  cars, footnotes = parse_cars_from_markdown(input_path)
  source_name = input_path.stem.lower()
  source_url = source_urls.get(source_name)
  if not source_url:
    raise ValueError(
      f"Missing URL for '{source_name}' in {SOURCES_FILE.name}"
    )
  output_data = build_output(
    cars,
    source_name,
    source_url,
    footnotes,
    generator="markdown_to_json.py",
    include_footnote_definitions=True,
  )
  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
  try:
    display_output_path = output_path.relative_to(BASE_DIR)
  except ValueError:
    display_output_path = output_path
  print(f"Processed {input_path.name}: {len(cars)} cars -> {display_output_path}")
  return len(cars)


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--input", "-i", type=Path, help="Single markdown file to convert")
  parser.add_argument("--output", "-o", type=Path, help="Output JSON path (only with --input)")
  args = parser.parse_args()

  if args.output and not args.input:
    print("Error: --output requires --input", file=sys.stderr)
    sys.exit(1)

  if not args.input:
    if not REF_DIR.is_dir():
      print(f"Error: input directory not found: {REF_DIR}", file=sys.stderr)
      sys.exit(1)

  input_files = [args.input] if args.input else find_input_markdown_files()
  if not input_files:
    print(f"Error: no markdown files found in {REF_DIR}", file=sys.stderr)
    sys.exit(1)

  source_urls = load_source_urls()

  failed = False
  for input_path in input_files:
    output_path = args.output or output_path_for_input(input_path)
    try:
      process_markdown_file(input_path, output_path, source_urls)
    except (RowValidationError, ValueError) as error:
      print(f"Error processing {input_path.name}: {error}", file=sys.stderr)
      failed = True

  if failed:
    sys.exit(1)


if __name__ == "__main__":
  main()
