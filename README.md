# VideoSheet2PDF 🎶

这是一个基于 Python 的自动化工具，专门用于将**视频格式的乐谱**转换为**高清晰度的拼版 PDF 文档**。它通过 OpenCV 自动识别乐谱区域，并利用 FFmpeg 的场景检测功能自动捕捉翻页瞬间。

## 🌟 核心功能

- **自动裁切**：通过 OpenCV 识别视频中乐谱的有效边界，自动计算 `crop` 参数并进行内缩补偿，消除白边。
- **智能抽帧**：利用 FFmpeg `scene detection` 算法，仅在乐谱翻页时提取画面，避免产生冗余帧。
- **高质量合成**：使用 ImageMagick 将提取的页面按 1x5（或自定义）布局拼接，并采用 `Group4` 压缩算法，确保 PDF 既清晰又小巧。
- **单脚本运行**：基于 `uv` 的单文件设计，无需手动管理虚拟环境和依赖。

## 🛠️ 环境要求

你需要安装以下工具：
1. [uv](https://github.com/astral-sh/uv) ( Python 包管理工具)
2. [FFmpeg](https://ffmpeg.org/) (用于视频处理)
3. [ImageMagick](https://imagemagick.org/) (用于 PDF 合成)

> **提示**：如果你安装了 `Scoop`，建议通过 `Scoop` 安装：
> `scoop install uv ffmpeg imagemagick`

## 🚀 快速开始

将脚本保存为 `videosheet2pdf.py`，然后在终端执行：

```bash
uv run videosheet2pdf.py "你的乐谱视频.mp4"
```

## Credits
The core logic for sheet music region detection is inspired by the [Wubaboo/ytSheetMusic](https://github.com/Wubaboo/ytSheetMusic) project.