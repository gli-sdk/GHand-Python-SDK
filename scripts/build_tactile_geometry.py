"""Build packaged GHand5 geometry from the supplied PX Excel/matrix files.

Usage: python3 scripts/build_tactile_geometry.py /path/to/px
No Excel/CAD runtime dependencies are needed by this generator or the SDK.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def build(source: Path) -> dict:
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    models = {}
    for code, model, count in (("A", "PXSR-CMDDP21A", 38), ("B", "PXSR-CMDDP21B", 31)):
        header = source / f"{model}.h"
        sheet = next(source.glob(f"*{model}测点坐标.xlsx"))
        flat = ast.literal_eval(header.read_text().strip().rstrip(";"))
        matrices = [[row[i:i + 3] for i in (0, 3, 6)] for row in flat]
        with zipfile.ZipFile(sheet) as archive:
            root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        ids, points = [], []
        for row in root.findall(".//s:sheetData/s:row", ns)[1:]:
            cells = {c.attrib["r"].rstrip("0123456789"): c.findtext("s:v", namespaces=ns) for c in row}
            ids.append(int(cells["A"]))
            points.append([float(cells[k]) for k in ("B", "C", "D")])
        if ids != list(range(1, count + 1)) or len(matrices) != count or any(len(r) != 9 for r in flat):
            raise ValueError(f"{model}: point IDs / matrix count mismatch")
        models[model] = {
            "point_ids": ids, "positions_mm": points, "rotations_cad_to_local": matrices,
            "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (header, sheet)},
        }
    return {
        "schema": "ghand.tactile_geometry.v1",
        "position_unit": "mm",
        "rotation_convention": "cad_to_taxel_local_column_vector",
        "convention_source": "Integrator confirmation 2026-11-06: F_local = R @ F_cad",
        "input_force_frame": "taxel_local",
        "output_frame": "per_sensor_cad",
        "point_order": "1-based Excel IDs; matrix rows and SDK triples in the same order",
        "sensor_models": {"THUMB": "PXSR-CMDDP21A", **{k: "PXSR-CMDDP21B" for k in ("FF", "MF", "RF", "LF")}},
        "models": models,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "src/ghand/config/ghand5_tactile_geometry.json")
    args = parser.parse_args()
    args.output.write_text(json.dumps(build(args.source), ensure_ascii=False, indent=2) + "\n")
