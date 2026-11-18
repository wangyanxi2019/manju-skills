#!/usr/bin/env python3
"""Render a manju JSON bundle to matching offline HTML and Markdown files."""

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import quote


CSS = Path(__file__).with_name("preview_style.css").read_text(encoding="utf-8")

JS = r"""
const search = document.getElementById('search');
const cards = [...document.querySelectorAll('.card')];
const count = document.getElementById('visible-count');
const empty = document.getElementById('empty');
const toast = document.getElementById('toast');
let toastTimer;
search.addEventListener('input', () => {
  const query = search.value.trim().toLocaleLowerCase();
  let visible = 0;
  for (const card of cards) {
    const match = card.textContent.toLocaleLowerCase().includes(query);
    card.hidden = !match;
    if (match) visible++;
  }
  count.textContent = String(visible);
  empty.classList.toggle('show', visible === 0);
});
function announce(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2300);
}
async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch (_) { /* Local files may deny the modern clipboard API. */ }
  }
  const previousFocus = document.activeElement;
  const area = document.createElement('textarea');
  area.value = value;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  let success = false;
  try {
    area.select();
    area.setSelectionRange(0, value.length);
    success = document.execCommand('copy');
  } finally {
    area.remove();
    if (previousFocus && previousFocus.focus) previousFocus.focus({preventScroll:true});
  }
  if (!success) throw new Error('copy unavailable');
}
document.addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-copy]');
  if (!button || button.disabled) return;
  const target = document.getElementById(button.dataset.copy);
  if (!target) return;
  button.disabled = true;
  button.dataset.originalLabel ||= button.textContent;
  clearTimeout(button.copyResetTimer);
  try {
    await copyText(target.textContent);
    button.textContent = '已复制';
    announce('提示词已复制');
  } catch (_) {
    button.textContent = button.dataset.originalLabel;
    announce('复制失败，请选中文本手动复制');
  } finally {
    button.copyResetTimer = setTimeout(() => {button.textContent = button.dataset.originalLabel;}, 1800);
    button.disabled = false;
  }
});
"""


def e(value):
    return html.escape(str(value), quote=True)


