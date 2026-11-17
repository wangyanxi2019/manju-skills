# 漫剧输出格式

每个 Skill 交付同名的 `.json`、`.md`、`.html`。按各 Skill 原有模板写 Markdown，同时保存相同 Prompt 的 JSON，然后运行 `render_preview.py` 生成离线 HTML。HTML 在手机和桌面浏览器打开，Prompt 卡片有“复制”按钮和搜索框，无外部字体、脚本或服务依赖。渲染器默认不覆盖 Markdown；只有在没有既定 Markdown 格式时才加 `--write-markdown` 自动生成。

## 命令

```bash
python3 /path/to/manju-shared/render_preview.py /path/to/作品_范围_manju-fj.json
```

桌面项目中脚本位于 `manju-skill/manju-shared/render_preview.py`。安装到个人 Skills 目录后，脚本位于与各 Skill 同级的 `manju-shared/render_preview.py`。离线 HTML 的共用视觉主题在同目录 `preview_style.css`，由渲染器读入并内嵌到每个输出文件；修改主题后需重新运行渲染器生成已有 HTML。主题参考本项目的剧本报告页面：浅灰纸面、朱红强调色、宋体标题、细边框、紧凑内容卡。复制、搜索、下载功能由渲染器保留。

## JSON 结构

```json
{
  "schema_version": "1",
  "skill": "manju-fj",
  "title": "作品名 · 第1集四宫格提示词",
  "subtitle": "可选的范围说明",
  "source_files": ["分镜脚本.md", "参考图目录"],
  "items": [
    {
      "id": "01-01",
      "title": "第1集-01｜15秒",
      "summary": "本组故事概况",
      "fields": [
        {"label": "场景", "value": "房内与门外道路"},
        {"label": "镜头", "value": "4镜，15秒"}
      ],
      "prompts": [
        {"label": "四宫格绘图 Prompt", "text": "生成一张横向2×2四宫格分镜图……"}
      ],
      "notes": ["可选的本条核对事项"],
      "data": {"record_id": "01-01-grid1"}
    }
  ],
  "notes": ["可选的全局核对事项"],
  "data": {
    "grids": [{
      "id": "01-01-grid1",
      "group_id": "01-01",
      "image_path": null,
      "reference_assets": [],
      "panel_map": {"top_left":"01-01-S01", "top_right":"01-01-S02", "bottom_left":"01-01-S03", "bottom_right":"01-01-S04"},
      "uncovered_shot_ids": [],
      "spatial_layout": "此处保存完整固定空间关系",
      "sources": [{"file":"分镜脚本.md", "locator":"01-01", "basis":"storyboard"}]
    }]
  }
}
```

`schema_version`、`skill`、`title`、`items` 必填。`skill` 是六个技能名之一。每个 item 的 `id` 为唯一的非空字符串，`title` 必填，`prompts` 至少一条，每条有非空 `label` 和 `text`。`fields` 中 `label/value` 都为字符串；`notes/source_files` 是字符串数组，`data` 是对象。`fields`、`notes` 可省略。提取结果确实为空时允许 `items: []`，但根 `notes` 必须说明范围和未发现结果，不造一个假角色／道具来凑条目。

`data` 保存下游复用的结构化事实，renderer 不展示也不改写。交付前核对 Markdown 与 JSON 的每条 Prompt 正文一致，HTML 直接显示 JSON 中的同一正文。渲染器会检查基础类型和重复 item ID，并检查已有 Markdown 是否含有每条完整 Prompt；发现不一致会停止写入。它不验证小说事实、全量覆盖或全部领域字段，这些仍需逐项核对。

## 各 Skill 的 `data` 约定

下游读取 JSON 时先核对 `skill` 与 `schema_version`。原始小说、分镜或图片仍是最终事实来源，JSON 是已确认信息的索引。缺少上游 JSON 时继续读取原始素材。

- `manju-jb`：根 `data.groups[]` 保留组号、章节、场景、人物、物品、站位、各镜时长与完整文字、台词、音效和结尾状态。每组 `items[].prompts[]` 放可复制的完整分镜组。
- `manju-rw`：根 `data.characters[]` 保留人物 ID、规范名、代称、外貌字段、服装版本与出处。每个角色 item 有人物形象和三视图两条 Prompt。
- `manju-dj`：根 `data.objects[]` 保留物品 ID、代称、外观五字段、状态版本与出处。每个物品状态 item 有单物品图 Prompt。
- `manju-cj`：根 `data.scenes[]` 保留场景 ID、代称、固定空间坐标、面积依据和状态版本。每个场景状态 item 有无人场景图及三视图 Prompt。
- `manju-fj`：根 `data.grids[]` 保留分镜组号、参考图映射、四格与镜头映射、固定空间关系。每组 item 有一条四宫格绘图 Prompt。
- `manju-h3`：根 `data.videos[]` 保留分镜组号、实际素材标签、切镜时间、对白与声音来源。每组 item 有一条六字段 H3 提示词。

