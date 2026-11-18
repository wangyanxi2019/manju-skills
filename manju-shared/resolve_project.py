#!/usr/bin/env python3
"""Locate editable rules and the visual style confirmed for one work."""
import argparse
import json
from pathlib import Path
from style_config import CONFIG_NAME, load as load_style


RULES = {
    "manju-jb": "分镜脚本.txt",
    "manju-rw": "人物三视图例子.txt",
    "manju-h3": "视频大师提示词.txt",
}


def resolve(shared_dir, project=None, work_dir=None, work_title=None):
    shared_dir = Path(shared_dir).resolve()
    bundled_root = shared_dir.parent
    if project is not None:
        root = Path(project).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Project directory not found: {root}")
        mode = "explicit"
    elif (bundled_root / "manju-jb").is_dir():
        root, mode = bundled_root, "local-suite"
    else:
        config = shared_dir / "project.json"
        value = json.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
        configured = value.get("default_project_root")
        root = Path(configured).expanduser().resolve() if configured else bundled_root
        if not root.is_dir():
            raise ValueError(f"Configured project was moved: {root}; pass --project with its new location")
        mode = "configured" if configured else "bundled"
    references = {}
    for skill, filename in RULES.items():
        relative = Path(skill) / "references" / filename
        candidate = root / relative
        if not candidate.is_file():
            candidate = bundled_root / relative
        references[skill] = str(candidate) if candidate.is_file() else None
    style = load_style(work_dir, work_title) if work_dir else None
    return {
        "project_root": str(root),
        "selection": mode,
        "style_file": str(Path(work_dir).expanduser().resolve() / CONFIG_NAME) if style else None,
        "style_prompt": style["prompt"] if style else None,
        "style_base_prompt": style.get("prompts", {}).get("base") if style else None,
        "style_character_prompt": style.get("prompts", {}).get("character") if style else None,
        "style_scene_prompt": style.get("prompts", {}).get("scene") if style else None,
        "style_prop_prompt": style.get("prompts", {}).get("prop") if style else None,
        "style_preset": style["selected_preset"] if style else None,
        "style_medium": style.get("medium") if style else None,
        "references": references,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, help="Explicit rules root")
    parser.add_argument("--work-dir", type=Path, help="One work's output directory")
    parser.add_argument("--work-title", help="Reject a style config belonging to another work")
    args = parser.parse_args()
    try:
        result = resolve(Path(__file__).parent, args.project, args.work_dir, args.work_title)
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
