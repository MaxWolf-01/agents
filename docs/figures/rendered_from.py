"""What each image under mx/assets/ was rendered from, recorded beside it, and whether that still holds.

`<stem>.rendered-from.json` holds the script that rendered `<stem>.png` (and `<stem>-light.png`
where there is one) and the sha256 of each source it read: a file's is `sha256sum`'s, a
directory's covers its files as git sees them, ignored ones left out. A source edited after the
render no longer matches. Comparing sources rather than images keeps the answer off the host that
rendered: the same HTML renders to different bytes on another machine's text rasterizer.
"""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "mx" / "assets"
SUFFIX = ".rendered-from.json"


def record(stem: str, renderer: Path, *sources: Path) -> None:
    """Write `<stem>`'s record: `renderer` rendered it from `sources`, as they are now."""
    rel = lambda path: str(path.resolve().relative_to(ROOT))  # noqa: E731
    body = {"renderer": rel(renderer), "sources": {rel(s): digest(s) for s in sources}}
    (ASSETS / (stem + SUFFIX)).write_text(json.dumps(body, indent=2) + "\n")


def stale() -> list[str]:
    """One line per image whose record is missing or whose sources moved since its render."""
    images: dict[str, list[str]] = {}
    for png in sorted(ASSETS.glob("*.png")):
        images.setdefault(png.stem.removesuffix("-light"), []).append(f"mx/assets/{png.name}")
    problems = []
    for stem, pngs in images.items():
        path = ASSETS / (stem + SUFFIX)
        if not path.is_file():
            problems.append(f"{', '.join(pngs)}: nothing records what it was rendered from (no mx/assets/{path.name})")
            continue
        recorded = json.loads(path.read_text())
        for source, sha in recorded["sources"].items():
            if not (ROOT / source).exists() or digest(ROOT / source) != sha:
                problems.append(f"{', '.join(pngs)}: {source} changed since it was rendered; "
                                f"{recorded['renderer']} renders it again")
    return problems


def digest(source: Path) -> str:
    if source.is_file():
        return hashlib.sha256(source.read_bytes()).hexdigest()
    listed = subprocess.run(["git", "-C", str(source), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                            capture_output=True, text=True, check=True).stdout.split("\0")
    whole = hashlib.sha256()
    for name in sorted(n for n in listed if n and (source / n).is_file()):  # a deleted tracked file is still listed
        whole.update(f"{name}\0{digest(source / name)}\0".encode())
    return whole.hexdigest()
