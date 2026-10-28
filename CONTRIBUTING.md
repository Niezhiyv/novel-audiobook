# 参与贡献

感谢你愿意改进这个项目。提交代码前，请先搜索现有 Issue，避免重复工作；较大的功能或行为变更建议先创建 Issue 说明使用场景和设计。

## 开发环境

项目当前面向 Windows 和 Python 3.12。

```powershell
uv sync --all-groups
$env:QT_QPA_PLATFORM = "offscreen"
uv run pytest -q
```

自动化测试使用确定性的假 TTS，不需要下载 Kokoro 模型。需要验证真实模型时，先按 [Kokoro 配置](docs/kokoro-setup.md) 准备本地文件，再运行：

```powershell
uv run python scripts/check_kokoro.py
```

## 提交 Pull Request

1. 从最新的 `master` 创建分支。
2. 为行为变更补充或更新测试。
3. 运行完整测试，并确认工作区中没有模型、音频、密钥或构建产物。
4. 使用清晰、聚焦的提交说明，Pull Request 中写明变更目的和验证方式。

请勿提交 `models/`、`projects/`、`exports/`、虚拟环境、生成的 EXE 或任何凭据。仅提交你有权公开的示例小说文本。
