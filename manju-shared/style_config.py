#!/usr/bin/env python3
"""Read and save a confirmed visual style in one work's output directory."""
import argparse
import json
import re
from pathlib import Path


CONFIG_NAME = "视觉风格配置.json"
PRESETS_FILE = Path(__file__).with_name("style_presets.json")
STYLE_SOURCE = Path(__file__).parent / "references" / "漫剧生图影视风格预设.md"
VARIANTS_SOURCE = Path(__file__).parent / "references" / "漫剧资产风格变体.md"


def source_prompts():
    """Extract numbered style prompts verbatim from the editable Markdown source."""
    source = STYLE_SOURCE.read_text(encoding="utf-8")
    pattern = re.compile(r"^### (\d{2})｜([^\n]+)\n\n```text\n([^`]+)\n```", re.MULTILINE)
    found = {}
    for match in pattern.finditer(source):
        number, name, prompt = match.groups()
        if number in found or not name.strip() or not prompt.strip():
            raise ValueError(f"Duplicate or empty style {number}: {STYLE_SOURCE}")
        found[number] = {"name": name.strip(), "prompt": prompt.strip()}
    if not found:
        raise ValueError(f"No numbered style prompts in {STYLE_SOURCE}")
    return found


def common_negative_prompt():
    source = STYLE_SOURCE.read_text(encoding="utf-8")
    match = re.search(r"^## 通用负面提示词\s*\n\s*```text\n([^`]+)\n```", source, re.MULTILINE)
    return match.group(1).strip() if match else None


def asset_variants():
    """Read the editable subject-specific variants for every numbered style."""
    source = VARIANTS_SOURCE.read_text(encoding="utf-8")
    headings = list(re.finditer(r"^## (\d{2})｜[^\n]+$", source, re.MULTILINE))
    variants = {}
    labels = {"base": "通用风格", "scene": "无人场景风格", "prop": "单物品风格"}
    for index, heading in enumerate(headings):
        number = heading.group(1)
        if number in variants:
            raise ValueError(f"Duplicate variant number {number}: {VARIANTS_SOURCE}")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(source)
        section = source[heading.end():end]
        entry = {}
        for key, label in labels.items():
            match = re.search(rf"^### {label}\s*\n```text\n(.*?)\n```", section, re.MULTILINE | re.DOTALL)
            if not match or not match.group(1).strip():
                raise ValueError(f"Missing {label} for {number}: {VARIANTS_SOURCE}")
            entry[key + "_prompt"] = match.group(1).strip()
        variants[number] = entry
    if not variants:
        raise ValueError(f"No asset variants in {VARIANTS_SOURCE}")
    return variants


def presets():
    data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    items = data.get("presets")
    if not isinstance(items, list) or not items:
        raise ValueError(f"Invalid presets: {PRESETS_FILE}")
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)) or not all(isinstance(value, str) and value for value in ids):
        raise ValueError(f"Duplicate or empty preset id: {PRESETS_FILE}")
    source = source_prompts()
    variants = asset_variants()
    numbers = [item.get("number") for item in items]
    if len(numbers) != len(set(numbers)) or set(numbers) != set(source) or set(numbers) != set(variants):
        raise ValueError(f"Preset numbers must match both Markdown sources: {PRESETS_FILE}")
    result = []
    for item in items:
        if not isinstance(item.get("medium"), str) or not item["medium"].strip():
            raise ValueError(f"Invalid preset entry: {item.get('id')}")
        result.append({**item, **source[item["number"]], **variants[item["number"]]})
    return result


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
    prompts = value.get("prompts")
    if prompts is not None:
        if not isinstance(prompts, dict) or any(
            not isinstance(prompts.get(key), str) or not prompts[key].strip()
            for key in ("base", "character", "scene", "prop")
        ) or prompts["character"] != value["prompt"]:
            raise ValueError(f"Incomplete subject-specific style prompts: {path}")
    return value


