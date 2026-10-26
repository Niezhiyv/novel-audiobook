# Kokoro 离线模型配置

## 已验证文件

首版使用 `kokoro-onnx 0.6.1` 和 Kokoro v1.1-zh 的 CPU int8 模型。

将以下两个文件放到仓库的 `models/kokoro/`：

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `kokoro-v1.1-zh.int8.onnx` | 114,120,125 字节 | `11751c087b4bbeed031e2b687b11dda698bd27ba0509472f960b57f835a999f7` |
| `voices-v1.1-zh.bin` | 53,815,880 字节 | `14cb6186c99e4f6016871405f62046c5df863ae27465cbdc4ee08be7dd703acd` |

官方下载地址：

- <https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.1-zh.int8.onnx>
- <https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.1-zh.bin>

模型和音色文件不得提交到 Git，仓库已通过 `.gitignore` 排除 `models/`。

## 内置中文音色

v1.1-zh 音色包共包含 103 个音色。当前界面固定提供以下六个经过检查的中文音色：

| ID | 界面标签 |
|---|---|
| `zf_001` | 中文女声 1 |
| `zf_002` | 中文女声 2 |
| `zf_003` | 中文女声 3 |
| `zm_009` | 中文男声 1 |
| `zm_010` | 中文男声 2 |
| `zm_011` | 中文男声 3 |

这些 ID 来自实际 `voices-v1.1-zh.bin` 文件，不是通用 Kokoro v1.0 的音色名称。

## 自定义路径

可通过环境变量覆盖默认路径：

```powershell
$env:KOKORO_MODEL_PATH = "D:\models\kokoro-v1.1-zh.int8.onnx"
$env:KOKORO_VOICES_PATH = "D:\models\voices-v1.1-zh.bin"
$env:KOKORO_LANGUAGE = "cmn"
```

v1.1-zh 模型的 vocabulary 已内嵌，无需设置 `KOKORO_VOCAB_PATH`。

## 验证六音色

```powershell
uv run python scripts/check_kokoro.py
```

脚本会在 `models/kokoro/previews/` 生成六段 WAV 和 `manifest.json`。整个检查过程不访问网络。

## Windows 中文路径说明

`espeak-ng` 在部分 Windows 环境下无法直接读取包含中文的安装路径。应用会把 G2P 数据复制到纯 ASCII 临时目录：

```text
%TEMP%\novel-audiobook\espeak-ng-data
```

模型文件本身可以继续放在包含中文的仓库路径中。

## 断网验收

1. 下载并核对上述两个文件。
2. 执行一次 `uv run python scripts/check_kokoro.py`。
3. 断开网络。
4. 执行 `uv run python -m app`。
5. 使用 `examples/sample-novel.txt` 创建项目，分配音色并生成章节 MP3。
