# opendbc-community-data

Turn community car-support sources into normalized JSON files.

Use it for two different kinds of data:

- **Fork sources**: full `docs/CARS.md` tables from openpilot-style forks.
- **Branch/WIP cars**: individual cars in progress or cars that are staying experiemntal for the time being. This will have more required info so future users can be pointed to the right direction if they want to explore the branch.

## Which Path To Use

```text
Do you have a full fork with docs/CARS.md?
  yes -> add it to md_sources.json
   no -> add a car entry under data/wip/<make>.toml
```

## Add A Fork Source

Use this when a fork publishes a full `docs/CARS.md` table.

Add one object to `md_sources.json`:

```json
{
  "source": "examplepilot",
  "url": "https://github.com/example/examplepilot/blob/main/docs/CARS.md",
  "raw_url": "https://raw.githubusercontent.com/example/examplepilot/main/docs/CARS.md"
}
```

Fork `docs/CARS.md` must include these required table headers (exact names expected by the parser):

- `Make`
- `Model`
- `Hardware Needed`
- `Supported Package`
- `ACC`
- `No ACC accel below`
- `No ALC below`
- `Resume from stop`

Optional headers:

- `Video`
- `Setup Video`

Then run:

```bash
python3 fetch_md_sources.py
python3 markdown_to_json.py
python3 enrich_upstream_gaps.py
```

This creates:

- `data/ref/examplepilot.md`: fetched source markdown.
- `data/examplepilot.json`: normalized fork data.

Fork JSON keeps source footnotes:

```text
data/examplepilot.json
  _metadata
  footnote_definitions
  cars[]
```

## Add A Branch/WIP Car

Use this when support exists on a branch but is not represented by a full fork `CARS.md`.

Create or edit a make-specific TOML file:

```text
data/wip/tesla.toml
data/wip/hyundai.toml
data/wip/toyota.toml
```

Each car is a `[[cars]]` entry:

```toml
[[cars]]
# required
make = "Tesla"
model = "Cybertruck 2077 (with hw10)"
hardware_needed = "comma X"
supported_package = "All"
acc = "openpilot"
no_acc_below = "0 mph"
no_alc_below = "0 mph"
auto_resume_available = true
branch_name = "the-cybertruck"
branch_url = "https://github.com/elon/opendbc/tree/the-cybertruck"
branch_desc = "Highly experimental branch with limited validation."
wiki_url = "https://github.com/commaai/openpilot/wiki/Tesla"
discord_url = "https://discord.com/channels/469524606043160576/524328474081755137"
discord_name = "elon"

# optional
extra_resource_url = ""
video = ""
setup_video = ""
important_notes = [
  "Current support is confirmed only for models manufactured after March 2077",
  "Further tuning is still needed for rough-road steering behavior.",
]
```

Then run:

```bash
python3 toml_to_json.py
python3 enrich_upstream_gaps.py
```

This creates or updates `data/wip.json`.

## Upstream Gap Fields

`enrich_upstream_gaps.py` compares every non-openpilot JSON file against `data/openpilot.json`.

Each car gets:

```json
"years_not_in_upstream": [2024, 2025]
```

An empty list means the entry has no detected year gap against upstream openpilot, or it did not have enough normalized year/package/model data to compare.

## Quick Validation

Run focused tests:

```bash
python3 -m unittest tests/test_car_normalize.py tests/test_markdown_to_json.py tests/test_toml_to_json.py
```

Run the full data update locally:

```bash
python3 fetch_md_sources.py && python3 markdown_to_json.py && python3 toml_to_json.py && python3 enrich_upstream_gaps.py
```

## Data Flow

```text
[Inputs]
  md_sources.json
  data/wip/*.toml

[Pipeline]
  md_sources.json
    -> fetch_md_sources.py
    -> data/ref/<source>.md
    -> markdown_to_json.py
    -> data/<fork>.json (openpilot.json, sunnypilot.json, ...)

  data/wip/*.toml
    -> toml_to_json.py
    -> data/wip.json

[Enrichment]
  data/openpilot.json + every other data/*.json
    -> enrich_upstream_gaps.py
    -> data/*.json with years_not_in_upstream added per car

[Final Outputs]
  data/openpilot.json
  data/<fork>.json
  data/wip.json
```

The scheduled workflow in `update-data.yml` runs the same sequence:

```bash
python3 fetch_md_sources.py && python3 markdown_to_json.py && python3 toml_to_json.py && python3 enrich_upstream_gaps.py
```

