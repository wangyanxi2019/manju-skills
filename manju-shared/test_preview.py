"""Regression checks for malformed data, preserved files and project isolation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import render_preview as render
from resolve_project import resolve
from style_config import load as load_style, presets, save as save_style


def fixture():
    return {"schema_version": "1", "skill": "manju-fj", "title": "预览", "items": [
        {"id": "01", "title": "镜头", "prompts": [{"label": "Prompt", "text": "中文\n<Subject 1>"}]}]}


class PreviewTests(unittest.TestCase):
    def test_invalid_types_rejected_before_render(self):
        for path, value in [
            (("items", 0, "id"), []), (("items", 0, "title"), 42),
            (("items", 0, "fields"), [{}]), (("items", 0, "notes"), [{}]),
            (("items", 0, "prompts", 0, "label"), []),
            (("notes",), "wrong"), (("source_files",), [42]),
            (("data",), []), (("skill",), "unknown"),
        ]:
            data = fixture()
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                render.validate(data)

    def test_duplicate_id_rejected(self):
        data = fixture()
        data["items"].append(copy.deepcopy(data["items"][0]))
        with self.assertRaises(ValueError):
            render.validate(data)

    def test_empty_extraction_has_explanation(self):
        data = fixture()
        data["items"] = []
        with self.assertRaises(ValueError):
            render.validate(data)
        data["notes"] = ["指定段落没有关键道具。"]
        self.assertEqual(render.validate(data), [])
        self.assertIn('class="empty show"', render.preview(data, [], "empty.json"))

    def test_prompt_is_escaped_without_losing_source(self):
        data = fixture()
        prompt = '</script><img src=x onerror="alert(1)"> & 中文'
        data["items"][0]["prompts"][0]["text"] = prompt
        output = render.preview(data, render.validate(data), "预览.json")
        self.assertNotIn('<img src=x', output)
        self.assertIn(render.e(prompt), output)
        self.assertEqual(data["items"][0]["prompts"][0]["text"], prompt)

    def test_reserved_filename_characters_are_url_encoded(self):
        data = fixture()
        output = render.preview(data, render.validate(data), "a#b?.json", "a#b?.md")
        self.assertIn('href="a%23b%3F.json"', output)
        self.assertIn('href="a%23b%3F.md"', output)

    def test_nested_markdown_fences_preserve_prompt(self):
        data = fixture()
        text = "说明\n```text\n原文\n```"
        data["items"][0]["prompts"][0]["text"] = text
        output = render.markdown(data, render.validate(data))
        self.assertIn("````text\n" + text + "\n````", output)

    def run_cli(self, source, *flags):
        return subprocess.run([sys.executable, str(Path(render.__file__)), str(source), *flags],
                              capture_output=True, text=True)

    def test_existing_markdown_is_preserved_and_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "output.json"
            data = fixture()
            source.write_text(json.dumps(data))
            original = "# 特定格式\n" + data["items"][0]["prompts"][0]["text"] + "\n用户注释\n"
            source.with_suffix('.md').write_text(original)
            result = self.run_cli(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.with_suffix('.md').read_text(), original)
            html = source.with_suffix('.html').read_text()
            data["items"][0]["prompts"][0]["text"] = "JSON 不一致"
            source.write_text(json.dumps(data))
            result = self.run_cli(source)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(source.with_suffix('.html').read_text(), html)
            self.assertEqual(source.with_suffix('.md').read_text(), original)

    def test_malformed_input_never_overwrites_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "output.json"
            data = fixture()
            data["items"][0]["fields"] = [{}]
            source.write_text(json.dumps(data))
            for suffix in ('.md', '.html'):
                source.with_suffix(suffix).write_text('keep')
            result = self.run_cli(source, '--write-markdown')
            self.assertNotEqual(result.returncode, 0)
            for suffix in ('.md', '.html'):
                self.assertEqual(source.with_suffix(suffix).read_text(), 'keep')

    def test_installed_skill_resolves_editable_project_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shared = base / 'installed/manju-shared'
            shared.mkdir(parents=True)
            project = base / 'project'
            rule = project / 'manju-jb/references/分镜脚本.txt'
            rule.parent.mkdir(parents=True)
            rule.write_text('editable')
            (shared / 'project.json').write_text(json.dumps({'default_project_root': str(project)}))
            result = resolve(shared)
            self.assertEqual(result['references']['manju-jb'], str(rule.resolve()))
            self.assertIsNone(result['style_file'])

    def test_explicit_project_does_not_inherit_old_style(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shared = base / 'old/manju-shared'
            shared.mkdir(parents=True)
            (shared.parent / '视觉风格.md').write_text('old style')
            project = base / 'new'
            project.mkdir()
            result = resolve(shared, project)
            self.assertIsNone(result['style_file'])
            self.assertEqual(result['project_root'], str(project.resolve()))

    def test_moved_suite_precedes_old_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = root / 'manju-shared'
            shared.mkdir()
            (root / 'manju-jb').mkdir()
            (shared / 'project.json').write_text('{"default_project_root":"/does/not/exist"}')
            self.assertEqual(resolve(shared)['selection'], 'local-suite')

    def test_each_work_has_independent_style_and_no_default(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shared = base / 'manju-shared'
            shared.mkdir()
            (base / 'manju-jb').mkdir()
            (base / '视觉风格.md').write_text('过时的全局修仙风格')
            first, second = base / '作品甲-漫剧', base / '作品乙-漫剧'
            self.assertIsNone(resolve(shared, work_dir=first, work_title='作品甲')['style_prompt'])
            save_style(first, '作品甲', 'xianxia_3d')
            save_style(second, '作品乙', 'urban_realistic')
            self.assertEqual(resolve(shared, work_dir=first, work_title='作品甲')['style_preset'], 'xianxia_3d')
            self.assertEqual(resolve(shared, work_dir=second, work_title='作品乙')['style_preset'], 'urban_realistic')
            self.assertNotEqual(load_style(first)['prompt'], load_style(second)['prompt'])
            self.assertIsNone(resolve(shared)['style_prompt'])

    def test_style_cannot_be_reused_for_a_different_title(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            save_style(base, '作品甲', 'urban_3d')
            with self.assertRaisesRegex(ValueError, '作品甲'):
                load_style(base, '作品乙')
            with self.assertRaisesRegex(ValueError, '作品甲'):
                save_style(base, '作品乙', 'xianxia_3d')

    def test_custom_style_is_preserved_and_invalid_choice_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            save_style(base, '都市故事', custom_prompt='低饱和都市夜景，胶片质感。')
            self.assertEqual(load_style(base)['prompt'], '低饱和都市夜景，胶片质感。')
            self.assertEqual(load_style(base)['selected_preset'], 'custom')
            with self.assertRaisesRegex(ValueError, 'Unknown preset'):
                save_style(base, '都市故事', 'not_a_preset')
            self.assertEqual(load_style(base)['selected_preset'], 'custom')
            self.assertEqual(len(presets()), 3)


if __name__ == '__main__':
    unittest.main()
