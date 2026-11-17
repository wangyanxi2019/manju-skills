#!/usr/bin/env python3
"""Read and save a confirmed visual style in one work's output directory."""
import argparse
import json
from pathlib import Path


CONFIG_NAME = "视觉风格配置.json"
PRESETS_FILE = Path(__file__).with_name("style_presets.json")


def presets():
    data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    items = data.get("presets")
    if not isinstance(items, list) or not items:
        raise ValueError(f"Invalid presets: {PRESETS_FILE}")
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)) or not all(isinstance(value, str) and value for value in ids):
        raise ValueError(f"Duplicate or empty preset id: {PRESETS_FILE}")
    for item in items:
        if not all(isinstance(item.get(key), str) and item[key].strip()
                   for key in ("name", "description", "prompt")):
            raise ValueError(f"Invalid preset entry: {item.get('id')}")
    return items


def load(work_dir, work_title=None):
    path = Path(work_dir).expanduser().resolve() / CONFIG_NAME
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("status") != "confirmed":
        raise ValueError(f"Style config is not confirmed: {path}")
    for key in ("work_title", "prompt", "selected_preset"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError(f"Missing {key} in {path}")
    if work_title and value["work_title"] != work_title:
        raise ValueError(f"Style belongs to {value['work_title']}, not {work_title}: {path}")
    return value


def save(work_dir, work_title, preset_id=None, custom_prompt=None):
    if not isinstance(work_title, str) or not work_title.strip():
        raise ValueError("A nonempty work title is required")
    if (preset_id is None) == (custom_prompt is None):
        raise ValueError("Choose exactly one preset or custom prompt")
    directory = Path(work_dir).expanduser().resolve()
    previous = load(directory, work_title)
    if preset_id is not None:
        match = next((item for item in presets() if item["id"] == preset_id), None)
        if match is None:
            raise ValueError(f"Unknown preset: {preset_id}")
        prompt, chosen = match["prompt"], preset_id
    else:
        prompt, chosen = custom_prompt.strip(), "custom"
        if not prompt:
            raise ValueError("Custom style prompt cannot be empty")
    value = {"version": 1, "work_title": work_title.strip(), "status": "confirmed",
             "selected_preset": chosen, "prompt": prompt}
    if previous == value:
        return directory / CONFIG_NAME
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CONFIG_NAME
    temp = directory / (CONFIG_NAME + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True, help="One work's output directory")
    parser.add_argument("--title", help="Work title, required when saving")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--select", help="Preset id selected by the user")
    choice.add_argument("--custom", help="User-confirmed custom style prompt")
    choice.add_argument("--custom-file", type=Path, help="UTF-8 file with user-confirmed style")
    args = parser.parse_args()
    try:
        custom = args.custom_file.read_text(encoding="utf-8") if args.custom_file else args.custom
        if args.select is not None or custom is not None:
            if not args.title:
                parser.error("--title is required when saving")
            save(args.work_dir, args.title, args.select, custom)
        result = {"work_dir": str(args.work_dir.expanduser().resolve()),
                  "config_file": str(args.work_dir.expanduser().resolve() / CONFIG_NAME),
                  "current": load(args.work_dir, args.title), "presets": presets()}
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
