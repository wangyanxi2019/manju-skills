"""Checks that image-prompt QA catches production metadata without flagging voice text."""
import unittest

from lint_image_prompts import issues


def bundle(skill, prompts):
    return {"skill": skill, "items": [{"id": "01", "prompts": prompts}]}


class ImagePromptLintTests(unittest.TestCase):
    def test_scene_metadata_is_detected(self):
        source = bundle("manju-cj", [{"label": "无人场景图 Prompt", "text":
            "狭小木屋。面积：原文称狭小，没有平方米数。凳子状态：原位置未说明。参考图未上传。"}])
        self.assertEqual({issue[2] for issue in issues(source)},
                         {"unresolved", "provenance", "missing_asset", "status_field"})

    def test_renderable_scene_and_prop_pass(self):
        scene = bundle("manju-cj", [{"label": "无人场景图 Prompt", "text":
            "初秋正午，狭小木屋内，南侧房门紧闭，北侧一把太师椅，土黄色地面。无人。"}])
        prop = bundle("manju-dj", [{"label": "单物品图 Prompt", "text":
            "真实物品，单物品图，白色背景。一只深褐木凳，四足完整，木纹清晰。"}])
        self.assertEqual(issues(scene), [])
        self.assertEqual(issues(prop), [])

    def test_voice_prompt_and_h3_are_out_of_scope(self):
        voice = bundle("manju-rw", [{"label": "固定声线描述 Prompt", "text": "音色未说明。"}])
        h3 = bundle("manju-h3", [{"label": "H3 Prompt", "text": "未上传参考图。"}])
        self.assertEqual(issues(voice), [])
        self.assertEqual(issues(h3), [])


if __name__ == "__main__":
    unittest.main()
