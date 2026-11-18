#!/usr/bin/env python3
"""Flag production metadata accidentally copied into image generation prompts."""
import argparse
import json
import re
from pathlib import Path


IMAGE_SKILLS = {"manju-rw", "manju-dj", "manju-cj", "manju-fj"}
PATTERNS = (
    ("unresolved", re.compile(r"未说明|未明确|未确认|待核|原位置未明|原位未明|没有平方米数|精确尺寸未说明")),
    ("provenance", re.compile(r"原文称|原文未|视觉补全设定|制图约定|参考材料|\([ ]?原文[ ]?\)|（原文）")),
    ("missing_asset", re.compile(r"未上传|拟上传|路径为空|图像未核验|参考图未到位")),
)
FIELD_LABEL = re.compile(r"(?:凳子|门|烟雾|光源)状态[：:]")


def issues(bundle):
    """Return issue records for image prompts, excluding voice and other text prompts."""
    skill = bundle.get("skill")
    if skill not in IMAGE_SKILLS:
        return []
    result = []
    for item in bundle.get("items", []):
        for prompt in item.get("prompts", []):
            label = prompt.get("label", "")
            if "声线" in label or "语音" in label:
                continue
            value = prompt.get("text", "")
            for code, pattern in PATTERNS:
                match = pattern.search(value)
                if match:
                    result.append((item.get("id", "?"), label, code, match.group(0)))
            match = FIELD_LABEL.search(value)
            if match:
                result.append((item.get("id", "?"), label, "status_field", match.group(0)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="manju JSON output files")
    args = parser.parse_args()
    total = 0
    for path in args.inputs:
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
            found = issues(bundle)
        except (OSError, ValueError, TypeError) as exc:
            parser.error(f"{path}: {exc}")
        for item_id, label, code, term in found:
            print(f"{path}: {item_id} / {label}: {code}: {term}")
        total += len(found)
        print(f"{path}: {len(found)} issue(s)")
    raise SystemExit(1 if total else 0)


if __name__ == "__main__":
    main()
