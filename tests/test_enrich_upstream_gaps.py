import unittest

from enrich_upstream_gaps import (
  enrich_car,
  upstream_by_model,
  years_not_in_upstream,
)


def car(
  *,
  make="Hyundai",
  model="Ioniq 5",
  years=None,
  model_variant_list=None,
  supported_package="All",
  supported_package_list=None,
):
  return {
    "make": make,
    "model": model,
    "model_variant": None,
    "model_variant_list": model_variant_list or [],
    "years": None,
    "year_list": years if years is not None else [2022],
    "supported_package": supported_package,
    "supported_package_list": supported_package_list or [supported_package],
    "footnotes": {"make": [], "model": []},
  }


class EnrichUpstreamGapsTest(unittest.TestCase):
  def test_lists_only_years_missing_from_upstream(self):
    upstream = upstream_by_model([car(years=[2022, 2023])])

    self.assertEqual(
      years_not_in_upstream(car(years=[2022, 2023, 2024]), upstream),
      [2024],
    )

  def test_region_variant_matches_upstream_superset(self):
    upstream = upstream_by_model(
      [
        car(
          years=[2022, 2023],
          model_variant_list=["Southeast Asia only", "Europe only"],
        )
      ]
    )

    self.assertEqual(
      years_not_in_upstream(
        car(years=[2022], model_variant_list=["Southeast Asia only"]),
        upstream,
      ),
      [],
    )

  def test_returns_all_missing_years_as_list(self):
    upstream = upstream_by_model([car(years=[2020])])

    self.assertEqual(
      years_not_in_upstream(car(years=[2022, 2023]), upstream),
      [2022, 2023],
    )

  def test_enrich_car_adds_years_not_in_upstream(self):
    upstream = upstream_by_model([car(years=[2020])])
    enriched = enrich_car(car(years=[2024]), upstream)
    self.assertEqual(enriched["years_not_in_upstream"], [2024])

  def test_overwrites_existing_years_not_in_upstream_value(self):
    existing = car(years=[2024])
    existing["years_not_in_upstream"] = [2024]
    upstream = upstream_by_model([car(years=[2020])])
    enriched = enrich_car(existing, upstream)
    self.assertEqual(enriched["years_not_in_upstream"], [2024])


if __name__ == "__main__":
  unittest.main()
