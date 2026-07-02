import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"

src_path = str(SRC_PATH)
if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)
