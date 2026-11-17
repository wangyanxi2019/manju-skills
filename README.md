# manju-skills

六个可串联使用的漫剧 Skill：从小说原文制作 15 秒分镜，整理人物、道具与场景资产，再生成四宫格和 MiniMax H3 视频提示词。每一步交付 Markdown、结构化 JSON 和可搜索、可复制提示词的离线 HTML。

| Skill | 作用 |
| --- | --- |
| `/manju-jb` | 按可编辑的分镜规则，将小说拆为 15 秒分镜组；指定单章时核对前后约三章的上下文。 |
| `/manju-rw` | 合并人物代称，生成角色形象、正侧背设定图提示词；为发声角色建立可复制的固定声线描述。 |
| `/manju-dj` | 提取关键物品及真实出现的状态，生成白底单物品图提示词。 |
| `/manju-cj` | 提取场景及开关门、昼夜等状态，生成无人场景图与三视图提示词。 |
| `/manju-fj` | 将每个分镜组转换为横向 2×2 四宫格提示词，保留四格与原镜头的映射。 |
| `/manju-h3` | 结合文字分镜与实际参考素材，生成六字段的 MiniMax H3 视频提示词。 |

常用顺序：`jb → rw / dj / cj → fj → h3`。可按需要只运行其中一步，但后续步骤仍须核对原始素材。各 Skill 的详细规则在对应 `SKILL.md`，JSON 交接格式见 [`manju-shared/OUTPUT_FORMAT.md`](manju-shared/OUTPUT_FORMAT.md)。

## 获取与安装

```bash
git clone git@github.com:wangyanxi2019/manju-skills.git
cd manju-skills
./install.sh
```

安装脚本会把六个 Skill 和 `manju-shared` 链接到当前仓库。以后直接修改仓库里的规则、风格或程序即可生效，无需手动填写路径。已有的同名安装目录会先备份到 `~/.agents/skills/.manju-skills-backups/`。安装完成后脚本会自动打印所选项目和规则路径。

需要手动核对或重新生成 HTML 时，可运行：

```bash
python3 manju-shared/resolve_project.py
python3 manju-shared/render_preview.py 预览示例/第1集-01_manju-fj.json
```

仓库中的 `project.json` 不包含个人路径。若另建项目，可在运行解析器时使用 `--project /项目/绝对路径`，并在该目录准备项目规则与已确认的风格文件。`manju-shared/preview_style.css` 控制六个 Skill 共用的离线预览外观；修改后重新运行渲染器生成已有 HTML。移动仓库到新位置后重新运行 `./install.sh`，链接会更新。

## 参考素材与边界

- `manju-jb/references/分镜脚本.txt`、`manju-rw/references/人物三视图例子.txt`、`manju-h3/references/视频大师提示词.txt` 是可编辑的项目规则副本。小说、图片、音频由使用者在运行时提供，不包含在本仓库。
- 人物与场景的图片提示词使用项目已确认的共用风格。四宫格提示词使用参考图锁定外观；物品按当前项目要求保留真实白底单物品图。
- H3 的官方格式资料来自 [MiniMax-AI/MiniMax-H3 的 h3-prompt-writing Skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/.agents/skills/h3-prompt-writing)。本仓库提供[来源与适配说明](manju-h3/references/official/SOURCE.md)，不再发布其参考文档全文。说明正文采用本项目要求的中文，官方原文要求英文；运行时以用户要求和当时的官方格式核对。
- 任何声线描述都只是文字生成约束。只有实际提供的音频文件才能作为音频参考素材。

## 检查

共享预览器使用 Python 标准库；回归检查可运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s manju-shared -p test_preview.py
```

发布此仓库并不代表已实测图片或视频模型输出；实际作品仍需核对人物、空间、声音及镜头连续性。
