# 离线多人有声小说

Windows 本地桌面工具：导入中文 TXT，识别章节和说话人，人工校正角色归属，并使用本地 Kokoro 中文音色生成分章 MP3。小说文本、模型推理和音频处理都不依赖云端服务。

## 当前功能

- 导入 UTF-8、GB18030/GBK、UTF-16 TXT。
- 识别常见中文章节标题。
- 分离旁白和中文引号对白。
- 从“林舟说道”等明确提示提取角色，代词保持未分配。
- 批量修改说话人、合并角色别名、为角色分配音色和语速。
- 章节改名、按片段边界拆分、连续合并。
- 后台逐章生成、进度显示、停止、失败记录和重试。
- 片段级音频缓存，角色音色变化时只重生成受影响片段。
- 导出 `序号 - 章节名.mp3` 并保存项目状态。

## 环境

- Windows
- Python 3.12
- [uv](https://docs.astral.sh/uv/)

```powershell
uv sync --all-groups
```

## 模型

将 v1.1-zh int8 模型和音色包放入 `models/kokoro/`。文件、校验值、六个内置音色和断网步骤见 [Kokoro 配置](docs/kokoro-setup.md)。

模型缺失时仍可创建或打开项目，实际生成或试听时会提示模型配置不完整。

## 启动

```powershell
uv run python -m app
```

示例文本位于 `examples/sample-novel.txt`。

## 测试

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
uv run pytest -q
```

自动化测试使用确定性假 TTS，不加载真实模型、不访问网络。真实模型检查单独执行：

```powershell
uv run python scripts/check_kokoro.py
```
