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

常用顺序：`jb → rw / dj / cj → fj → h3`。也可以单独使用其中一个 Skill。

每次运行 `/manju-jb` 前选择或确认本作品视觉风格；设置保存在该作品输出目录的 `视觉风格配置.json`，供后续技能使用。

## 获取与安装

```bash
git clone git@github.com:wangyanxi2019/manju-skills.git
cd manju-skills
./install.sh
```
