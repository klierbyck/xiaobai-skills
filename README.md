# xiaobai-skills

这里集中存放多个可以独立安装的 Skill。

## 当前可用 Skill

| Skill ID | 目录 | 用途 |
| --- | --- | --- |
| `image-gen` | `skills/image-gen/` | 通过可配置的图片 API 完成文生图、参考图生图和持续图片编辑，支持 OpenAI Images 与 Gemini 兼容接口。 |
| `media-transcriber` | `skills/media-transcriber/` | 处理本地视频或音频，生成完整书面稿，并保留原始转写、字幕和相关证据。 |
| `skillsvc-image` | `skills/skillsvc-image/` | 使用 Skillsvc 图片 API 进行文生图、参考图生图、持续编辑和图文配图。包含公众号、小红书、贴图号和活人写作等包内模块。 |

完整的机器可读清单见 [catalog.yaml](catalog.yaml)。

## 目录约定

每个 Skill 放在 `skills/<skill-id>/` 下，并保留它自己的完整目录结构：

```text
skills/
└── <skill-id>/
    ├── SKILL.md          # 如果该 Skill 使用此入口文件
    ├── skill.yaml        # 可选：名称、版本和描述
    ├── scripts/          # 可选：脚本
    ├── references/       # 可选：参考资料
    └── assets/            # 可选：模板、图片等资源
```

安装某个 Skill 时，只安装对应的 `skills/<skill-id>/` 目录，不安装其他 Skill，也不要改变目录结构。

新增 Skill 后，请在 `skills/` 下创建独立目录，并同步补充 [catalog.yaml](catalog.yaml) 和上面的可用列表。

## 给 AI 的安装规则

仓库地址：

```text
https://github.com/klierbyck/xiaobai-skills.git
```

收到这个仓库地址后，AI 必须按照用户是否指定 Skill 执行：

### 用户没有指定 Skill

只读取 `skills/` 下的一级目录，列出所有可安装 Skill 的 ID 和简介，然后询问用户要安装哪一个，或是否安装全部。此时不要直接安装。

示例回复：

```text
这个仓库包含以下 Skill：

1. image-gen：图片生成与编辑
2. media-transcriber：音频和视频转写整理
3. skillsvc-image：Skillsvc 图片生成与图文配图

请选择要安装的 Skill，或者回复“全部安装”。
```

### 用户指定了具体 Skill

只安装 `skills/<skill-id>/` 对应目录，保留该目录的完整结构，不安装其他 Skill。

例如用户说：

```text
请帮我安装 image-gen：
https://github.com/klierbyck/xiaobai-skills.git
```

只能安装：

```text
skills/image-gen/
```

### 用户明确要求全部安装

安装 `skills/` 下的所有一级 Skill 目录。隐藏文件、`.gitkeep` 和其他仓库文件不算 Skill。

### 用户指定了不存在的 Skill

不要猜测或安装相似名称。列出实际可用的 Skill ID，请用户重新选择。

安装 `skillsvc-image` 时，需要安装整个 `skills/skillsvc-image/` 目录，因为它包含自己的 `gzh-image`、`human-writing` 和 `xhs-image` 模块。它们是包内模块，不是本仓库的一级可安装 Skill。

Skill 是否能被使用，以及最终安装到哪里，由当前 AI 平台决定。
