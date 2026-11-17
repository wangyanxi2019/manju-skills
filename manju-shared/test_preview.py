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
            (project / '视觉风格.md').write_text('confirmed')
            (shared / 'project.json').write_text(json.dumps({'default_project_root': str(project)}))
            result = resolve(shared)
            self.assertEqual(result['references']['manju-jb'], str(rule.resolve()))
            self.assertEqual(result['style_file'], str((project / '视觉风格.md').resolve()))

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
            (root / '视觉风格.md').write_text('new style')
            (shared / 'project.json').write_text('{"default_project_root":"/does/not/exist"}')
            self.assertEqual(resolve(shared)['selection'], 'local-suite')


if __name__ == '__main__':
    unittest.main()