def validate(bundle):
    if not isinstance(bundle, dict) or bundle.get("schema_version") != "1":
        raise ValueError("schema_version must be '1'")
    if not isinstance(bundle.get("title"), str) or not bundle["title"].strip():
        raise ValueError("title is required")
    if bundle.get("skill") not in {"manju-jb", "manju-rw", "manju-dj", "manju-cj", "manju-fj", "manju-h3"}:
        raise ValueError("skill must identify one of the six manju skills")
    for key in ("notes", "source_files"):
        values = bundle.get(key, [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError(f"{key} must be a list of strings")
    if not isinstance(bundle.get("data", {}), dict):
        raise ValueError("data must be an object")
    global_style = bundle.get("data", {}).get("global_style")
    if global_style is not None and (not isinstance(global_style, str) or not global_style.strip()):
        raise ValueError("data.global_style must be a non-empty string")
    if "subtitle" in bundle and not isinstance(bundle["subtitle"], str):
        raise ValueError("subtitle must be a string")
    items = bundle.get("items")
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    if not items and not bundle.get("notes"):
        raise ValueError("empty items requires a note explaining the result")
    ids = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"item {index} must be an object")
        if any(not isinstance(item.get(key), str) or not item[key].strip() for key in ("id", "title")):
            raise ValueError(f"item {index} needs id and title")
        if item["id"] in ids:
            raise ValueError(f"duplicate item id: {item['id']}")
        ids.add(item["id"])
        prompts = item.get("prompts")
        if not isinstance(prompts, list) or not prompts:
            raise ValueError(f"item {index} needs at least one prompt")
        for prompt in prompts:
            if not isinstance(prompt, dict) or not isinstance(prompt.get("label"), str) or not prompt["label"].strip() or not isinstance(prompt.get("text"), str) or not prompt["text"].strip():
                raise ValueError(f"item {index} has invalid prompt")
        if not isinstance(item.get("fields", []), list) or not isinstance(item.get("notes", []), list):
            raise ValueError(f"item {index} fields and notes must be lists")
        for field in item.get("fields", []):
            if not isinstance(field, dict) or any(not isinstance(field.get(key), str) for key in ("label", "value")):
                raise ValueError(f"item {index} field requires string label and value")
        if any(not isinstance(note, str) for note in item.get("notes", [])):
            raise ValueError(f"item {index} notes must contain strings")
        if not isinstance(item.get("data", {}), dict):
            raise ValueError(f"item {index} data must be an object")
        if "summary" in item and not isinstance(item["summary"], str):
            raise ValueError(f"item {index} summary must be a string")
    return items


def markdown(bundle, items):
    lines = [f"# {bundle['title']}", ""]
    if bundle.get("subtitle"):
        lines.extend([bundle["subtitle"], ""])
    if bundle["skill"] == "manju-jb" and bundle.get("data", {}).get("global_style"):
        lines.extend([bundle["data"]["global_style"], ""])
    for item in items:
        lines.extend([f"## {item['title']}", ""])
        if item.get("summary"):
            lines.extend([item["summary"], ""])
        for field in item.get("fields", []):
            lines.extend([f"- **{field['label']}**  {field['value']}", ""])
        for prompt in item["prompts"]:
            fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", prompt["text"])), default=0))
            lines.extend([f"### {prompt['label']}", "", fence + "text", prompt["text"], fence, ""])
        for note in item.get("notes", []):
            lines.extend([f"- {note}", ""])
    if bundle.get("notes"):
        lines.extend(["## 核对记录", ""])
        for note in bundle["notes"]:
            lines.extend([f"- {note}", ""])
    return "\n".join(lines).rstrip() + "\n"


def preview(bundle, items, json_name, md_name=None):
    sections = []
    for item_index, item in enumerate(items):
        fields = "".join(
            f'<div class="field"><dt>{e(field["label"])}</dt><dd>{e(field["value"])}</dd></div>'
            for field in item.get("fields", [])
        )
        prompts = []
        for prompt_index, prompt in enumerate(item["prompts"]):
            code_id = f"prompt-{item_index}-{prompt_index}"
            prompts.append(
                '<section class="prompt">'
                f'<div class="prompt-head"><h4>{e(prompt["label"])}</h4>'
                f'<button class="copy" type="button" data-copy="{code_id}" aria-label="复制{e(prompt["label"])}">复制</button></div>'
                f'<pre id="{code_id}"><code>{e(prompt["text"])}</code></pre></section>'
            )
        notes = item.get("notes", [])
        note_html = '<ul class="notes">' + "".join(f"<li>{e(note)}</li>" for note in notes) + "</ul>" if notes else ""
        sections.append(
            '<article class="card">'
            f'<div class="card-head"><span class="card-id">{e(item["id"])}</span><h3>{e(item["title"])}</h3>'
            f'<p class="summary">{e(item.get("summary", ""))}</p></div>'
            f'<dl class="fields">{fields}</dl>' + "".join(prompts) + note_html + "</article>"
        )
    notes = bundle.get("notes", [])
    notes_html = '<h2><span class="section-no">02</span>核对记录</h2><ul>' + "".join(f"<li>{e(note)}</li>" for note in notes) + "</ul>" if notes else '<h2><span class="section-no">02</span>文件下载</h2>'
    subtitle = f'<p class="subtitle">{e(bundle.get("subtitle", ""))}</p>' if bundle.get("subtitle") else ""
    markdown_link = f'<a href="{e(quote(md_name, safe=""))}" download>下载 Markdown</a>' if md_name else ""
    empty_class = "empty" if items else "empty show"
    cards_class = "cards single" if len(items) == 1 else "cards"
    prompt_count = sum(len(item["prompts"]) for item in items)
    source_count = len(bundle.get("source_files", []))
    global_style = bundle.get("data", {}).get("global_style") if bundle["skill"] == "manju-jb" else None
    global_style_html = (
        '<section class="global-setting" aria-label="全局风格与通用约束">'
        '<div class="prompt-head"><h2>全局风格与通用约束</h2>'
        '<button class="copy" type="button" data-copy="global-style" aria-label="复制全局风格与通用约束">复制</button></div>'
        f'<pre id="global-style"><code>{e(global_style)}</code></pre></section>'
    ) if global_style else ""
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(bundle["title"])}</title><style>{CSS}</style></head><body>'
        '<main class="shell"><header class="mast"><div class="mast-top"><div>'
        f'<p class="eyebrow">MANJU / {e(bundle.get("skill", "PREVIEW"))}</p><h1>{e(bundle["title"])}</h1>{subtitle}'
        '</div><span class="status">离线预览</span></div></header>'
        '<div class="metrics" aria-label="文档统计">'
        f'<div class="metric"><span class="metric-label">内容条目</span><strong class="metric-value">{len(items)}</strong><span class="metric-detail">当前文档范围</span></div>'
        f'<div class="metric"><span class="metric-label">可复制提示词</span><strong class="metric-value">{prompt_count}</strong><span class="metric-detail">逐条独立复制</span></div>'
        f'<div class="metric"><span class="metric-label">来源文件</span><strong class="metric-value">{source_count}</strong><span class="metric-detail">以 JSON 所列为准</span></div></div>'
        f'{global_style_html}'
        '<div class="toolbar"><h2><span class="section-no">01</span>内容与提示词 <span class="visible">匹配 <span id="visible-count">'
        f'{len(items)}</span> 项</span></h2><input id="search" class="search" type="search" placeholder="搜索人物、场景、镜头或提示词" aria-label="搜索内容"></div>'
        f'<div class="{cards_class}">{"".join(sections)}</div><p class="{empty_class}" id="empty">没有匹配内容，请查看核对记录。</p>'
        f'<footer class="foot">{notes_html}<div class="links">{markdown_link}'
        f'<a href="{e(quote(json_name, safe=""))}" download>下载 JSON</a></div></footer></main>'
        '<div id="toast" class="toast" role="status" aria-live="polite"></div>'
        f'<script>{JS}</script></body></html>'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="manju JSON bundle")
    parser.add_argument("--write-markdown", action="store_true", help="also generate Markdown from the JSON bundle")
    args = parser.parse_args()
    source = args.input.resolve()
    html_path = source.with_suffix(".html")
    md_path = source.with_suffix(".md")
    try:
        bundle = json.loads(source.read_text(encoding="utf-8"))
        items = validate(bundle)
        md_text = markdown(bundle, items) if args.write_markdown else None
        if md_text is None and md_path.exists():
            existing = md_path.read_text(encoding="utf-8")
            global_style = bundle.get("data", {}).get("global_style") if bundle["skill"] == "manju-jb" else None
            if global_style and global_style not in existing:
                raise ValueError("Markdown differs from JSON global style")
            for item in items:
                for prompt in item["prompts"]:
                    if prompt["text"] not in existing:
                        raise ValueError(f"Markdown differs from JSON prompt: {item['id']} / {prompt['label']}")
        html_text = preview(bundle, items, source.name, md_path.name if md_text is not None or md_path.exists() else None)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    # Validate and render everything before touching existing deliverables.
    if md_text is not None:
        md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    print(html_path)
    if md_path.exists():
        print(md_path)


if __name__ == "__main__":
    main()
