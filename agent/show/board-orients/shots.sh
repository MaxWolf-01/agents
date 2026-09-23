#!/usr/bin/env bash
# Rebuilds the demo tracker, renders its board, and takes the screenshots index.html shows:
# the top of the board and two rows opened, each in both colour schemes, cropped to the part
# the page annotates. The PNGs land in shots/ beside this script and stay untracked.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
demo=/var/tmp/board-orients-demo
"$here/../../prototypes/board-orients/demo-tracker/build.sh" "$demo" >/dev/null

# a copy of the board with two rows opened: the question-stopped ticket and a build in review
sed -e 's/<details class="ticket" id="t-csv-import-02"/<details open class="ticket" id="t-csv-import-02"/' \
    -e 's/<details class="ticket" id="standalone-flaky-upload-test"/<details open class="ticket" id="standalone-flaky-upload-test"/' \
    "$demo/board.html" > "$demo/board-open.html"
cp "$demo/board.html.stamp.js" "$demo/board-open.html.stamp.js"

mkdir -p "$here/shots"
for theme in day night; do
    chromium --headless=new --disable-gpu --hide-scrollbars --window-size=1600,1900 --virtual-time-budget=12000 \
        --screenshot="$here/shots/full-$theme.png" "file://$demo/board.html?theme=$theme" 2>/dev/null
    chromium --headless=new --disable-gpu --hide-scrollbars --window-size=1600,2800 --virtual-time-budget=12000 \
        --screenshot="$here/shots/open-full-$theme.png" "file://$demo/board-open.html?theme=$theme" 2>/dev/null
done
uv run --quiet --with pillow python - "$here/shots" <<'EOF'
import sys
from pathlib import Path
from PIL import Image
shots = Path(sys.argv[1])
for theme in ("day", "night"):
    Image.open(shots / f"full-{theme}.png").crop((0, 0, 1600, 700)).save(shots / f"top-{theme}.png")
    Image.open(shots / f"open-full-{theme}.png").crop((0, 110, 1060, 2250)).save(shots / f"open-{theme}.png")
EOF
ls "$here/shots"
