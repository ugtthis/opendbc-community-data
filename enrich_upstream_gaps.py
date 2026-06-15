import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

UPSTREAM_SOURCE = "openpilot"


@dataclass(frozen=True)
class CarKey:
  years: tuple[int, ...]
  make: str
  model: str
  model_variant_list: tuple[str, ...]
  supported_package_list: tuple[str, ...]


def normalize_text(value: object) -> str:
  return " ".join(str(value or "").strip().lower().split())


def normalized_year_list(car: dict) -> tuple[int, ...]:
  value = car.get("year_list")
  if not isinstance(value, list):
    return ()
  return tuple(sorted({int(year) for year in value if str(year).isdigit()}))


def normalized_model_variant_list(car: dict) -> tuple[str, ...]:
  variant_entries = car.get("model_variant_list")
  if not isinstance(variant_entries, list):
    return ()
  return tuple(
    normalize_text(variant_entry)
    for variant_entry in variant_entries
    if normalize_text(variant_entry)
  )


def normalized_supported_package_list(car: dict) -> tuple[str, ...]:
  package_entries = car.get("supported_package_list")
  if not isinstance(package_entries, list):
    return ()
  return tuple(
    normalize_text(package_entry)
    for package_entry in package_entries
    if normalize_text(package_entry)
  )


def car_key(car: dict) -> CarKey | None:
  years = normalized_year_list(car)
  make = normalize_text(car.get("make"))
  model = normalize_text(car.get("model"))
  supported_package_list = normalized_supported_package_list(car)
  if not years or not make or not model or not supported_package_list:
    return None
  return CarKey(
    years,
    make,
    model,
    normalized_model_variant_list(car),
    supported_package_list,
  )


def upstream_by_model(openpilot_cars: Iterable[dict]) -> dict[tuple[str, str], list[CarKey]]:
  upstream: dict[tuple[str, str], list[CarKey]] = defaultdict(list)
  for car in openpilot_cars:
    key = car_key(car)
    if key:
      upstream[(key.make, key.model)].append(key)
  return upstream


def is_region_variant(item: str) -> bool:
  return item.endswith(" only")


def variant_matches(source_variants: tuple[str, ...], upstream_variants: tuple[str, ...]) -> bool:
  source_items = set(source_variants)
  upstream_items = set(upstream_variants)
  if source_items == upstream_items:
    return True

  source_features = {item for item in source_items if not is_region_variant(item)}
  upstream_features = {item for item in upstream_items if not is_region_variant(item)}
  if source_features != upstream_features:
    return False

  source_regions = {item for item in source_items if is_region_variant(item)}
  upstream_regions = {item for item in upstream_items if is_region_variant(item)}
  return bool(source_regions) and source_regions <= upstream_regions


def package_matches(source_packages: tuple[str, ...], upstream_packages: tuple[str, ...]) -> bool:
  source_items = set(source_packages)
  return bool(source_items) and source_items <= set(upstream_packages)


def year_available_upstream(
  source: CarKey,
  year: int,
  upstream: dict[tuple[str, str], list[CarKey]],
) -> bool:
  for upstream_key in upstream.get((source.make, source.model), []):
    if year not in upstream_key.years:
      continue
    if not variant_matches(source.model_variant_list, upstream_key.model_variant_list):
      continue
    if package_matches(source.supported_package_list, upstream_key.supported_package_list):
      return True
  return False


def years_not_in_upstream(
  car: dict,
  upstream: dict[tuple[str, str], list[CarKey]],
) -> list[int]:
  key = car_key(car)
  if not key:
    return []
  return [
    year
    for year in key.years
    if not year_available_upstream(key, year, upstream)
  ]


def enrich_car(car: dict, upstream: dict[tuple[str, str], list[CarKey]]) -> dict:
  enriched = dict(car)
  enriched["years_not_in_upstream"] = years_not_in_upstream(car, upstream)
  return enriched


def load_json(path: Path) -> dict:
  return json.loads(path.read_text(encoding="utf-8"))


def enrich_file(path: Path, upstream: dict[tuple[str, str], list[CarKey]]) -> None:
  payload = load_json(path)
  payload["cars"] = [
    enrich_car(car, upstream)
    for car in payload.get("cars", [])
  ]
  path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def enrich_data_dir(data_dir: Path) -> None:
  upstream_path = data_dir / f"{UPSTREAM_SOURCE}.json"
  upstream_payload = load_json(upstream_path)
  upstream = upstream_by_model(upstream_payload.get("cars", []))

  for path in sorted(data_dir.glob("*.json")):
    if path == upstream_path:
      continue
    payload = load_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("cars"), list):
      enrich_file(path, upstream)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser()
  parser.add_argument("--data-dir", default="data")
  return parser.parse_args()


def main() -> None:
  args = parse_args()
  enrich_data_dir(Path(args.data_dir))


if __name__ == "__main__":
  main()
