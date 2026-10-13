"""Give controlled card images consistent canvases without changing their content."""

from pathlib import Path
import argparse
import re
import runpy
from xml.parsers import expat


CARD_GROUPS = runpy.run_path(
    str(Path(__file__).with_name("validate-profile-cards.py"))
)["CARD_GROUPS"]
CARD_SIZES = {
    **{f"{name}-{theme}.svg": (495, 195)
       for name in ("stats", "streak") for theme in ("light", "dark")},
    **{f"top-langs-{theme}.svg": (340, 200) for theme in ("light", "dark")},
    **{name: (400, 150) for name in CARD_GROUPS["pins"]},
    **{name: (340, 200) for name in CARD_GROUPS["summary"]
       if not name.endswith("/0-profile-details.svg")},
}
ROOT_TAG = re.compile(rb'''<(?:[^<>"']|"[^"]*"|'[^']*')*>''')
ATTRIBUTE = re.compile(
    rb'''(?P<name>[A-Za-z_:][\w:.-]*)(?P<equals>\s*=\s*)(?P<quote>["'])(?P<value>.*?)(?P=quote)''',
    re.DOTALL,
)


def normalize_svg(document: bytes, width: int, height: int) -> bytes:
    """Edit only root attributes; retain viewBox, CSS, CDATA and all body bytes."""
    parser = expat.ParserCreate(namespace_separator="}")
    root = []

    def record_root(name, attrs):
        if not root:
            root.append((name, attrs, parser.CurrentByteIndex))

    parser.StartElementHandler = record_root
    parser.Parse(document, True)
    name, attrs, start = root[0]
    if name != "http://www.w3.org/2000/svg}svg":
        raise ValueError("Expected an SVG root")
    if "viewBox" not in attrs:
        raise ValueError("Cannot preserve scale without an existing viewBox")
    match = ROOT_TAG.match(document, start)
    if match is None:
        raise ValueError("Could not locate the SVG opening tag")
    replacements = {
        b"width": str(width).encode("ascii"),
        b"height": str(height).encode("ascii"),
        b"preserveAspectRatio": b"xMidYMid meet",
    }
    remaining = set(replacements)

    def replace_attribute(attribute):
        key = attribute["name"]
        if key not in replacements:
            return attribute[0]
        remaining.discard(key)
        quote = attribute["quote"]
        return key + attribute["equals"] + quote + replacements[key] + quote

    opening = ATTRIBUTE.sub(replace_attribute, match[0])
    closing_length = 2 if opening.endswith(b"/>") else 1
    additions = b"".join(
        b" " + key + b'="' + value + b'"'
        for key, value in replacements.items() if key in remaining
    )
    opening = opening[:-closing_length] + additions + opening[-closing_length:]
    return document[:start] + opening + document[match.end():]


def normalize(directory: Path, group: str) -> None:
    changed = 0
    for name in CARD_GROUPS[group]:
        if name not in CARD_SIZES:
            continue
        path = directory / name
        before = path.read_bytes()
        after = normalize_svg(before, *CARD_SIZES[name])
        if after != before:
            path.write_bytes(after)
            changed += 1
    print(f"Normalized {changed} {group} profile card canvases.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--group", choices=CARD_GROUPS, default="base")
    args = parser.parse_args()
    try:
        normalize(args.directory, args.group)
    except (OSError, ValueError, expat.ExpatError) as error:
        raise SystemExit(f"Card normalization failed: {error}") from None