def write_config(directory, value):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CONFIG_NAME
    temp = directory / (CONFIG_NAME + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def save(work_dir, work_title, preset_id=None, custom_prompt=None,
         base_prompt=None, scene_prompt=None, prop_prompt=None):
    if not isinstance(work_title, str) or not work_title.strip():
        raise ValueError("A nonempty work title is required")
    if (preset_id is None) == (custom_prompt is None):
        raise ValueError("Choose exactly one preset or custom prompt")
    directory = Path(work_dir).expanduser().resolve()
    previous = load(directory, work_title)
    if preset_id is not None:
        if any(value is not None for value in (base_prompt, scene_prompt, prop_prompt)):
            raise ValueError("Preset variants come from the editable Markdown source")
        match = next((item for item in presets() if item["id"] == preset_id), None)
        if match is None:
            raise ValueError(f"Unknown preset: {preset_id}")
        prompt, chosen, medium = match["prompt"], preset_id, match["medium"]
        variants = {"base": match["base_prompt"], "character": prompt,
                    "scene": match["scene_prompt"], "prop": match["prop_prompt"]}
    else:
        prompt, chosen, medium = custom_prompt.strip(), "custom", "custom"
        if not prompt:
            raise ValueError("Custom style prompt cannot be empty")
        values = (base_prompt, scene_prompt, prop_prompt)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("Custom style requires base, scene and prop variants")
        variants = {"base": base_prompt.strip(), "character": prompt,
                    "scene": scene_prompt.strip(), "prop": prop_prompt.strip()}
    value = {"version": 2, "work_title": work_title.strip(), "status": "confirmed",
             "selected_preset": chosen, "medium": medium, "prompt": prompt, "prompts": variants}
    if previous == value:
        return directory / CONFIG_NAME
    return write_config(directory, value)


def upgrade(work_dir, work_title):
    """Explicitly add variants to a legacy preset while retaining its old character prompt."""
    directory = Path(work_dir).expanduser().resolve()
    previous = load(directory, work_title)
    if previous is None:
        raise ValueError("No saved style config to upgrade")
    if previous.get("prompts"):
        return directory / CONFIG_NAME
    match = next((item for item in presets() if item["id"] == previous["selected_preset"]), None)
    if match is None:
        raise ValueError("Legacy custom style needs reviewed base, scene and prop variants")
    value = {**previous, "version": 2, "medium": previous.get("medium") or match["medium"],
             "prompts": {"base": match["base_prompt"], "character": previous["prompt"],
                         "scene": match["scene_prompt"], "prop": match["prop_prompt"]}}
    return write_config(directory, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True, help="One work's output directory")
    parser.add_argument("--title", help="Work title, required when saving")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--select", help="Preset id selected by the user")
    choice.add_argument("--custom", help="User-confirmed custom style prompt")
    choice.add_argument("--custom-file", type=Path, help="UTF-8 file with user-confirmed style")
    choice.add_argument("--upgrade", action="store_true", help="Add variants to a legacy preset after confirmation")
    parser.add_argument("--base-file", type=Path, help="Confirmed base variant for a custom style")
    parser.add_argument("--scene-file", type=Path, help="Confirmed empty-scene variant for a custom style")
    parser.add_argument("--prop-file", type=Path, help="Confirmed single-object variant for a custom style")
    args = parser.parse_args()
    try:
        custom = args.custom_file.read_text(encoding="utf-8") if args.custom_file else args.custom
        if args.select is not None or custom is not None or args.upgrade:
            if not args.title:
                parser.error("--title is required when saving")
            if args.upgrade:
                upgrade(args.work_dir, args.title)
            else:
                files = (args.base_file, args.scene_file, args.prop_file)
                values = [file.read_text(encoding="utf-8") if file else None for file in files]
                save(args.work_dir, args.title, args.select, custom, *values)
        result = {"work_dir": str(args.work_dir.expanduser().resolve()),
                  "config_file": str(args.work_dir.expanduser().resolve() / CONFIG_NAME),
                  "current": load(args.work_dir, args.title), "presets": presets(),
                  "common_negative_prompt": common_negative_prompt()}
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
