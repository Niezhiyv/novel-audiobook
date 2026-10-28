# 离线多人有声小说

[![CI](https://github.com/Niezhiyv/novel-audiobook/actions/workflows/ci.yml/badge.svg)](https://github.com/Niezhiyv/novel-audiobook/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个面向 Windows 的本地桌面工具：导入中文 TXT 小说，自动识别章节、旁白与对白，人工校正说话人和音色后，使用 Kokoro 在本地生成分章 MP3。小说文本、模型推理和音频处理都不依赖云端服务。

> 项目处于 `0.1.0` 早期阶段，适合测试和参与共建。仓库不包含 TTS 模型、生成音频或预编译 EXE。

## 功能

- 导入 UTF-8、GB18030/GBK、UTF-16 编码的 TXT 文件。
- 识别常见中文章节标题，分离旁白和中文引号对白。
- 从“林舟说道”等明确提示提取角色名，代词保持未分配。
- 批量修改说话人、合并角色别名、分配音色和语速。
- 章节改名、按片段边界拆分、连续合并。
- 后台逐章生成，支持进度显示、停止、失败记录和重试。
- 片段级音频缓存，角色音色变化时只重新生成受影响片段。
- 按 `序号 - 章节名.mp3` 导出音频并保存项目状态。

## 环境要求

- Windows 10/11
- Python 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- 可用的 Kokoro v1.1-zh 本地模型文件

## 快速开始

```powershell
git clone https://github.com/Niezhiyv/novel-audiobook.git
cd novel-audiobook
uv sync --all-groups
```

按照 [Kokoro 配置](docs/kokoro-setup.md) 下载模型和音色包。校验值通过后启动应用：

```powershell
uv run python -m app
```

也可以在安装完依赖与模型后，双击根目录中的 `启动小说转听书.cmd`。示例文本位于 [examples/sample-novel.txt](examples/sample-novel.txt)。

## 测试

自动化测试使用确定性的假 TTS，不加载真实模型，也不访问网络：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
uv run pytest -q
```

安装真实模型后，可单独验证六个内置中文音色：

```powershell
uv run python scripts/check_kokoro.py
```

## 构建 Windows 单文件程序

先安装完整开发依赖并配置 Kokoro 模型，然后运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

构建结果位于项目根目录的 `小说转听书.exe`，该文件已被 `.gitignore` 排除。当前源码仓库不发布预编译程序；如后续需要，可在 GitHub Releases 中单独发布经过许可证审查的构建产物。

## 项目结构

| 目录 | 用途 |
|---|---|
| `app/importers/` | 文本编码识别与导入 |
| `app/parsing/` | 章节、对白和说话人解析 |
| `app/services/` | 项目与章节生成流程 |
| `app/tts/` | Kokoro 引擎、音色配置和缓存 |
| `app/audio/` | 音频合并与 MP3 导出 |
| `app/ui/` | PySide6 桌面界面 |
| `tests/` | 单元、服务和端到端测试 |

更完整的设计记录位于 `docs/superpowers/`。

## 隐私与内容

应用不上传小说文本、项目数据或生成音频。请仅导入和生成你有权使用的内容。模型文件来自 Kokoro 的公开发布页，其许可与使用条件请以对应发布页为准；本仓库的 MIT 许可证仅覆盖本仓库中的原创软件代码和文档。

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按 [SECURITY.md](SECURITY.md) 私密报告。

## 许可证

本项目采用 [MIT License](LICENSE)。