## 交接字段与唯一来源

新增输出将事实明细统一保存于上述根 `data` 数组。每条记录有唯一 `id`，`items[].data.record_id` 指向该记录。不要同时维护两份不同的事实。旧版只在 `items[].data` 存事实时可以读取并迁移；根和 item 两处冲突须记录，不静默选取。`schema_version: "1"` 的旧预览仍可渲染，事实字段不齐全时由原始素材补齐，不把空数组当作“原文没有”。

所有领域记录保留 `sources` 数组，元素格式为 `{"file":"输入文件路径","locator":"章节／段落／组号","basis":"original|storyboard|image|visual_fill"}`；`basis` 只取其中一值。视觉补全也要明确说明依据，不能冒充原文事实。ID 沿用上游，不因排序变动重编号；跨文件记录以 `skill + id` 区分。

- `groups[]`：`id`（组号）、`chapter`、`scene`、`characters`、`objects`、`spatial_layout`、`opening_state`、`ending_state`、`duration_seconds`、`shots[]`。每镜保留 `shot_id`、`index`、`duration_seconds`、`text`（完整分镜）、`dialogue[]`、`sound`。对白元素保存 `speaker`、`text`、`kind`（dialogue/os/narration），有声线卡时加 `voice_profile_id`；实际提供音频才有 `audio_path`。不以故事概况替代镜头正文。
- `characters[]`：`id`（造型记录）、`character_id`（人物身份）、`name`、`aliases[]`、`appearance`（age/gender/hair_color/hair_style/eye_color/upper_clothing/lower_clothing）、`version`、`scope`。每个外观字段同时保存 `value` 与 `basis`。有发声者另存 `voice_profile`：稳定的 `voice_profile_id`、固定声线 `description`、`register`、`timbre`、`breath`、`pace`、`accent_or_articulation`、`pause_habit`、`scope`、`sources`，以及 `reference_audio`（`status` 为 uploaded/missing；未上传时 `path` 为 null）。声线字段按来源标注，不将描述文本当作实际音频。
- `objects[]`：`id`（状态记录）、`object_id`（物品身份）、`name`、`aliases[]`、`appearance`（shape/material/color/size/marks，值同样带 basis）、`state`、`scope`。描述值不含人名。
- `scenes[]`：`id`（状态记录）、`scene_id`（场景身份）、`name`、`aliases[]`、`environment`、`time`、`atmosphere`、`area`（value/basis）、`spatial_layout`、`state`（门／灯等逐对象记录）、`unverified_regions[]`、`scope`。
- `grids[]`：`id`（图片记录）、`group_id`、`image_path`（未上传时为 null）、`reference_assets[]`、`panel_map`、`uncovered_shot_ids[]`、`spatial_layout`。`reference_assets` 保存 `ref_id`、`kind`、`name`、`path`、`status`（uploaded/planned）；拟上传的 path 为 null，不能在 H3 当作实际素材。
- `videos[]`：`id`、`group_id`、`assets[]`（实际文件路径、标签和参考作用）、`shots[]`（shot_id/start_seconds/duration_seconds/grid_id/panel/dialogue/sound/voice_profile_id）、`duration_seconds`。无对应格图时 `grid_id/panel` 为 null；没有发声时 `voice_profile_id` 为 null。切点从原镜头时长累计，不能用四格顺序重排五镜。`<Audio N>` 只能引用 `assets[]` 中已存在的真实音频，文字声线卡只通过 ID 关联。

四格到原镜头的映射示例（五镜选择第1、2、4、5镜）：

```json
{
  "id": "EP01-G01-grid1",
  "group_id": "EP01-G01",
  "panel_map": {
    "top_left": "EP01-G01-S01",
    "top_right": "EP01-G01-S02",
    "bottom_left": "EP01-G01-S04",
    "bottom_right": "EP01-G01-S05"
  },
  "uncovered_shot_ids": ["EP01-G01-S03"]
}
```

映射的四个键齐全且值必须是该组存在的 shot_id。未成格镜头仍属于视频脚本；辅助图可覆盖它，沿用原 group_id 并给独立 grid id。原文件尚无 ID 时先建立一次稳定 ID，并在对应表中记录，后续沿用。
