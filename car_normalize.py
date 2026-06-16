import re


MULTISPACE_PATTERN = re.compile(r"\s+")
YEAR_RANGE = r"(?:19|20)\d{2}(?:-\d{2,4})?"
YEAR_SUFFIX_PATTERN = rf"(?:{YEAR_RANGE}(?:\s*,\s*)?)+\s*$"
PARENTHESES_CONTENT = r"\(([^)]*)\)"


def normalize_whitespace(value: str) -> str:
  return MULTISPACE_PATTERN.sub(" ", value).strip()


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


def format_years_abbreviated(year_list: list[int]) -> str | None:
  if not year_list:
    return None

  ranges: list[tuple[int, int]] = []
  start = year_list[0]
  end = year_list[0]

  for year in year_list[1:]:
    if year == end + 1:
      end = year
    else:
      ranges.append((start, end))
      start = year
      end = year
  ranges.append((start, end))

  formatted_ranges: list[str] = []
  for range_start, range_end in ranges:
    if range_start == range_end:
      formatted_ranges.append(str(range_start))
    elif range_start // 100 == range_end // 100:
      formatted_ranges.append(f"{range_start}-{range_end % 100:02d}")
    else:
      formatted_ranges.append(f"{range_start}-{range_end}")

  return ", ".join(formatted_ranges)


def split_region_variant_item(variant_item: str) -> list[str]:
  only_suffix = " only"
  if not variant_item.lower().endswith(only_suffix):
    return [variant_item]

  region_text = variant_item[: -len(only_suffix)].strip()
  region_names = [
    normalize_whitespace(split_region)
    for split_region in re.split(r"\s+(?:and|&)\s+", region_text)
    if split_region.strip()
  ]
  if len(region_names) <= 1:
    return [variant_item]
  return [f"{region_name}{only_suffix}" for region_name in region_names]


def build_model_variant_list(variant_contents: list[str]) -> list[str]:
  model_variant_list: list[str] = []
  for variant_content in variant_contents:
    variant_items = [
      normalize_whitespace(part)
      for part in variant_content.split(",")
      if part.strip()
    ]
    for variant_item in variant_items:
      normalized_item = normalize_whitespace(variant_item)
      model_variant_list.extend(split_region_variant_item(normalized_item))
  return list(dict.fromkeys(model_variant_list))


def build_supported_package_list(supported_package: str) -> list[str]:
  package_values = [
    normalize_whitespace(package_value)
    for package_value in re.split(r"\s+or\s+", supported_package)
    if normalize_whitespace(package_value)
  ]
  return list(dict.fromkeys(package_values))


def split_model_and_variant(model_original: str) -> tuple[str, str | None, list[str]]:
  model_without_years = re.sub(YEAR_SUFFIX_PATTERN, "", model_original).strip()
  variant_contents = [
    normalize_whitespace(variant)
    for variant in re.findall(PARENTHESES_CONTENT, model_without_years)
    if variant.strip()
  ]
  variant_with_parentheses = [f"({variant})" for variant in variant_contents]
  model_variant_list = build_model_variant_list(variant_contents)
  model = normalize_whitespace(re.sub(PARENTHESES_CONTENT, "", model_without_years))
  return model, (" ".join(variant_with_parentheses) or None), model_variant_list


def build_output(
  cars: list[dict],
  source_name: str,
  source_url: str,
  footnotes: dict[int, str],
  *,
  generator: str,
  include_footnote_definitions: bool,
) -> dict:
  output = {
    "_metadata": {
      "url": source_url,
      "generator": generator,
      "source": source_name,
      "total": f"{len(cars)} cars",
    },
  }
  if include_footnote_definitions:
    output["footnote_definitions"] = footnotes
  output["cars"] = cars
  return output
