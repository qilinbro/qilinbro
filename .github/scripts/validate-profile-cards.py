"""Reject missing, invalid, or error cards before replacing published SVGs."""

from pathlib import Path
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
ERROR_MESSAGES = (
    "something went wrong",
    "api rate limit",
    "rate limit exceeded",
    "could not fetch",
    "failed to fetch",
    "please try again",
    "bad credentials",
    "maximum retries exceeded",
)


def validate(directory: Path) -> None:
    for name in CARD_NAMES:
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
    print(f"Validated all {len(CARD_NAMES)} profile cards.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: validate-profile-cards.py DIRECTORY")
    try:
        validate(Path(sys.argv[1]))
    except (OSError, ValueError, ET.ParseError) as error:
        raise SystemExit(f"Card validation failed: {error}") from None
