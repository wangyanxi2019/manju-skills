"""Regression checks for malformed data, preserved files and project isolation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import render_preview as render
import style_config
from resolve_project import resolve
from style_config import (asset_variants, common_negative_prompt, load as load_style,
                          presets, save as save_style, source_prompts, upgrade)


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

    def test_storyboard_global_style_is_once_before_groups(self):
        data = fixture()
        data["skill"] = "manju-jb"
        data["data"] = {"global_style": "全局风格：水墨三维\n全局摄影与声音约束：无SRT，无音乐。"}
        data["items"][0]["prompts"][0]["text"] = "【第1集-01｜15秒】\n场景：房内"
        data["items"].append({"id": "02", "title": "第二组", "prompts": [
            {"label": "分镜组正文", "text": "【第1集-02｜15秒】\n场景：门外"}]})
        items = render.validate(data)
        output_md = render.markdown(data, items)
        output_html = render.preview(data, items, "story.json")
        style = data["data"]["global_style"]
        self.assertEqual(output_md.count(style), 1)
        self.assertLess(output_md.index(style), output_md.index("【第1集-01｜15秒】"))
        self.assertEqual(output_html.count(render.e(style)), 1)
        self.assertIn('data-copy="global-style"', output_html)
        self.assertEqual(output_html.count('class="card"'), 2)

    def test_storyboard_global_style_must_match_existing_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "story.json"
            data = fixture()
            data["skill"] = "manju-jb"
            data["data"] = {"global_style": "全局风格：水墨三维"}
            source.write_text(json.dumps(data), encoding="utf-8")
            source.with_suffix(".md").write_text("# 分镜\n" + data["items"][0]["prompts"][0]["text"], encoding="utf-8")
            result = self.run_cli(source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Markdown differs from JSON global style", result.stderr)

    def test_storyboard_voice_direction_follows_shot(self):
        data = fixture()
        data["skill"] = "manju-jb"
        data["data"] = {"global_style": "全局风格：水墨三维"}
        shot = "【镜头01｜4秒：人物开口。】"
        voice = "【配音指令：人物｜对白：原文】"
        data["items"][0]["prompts"][0]["text"] = shot + "\n\n" + voice
        with self.assertRaisesRegex(ValueError, "voice direction must follow its shot"):
            render.validate(data)
        data["items"][0]["prompts"][0]["text"] = shot + "\n" + voice
        self.assertEqual(len(render.validate(data)), 1)

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
            selected = resolve(shared, work_dir=first, work_title='作品甲')
            self.assertEqual(selected['style_character_prompt'], load_style(first)['prompt'])
            self.assertNotEqual(selected['style_scene_prompt'], selected['style_character_prompt'])
            self.assertNotEqual(selected['style_prop_prompt'], selected['style_character_prompt'])
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
            with self.assertRaisesRegex(ValueError, 'requires base, scene and prop'):
                save_style(base, '都市故事', custom_prompt='低饱和都市夜景，胶片质感。')
            save_style(base, '都市故事', custom_prompt='低饱和都市夜景，胶片质感。',
                       base_prompt='低饱和胶片质感', scene_prompt='低饱和都市环境胶片质感',
                       prop_prompt='低饱和单物品胶片质感')
            self.assertEqual(load_style(base)['prompt'], '低饱和都市夜景，胶片质感。')
            self.assertEqual(load_style(base)['selected_preset'], 'custom')
            self.assertEqual(load_style(base)['prompts']['scene'], '低饱和都市环境胶片质感')
            with self.assertRaisesRegex(ValueError, 'Unknown preset'):
                save_style(base, '都市故事', 'not_a_preset')
            self.assertEqual(load_style(base)['selected_preset'], 'custom')
            self.assertEqual(len(presets()), 13)

    def test_all_source_presets_are_available_verbatim(self):
        source = source_prompts()
        variants = asset_variants()
        choices = presets()
        self.assertEqual(set(source), {item['number'] for item in choices})
        self.assertEqual(set(source), set(variants))
        for item in choices:
            with self.subTest(number=item['number']):
                self.assertEqual(item['name'], source[item['number']]['name'])
                self.assertEqual(item['prompt'], source[item['number']]['prompt'])
                for key in ('base_prompt', 'scene_prompt', 'prop_prompt'):
                    self.assertEqual(item[key], variants[item['number']][key])
                for key in ('scene_prompt', 'prop_prompt'):
                    self.assertFalse(any(word in item[key] for word in
                                         ('人物', '演员', '皮肤', '五官', '发丝', '服饰', '角色')))
        self.assertEqual(choices[0]['name'], '东方水墨修仙 3D 国漫')
        self.assertEqual(choices[-1]['name'], '民国年代电影')
        self.assertIn('低清晰度', common_negative_prompt())

    def test_editing_markdown_updates_choices_without_rewriting_old_work(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old_work, new_work = base / 'old', base / 'new'
            save_style(old_work, '旧作', 'xianxia_3d')
            original = load_style(old_work)['prompt']
            edited = base / 'presets.md'
            edited.write_text(style_config.STYLE_SOURCE.read_text(encoding='utf-8').replace(
                '东方水墨修仙3D国漫，电影级三维动画质感',
                '东方水墨修仙3D国漫，更新后的电影级三维动画质感', 1), encoding='utf-8')
            with patch.object(style_config, 'STYLE_SOURCE', edited):
                self.assertIn('更新后的', presets()[0]['prompt'])
                save_style(new_work, '新作', 'xianxia_3d')
            self.assertEqual(load_style(old_work)['prompt'], original)
            self.assertIn('更新后的', load_style(new_work)['prompt'])

    def test_legacy_preset_upgrade_keeps_character_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            legacy = {'version': 1, 'work_title': '旧作', 'status': 'confirmed',
                      'selected_preset': 'xianxia_3d', 'medium': '3D 动画',
                      'prompt': '旧版已确认的人物风格'}
            (work / style_config.CONFIG_NAME).write_text(json.dumps(legacy), encoding='utf-8')
            self.assertIsNone(resolve(work, work_dir=work, work_title='旧作')['style_scene_prompt'])
            upgrade(work, '旧作')
            saved = load_style(work, '旧作')
            self.assertEqual(saved['prompt'], legacy['prompt'])
            self.assertEqual(saved['prompts']['character'], legacy['prompt'])
            self.assertIn('三维环境', saved['prompts']['scene'])
            self.assertIn('三维物品', saved['prompts']['prop'])


if __name__ == '__main__':
    unittest.main()
