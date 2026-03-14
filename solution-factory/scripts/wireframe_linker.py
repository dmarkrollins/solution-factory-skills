#!/usr/bin/env python3
"""
List available wireframes from the configured wireframe path.
Used during story creation to link UX stories to wireframes.
"""

import json
import sys
import argparse
from pathlib import Path


def list_wireframes(root="."):
    """List wireframe files from config.json wireframe_path."""
    config_path = Path(root) / ".solution-factory" / "config.json"

    if not config_path.exists():
        return {"error": "config.json not found"}

    with open(config_path, "r") as f:
        cfg = json.load(f) or {}
    wireframe_path = cfg.get("ux", {}).get("wireframe_path")

    if not wireframe_path:
        return {"error": "ux.wireframe_path not configured in config.json"}

    wf_dir = Path(root) / wireframe_path
    if not wf_dir.exists():
        return {"error": f"Wireframe directory not found: {wireframe_path}"}

    # Find wireframe files (tsx, jsx, html, png, svg, figma exports)
    extensions = ["*.tsx", "*.jsx", "*.html", "*.png", "*.svg", "*.pdf"]
    wireframes = []

    for ext in extensions:
        for f in sorted(wf_dir.rglob(ext)):
            wireframes.append({
                "name": f.stem,
                "path": str(f.relative_to(root)),
                "type": f.suffix[1:]
            })

    return {
        "wireframe_path": wireframe_path,
        "count": len(wireframes),
        "wireframes": wireframes
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List available wireframes")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    result = list_wireframes(args.root)

    print(json.dumps(result, indent=2))
