#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "ref" / "CARS.md"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "ref" / "cars.json"

# Output keys -> acceptable markdown header aliases.
REQUIRED_COLUMNS = {
  "make": ["Make"],
  "model": ["Model"],
  "supported_package": ["Supported Package", "Required Package/Features", "Package"],
  "acc": ["ACC"],
  "no_acc_below": ["No ACC accel below", "No ACC below"],
  "no_alc_below": ["No ALC below"],
}

FOOTNOTE_PATTERN = re.compile(r"\[<sup>([^<]+)</sup>\]\(#footnotes\)", re.IGNORECASE)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MULTISPACE_PATTERN = re.compile(r"\s+")
YEAR_RANGE = r"(?:19|20)\d{2}(?:-\d{2,4})?"
YEAR_SUFFIX_PATTERN = rf"(?:{YEAR_RANGE}(?:\s*,\s*)?)+\s*$"
PARENTHESES_CONTENT = r"\(([^)]*)\)"


class RowValidationError(Exception):
  pass


def parse_row(text_line: str) -> list[str]:
  return [cell.strip() for cell in text_line.strip("|").split("|")]


def is_table_row(text_line: str) -> bool:
  return text_line.startswith("|") and "---" not in text_line


def map_columns(headers: list[str], column_spec: dict[str, list[str]]) -> dict[str, int]:
  column_map = {}
  for key, aliases in column_spec.items():
    for alias in aliases:
      if alias in headers:
        column_map[key] = headers.index(alias)
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


def clean_cell_text(cell_text: str) -> str:
  without_footnotes = FOOTNOTE_PATTERN.sub("", cell_text)
  without_html = HTML_TAG_PATTERN.sub("", without_footnotes)
  collapsed_whitespace = MULTISPACE_PATTERN.sub(" ", without_html)
  return collapsed_whitespace.strip()


def extract_years(model_string: str) -> list[int]:
  match = re.search(YEAR_SUFFIX_PATTERN, model_string)
  if not match:
    return []

  years: list[int] = []
  for year_match in re.findall(YEAR_RANGE, match.group()):
    parts = year_match.split("-")
    start = int(parts[0])
    if len(parts) > 1:
      if len(parts[1]) == 4:
        raise ValueError(f"Unexpected year format in '{model_string}'")
      end = int(parts[1])
      if end < 100:
        end += (start // 100) * 100
    else:
      end = start
    years.extend(range(start, end + 1))

  return sorted(set(years))


def clean_model(model: str) -> str:
  model = re.sub(YEAR_SUFFIX_PATTERN, "", model)
  model = re.sub(PARENTHESES_CONTENT, "", model)
  return model.strip()


def find_first_compatible_table_header(lines: list[str]) -> tuple[dict[str, int], int]:
  required_keys = set(REQUIRED_COLUMNS.keys())
  for index, line in enumerate(lines):
    if not is_table_row(line):
      continue
    col_map = map_columns(parse_row(line), REQUIRED_COLUMNS)
    if set(col_map.keys()) == required_keys:
      return col_map, index
  raise ValueError(
    "No CARS table found with required columns: "
    + ", ".join(sorted(REQUIRED_COLUMNS.keys()))
  )


def parse_car_row(row: list[str], col_map: dict[str, int]) -> tuple[dict | None, tuple[str, ...]]:
  raw_fields = {
    "make": get_cell(row, col_map, "make"),
    "model": get_cell(row, col_map, "model"),
    "supported_package": get_cell(row, col_map, "supported_package"),
    "acc": get_cell(row, col_map, "acc"),
    "no_acc_below": get_cell(row, col_map, "no_acc_below"),
    "no_alc_below": get_cell(row, col_map, "no_alc_below"),
  }

  missing_required_fields = tuple(key for key, value in raw_fields.items() if not value)
  if missing_required_fields:
    return None, missing_required_fields

  # make/model keep both clean values and footnote IDs scoped to that exact row.
  raw_make = raw_fields["make"] or ""
  raw_model = raw_fields["model"] or ""
  clean_make = clean_cell_text(raw_make)
  model_original = clean_cell_text(raw_model)
  model = clean_model(model_original)

  return {
    "name": f"{clean_make} {model_original}",
    "make": clean_make,
    "model": model,
    "model_original": model_original,
    "years": extract_years(model_original),
    "supported_package": clean_cell_text(raw_fields["supported_package"] or ""),
    "acc": clean_cell_text(raw_fields["acc"] or ""),
    "no_acc_below": clean_cell_text(raw_fields["no_acc_below"] or ""),
    "no_alc_below": clean_cell_text(raw_fields["no_alc_below"] or ""),
    "footnotes": {
      "make": parse_footnotes(raw_make),
      "model": parse_footnotes(raw_model),
    },
  }, ()


def parse_cars_from_markdown(input_path: Path) -> list[dict]:
  lines = input_path.read_text(encoding="utf-8").splitlines()
  col_map, header_index = find_first_compatible_table_header(lines)

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
      "Each row must include make, model, supported_package, acc, no_acc_below, and no_alc_below.\n"
      f"{formatted_errors}"
    )

  return cars


def derive_source_from_filename(source_filename: str) -> str:
  if source_filename.endswith("-CARS.md"):
    return source_filename[: -len("-CARS.md")]
  return Path(source_filename).stem


def build_output(cars: list[dict], source_filename: str) -> dict:
  return {
    "_metadata": {
      "generator": "markdown_to_json.py",
      "source": derive_source_from_filename(source_filename),
    },
    "cars": cars,
  }


def main() -> None:
  parser = argparse.ArgumentParser(
    description="Convert openpilot-style CARS.md table rows into JSON."
  )
  parser.add_argument("--input", "-i", type=Path, default=DEFAULT_INPUT)
  parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT)
  args = parser.parse_args()

  try:
    cars = parse_cars_from_markdown(args.input)
  except (RowValidationError, ValueError) as error:
    print(f"\nError: {error}\n")
    sys.exit(1)

  output_data = build_output(cars, args.input.name)
  args.output.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
  print(f"Processed {len(cars)} vehicles from {args.input.name}")


if __name__ == "__main__":
  main()
