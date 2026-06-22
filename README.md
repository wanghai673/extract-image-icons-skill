# Extract Image Icons Skill

[![English](https://img.shields.io/badge/docs-English-blue)](README_en.md) [![CI](https://github.com/wanghai673/extract-image-icons-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/wanghai673/extract-image-icons-skill/actions/workflows/ci.yml) [![GitHub stars](https://img.shields.io/github/stars/wanghai673/extract-image-icons-skill?style=flat&logo=github&label=stars)](https://github.com/wanghai673/extract-image-icons-skill/stargazers)

一个用于从截图、幻灯片、海报、流程图和其他合成图片中提取可复用视觉元素的 Codex Skill。它会先盘点并去重图标，再通过源图引导的 `gpt-image-2` 编辑生成稀疏资产表，最后确定性地去除纯色背景、拆分并导出带语义文件名的透明 PNG。

适合提取图标、徽章、Logo、吉祥物、贴纸、人物插画和其他独立视觉对象；不用于 OCR 文字提取，也不把普通箭头、连接线、卡片边框等布局元素当作图标。

> [!IMPORTANT]
> 本 Skill 的资产表生成阶段需要图片编辑能力。默认优先读取 `~/.codex/auth.json` 中的 Codex OAuth；不可用时可使用 `OPENAI_API_KEY`、可选的 `OPENAI_BASE_URL` 和 Python `openai` 包。

> [!WARNING]
> 生成式分离可能在低分辨率图标上产生重绘差异。工作流要求逐项与源图对比；当轮廓、姿态、颜色、配件或内部结构发生变化时，不得把结果报告为严格忠实。

## 特点

- 提取前建立完整图标清单，排除文字和普通布局元素。
- 对视觉上完全相同的重复图标去重。
- 每张资产表最多放置 9 个图标，并支持多资产表并发生成。
- 使用纯色键控背景，确定性转换为透明通道。
- 将资产表拆分为独立、方形、带语义名称的透明 PNG。
- 验证数量、名称、PNG/RGBA、透明度、尺寸和边缘裁切。
- 保留 inventory、批次计划、实际图片任务、拆分 manifest 和验证报告。

## 安装

在 Codex 中输入：

```text
安装 extract-image-icons 这个 skill，地址是 https://github.com/wanghai673/extract-image-icons-skill
```

也可以把 `skills/extract-image-icons` 复制到 `${CODEX_HOME:-~/.codex}/skills/`。

## 使用方式

```text
$extract-image-icons 把这张图片里的图标提取成透明 PNG。
$extract-image-icons 提取这个流程图中的人物和工具图标，并去重。
$extract-image-icons 把这组截图里的可复用视觉元素分别导出。
```

Skill 会执行以下流程：

1. 检查图片生成认证和本地图片处理依赖。
2. 盘点非文字视觉对象并写入 `icon_inventory.json`。
3. 把图标分配到每批不超过 9 个的资产表任务。
4. 以原图作为编辑输入，通过 `gpt-image-2` 生成纯色背景资产表。
5. 去除键控背景，检测组件并核对实际顺序。
6. 使用语义名称重新拆分，逐项做视觉检查和结构验证。

## 运行要求

- Python 3.10+
- Pillow
- 图片编辑认证任选其一：
  - 已登录 Codex，且存在 `~/.codex/auth.json`
  - `OPENAI_API_KEY`（可选 `OPENAI_BASE_URL`）和 `openai` Python 包

运行环境自检：

```bash
python skills/extract-image-icons/scripts/generate_icon_sheets.py --doctor
python skills/extract-image-icons/scripts/process_icon_sheet.py --self-test
```

## 输出结构

```text
run-dir/
├── icon_inventory.json
├── batch_plan.json
├── image-jobs.jsonl
├── generated/                 # gpt-image-2 生成的纯色背景资产表
├── intermediates/             # 透明化后的资产表
├── raw/                       # 未命名的组件切分结果
├── icons/                     # 最终语义命名的透明 PNG
├── manifests/                 # 原始与命名拆分记录
└── icons_validation.json
```

## 仓库结构

```text
.
├── .github/workflows/ci.yml
├── skills/extract-image-icons/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/
│   └── scripts/
├── AGENTS.md
├── CHANGELOG.md
├── LICENSE
├── README.md
└── README_en.md
```

## 许可证

MIT
