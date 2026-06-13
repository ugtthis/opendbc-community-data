import json
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).parent
SOURCES_FILE = BASE_DIR / "md_sources.json"
REF_DIR = BASE_DIR / "data" / "ref"


def main() -> None:
    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    REF_DIR.mkdir(parents=True, exist_ok=True)

    for source_config in sources:
        source = source_config["source"]
        raw_url = source_config["url"]
        output_path = REF_DIR / f"{source}.md"

        with urllib.request.urlopen(raw_url, timeout=30) as response:
            content = response.read().decode("utf-8")

        if not content.strip():
            raise RuntimeError(f"{source}: fetched markdown is empty")

        output_path.write_text(content, encoding="utf-8")
        print(f"Fetched {source}: {output_path.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
