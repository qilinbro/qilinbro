"""Reject missing, invalid, or error cards before replacing published SVGs."""

from pathlib import Path
import argparse
import sys
import xml.etree.ElementTree as ET

CARD_NAMES = (
    "stats-light.svg",
    "stats-dark.svg",
    "top-langs-light.svg",
    "top-langs-dark.svg",
    "streak-light.svg",
    "streak-dark.svg",
)
PIN_NAMES = tuple(
    f"pin-{project}-{theme}.svg"
    for project in ("website", "social", "game", "image-grid")
    for theme in ("light", "dark")
)
SUMMARY_NAMES = tuple(
    f"summary-{theme}/{name}.svg"
    for theme in ("default", "tokyonight")
    for name in (
        "0-profile-details",
        "1-repos-per-language",
        "2-most-commit-language",
        "3-stats",
        "4-productive-time",
    )
)
CARD_GROUPS = {
    "base": CARD_NAMES,
    "pins": PIN_NAMES,
    "summary": SUMMARY_NAMES,
    "3d": ("3d/profile-green-animate.svg", "3d/profile-night-green.svg"),
}
ERROR_MESSAGES = (
    "something went wrong",
    "api rate limit",
    "rate limit exceeded",
    "could not fetch",
    "failed to fetch",
    "please try again",
    "bad credentials",
    "maximum retries exceeded",
    "resource not accessible",
    "could not resolve to a repository",
    "repository not found",
)


def validate(directory: Path, group: str = "base") -> None:
    names = CARD_GROUPS[group]
    for name in names:
        path = directory / name
        document = path.read_bytes()
        if len(document) < 512:
            raise ValueError(f"{name}: card is unexpectedly small")
        root = ET.fromstring(document)
        if root.tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError(f"{name}: expected an SVG document")
        if not root.get("viewBox") and not (root.get("width") and root.get("height")):
            raise ValueError(f"{name}: missing image dimensions")
        text = " ".join(root.itertext()).casefold()
        if any(message in text for message in ERROR_MESSAGES):
            raise ValueError(f"{name}: renderer returned an error card")
        if not any(node.tag == "{http://www.w3.org/2000/svg}text" for node in root.iter()):
            raise ValueError(f"{name}: missing card labels")
    print(f"Validated all {len(names)} {group} profile cards.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--group", choices=CARD_GROUPS, default="base")
    parser.add_argument("--list", action="store_true", help="List the group's controlled relative paths")
    args = parser.parse_args()
    if args.list:
        print("\n".join(CARD_GROUPS[args.group]))
        sys.exit(0)
    try:
        validate(args.directory, args.group)
    except (OSError, ValueError, ET.ParseError) as error:
        raise SystemExit(f"Card validation failed: {error}") from None
