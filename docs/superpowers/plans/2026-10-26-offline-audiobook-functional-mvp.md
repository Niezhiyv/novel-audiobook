# 离线多人有声小说功能 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先交付一个能从中文 TXT 创建项目、校正角色、生成并导出章节 MP3 的可运行 Windows 桌面 MVP。

**Architecture:** 使用单进程 PySide6 桌面应用；领域服务与 Qt UI 分离，SQLite 保存项目状态，后台线程执行章节生成，TTS 通过协议隔离真假实现，音频先缓存为 WAV 再合成为章节 MP3。

**Tech Stack:** Python 3.12、PySide6、SQLite、NumPy、SoundFile、imageio-ffmpeg、kokoro-onnx、pytest、pytest-qt、uv

**Spec:** `docs/superpowers/specs/2026-10-26-offline-multivoice-audiobook-mvp-design.md`

## Global Constraints

- 目标平台是 Windows 桌面，中文界面，核心流程不能依赖开发者命令行。
- 使用独立的 Python 3.12 环境；不得直接使用系统 Python 3.14 作为运行环境。
- 依赖、模型和工具版本必须锁定；仓库不提交模型文件。
- 应用运行和生成过程不得联网，不得上传小说文本。
- 未分配角色必须保持“未分配”，不得静默套用随机声音。
- 单段失败、取消或程序异常不能删除已经完成的章节音频。
- 每章导出为 `序号 - 章节名.mp3`。
- 自动化测试默认使用假 TTS，不依赖网络、模型文件或 GPU。
- 每次改动必须有对应测试，并且测试通过后创建独立 Git 提交。

## Review Focus

- 输入文件编码错误或内容为空时，应用应给出可定位错误，不能覆盖已有项目。
- 中文引号、前置/后置说话提示混排时，角色必须正确归属或明确保持未分配。
- TTS 取消、失败和重试时，已经成功的音频缓存必须保留且不得产生损坏的章节 MP3。
- 长章节生成时 UI 必须保持响应，进度和错误必须能回到正确章节。
- 修改单个角色音色时，只允许相关片段缓存失效，其他角色和章节结果应继续复用。

---

### Task 1: 建立 Python 3.12 工程与可测试启动壳

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/__main__.py`
- Create: `tests/test_smoke.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: 无
- Produces: `python -m app` 启动入口；`app.__version__: str`；锁定依赖的 uv 工程

- [ ] **Step 1: 安装 uv 与 Python 3.12，并初始化项目环境**

Run:
```powershell
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.12
uv venv --python 3.12
```

Expected: `uv run python --version` 输出 `Python 3.12.x`。

- [ ] **Step 2: 写失败测试**

测试 `test_package_exposes_version()` 断言 `app.__version__ == "0.1.0"`；测试 `test_module_entrypoint_is_importable()` 能导入 `app.__main__`。

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: FAIL，因为 `app` 尚不存在。

- [ ] **Step 4: 创建最小工程、依赖和启动入口**

`pyproject.toml` 锁定 Python 3.12，并声明 PySide6、NumPy、SoundFile、imageio-ffmpeg、kokoro-onnx、pytest、pytest-qt。`.gitignore` 排除 `.venv/`、模型、缓存、项目数据和导出音频。`app.__main__` 暂时只显示一个最小 PySide6 窗口。

- [ ] **Step 5: 生成锁文件并验证**

Run:
```powershell
uv lock
uv sync --all-groups
uv run pytest tests/test_smoke.py -v
```

Expected: 测试 PASS，`uv.lock` 存在。

- [ ] **Step 6: 提交**

```powershell
git add pyproject.toml uv.lock app tests/test_smoke.py .gitignore
git commit -m "chore: bootstrap Python desktop app"
```

---

### Task 2: 实现项目领域模型与 SQLite 持久化

**Files:**
- Create: `app/domain/__init__.py`
- Create: `app/domain/models.py`
- Create: `app/storage/__init__.py`
- Create: `app/storage/database.py`
- Create: `app/storage/repository.py`
- Create: `tests/storage/test_repository.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `SegmentKind(str, Enum): NARRATION, DIALOGUE`
  - `ChapterStatus(str, Enum): PENDING, RUNNING, COMPLETED, FAILED`
  - dataclasses `Project`, `Chapter`, `Segment`, `Role`
  - `ProjectRepository.create_project(root: Path, title: str, source_text: str) -> Project`
  - `ProjectRepository.open_project(root: Path) -> Project`
  - `ProjectRepository.save_chapters(chapters: Sequence[Chapter]) -> None`
  - `ProjectRepository.load_chapters() -> list[Chapter]`
  - `ProjectRepository.save_segment(segment: Segment) -> None`
  - `ProjectRepository.save_role(role: Role) -> None`

- [ ] **Step 1: 写失败测试**

测试项目创建后存在 `source.txt`、`project.sqlite3` 和 schema version；测试章节、片段、角色写入后重新打开仓库仍完整；测试重复打开不会重建或清空数据库。

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/storage/test_repository.py -v`
Expected: FAIL，因为领域模型和仓库不存在。

- [ ] **Step 3: 实现模型、schema 和原子初始化**

使用 dataclass 表达领域对象；SQLite 使用事务写入，首版通过 `PRAGMA user_version` 做 schema 版本检查。项目初始化先写临时目录再原子改名为目标目录，目标已存在且不是有效项目时不得覆盖。

- [ ] **Step 4: 运行测试和时间相关回归测试**

Run: `uv run pytest tests/storage/test_repository.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add app/domain app/storage tests/storage
git commit -m "feat: persist audiobook projects in sqlite"
```

---

### Task 3: 导入 TXT、拆分章节、分离对白与识别明确角色

**Files:**
- Create: `app/importers/__init__.py`
- Create: `app/importers/text_importer.py`
- Create: `app/parsing/__init__.py`
- Create: `app/parsing/chapter_parser.py`
- Create: `app/parsing/dialogue_parser.py`
- Create: `app/parsing/speaker_resolver.py`
- Create: `tests/importers/test_text_importer.py`
- Create: `tests/parsing/test_chapter_parser.py`
- Create: `tests/parsing/test_dialogue_parser.py`
- Create: `tests/parsing/test_speaker_resolver.py`

**Interfaces:**
- Consumes: `SegmentKind`
- Produces:
  - `decode_txt(path: Path) -> str`
  - `normalize_text(text: str) -> str`
  - `split_chapters(text: str) -> list[ParsedChapter]`
  - `split_segments(text: str) -> list[ParsedSegment]`
  - `resolve_explicit_speakers(segments: Sequence[ParsedSegment]) -> list[ParsedSegment]`
  - `ParsedSegment(kind: SegmentKind, text: str, speaker_name: str | None, confidence: float, evidence: str | None)`

- [ ] **Step 1: 写失败测试**

覆盖 UTF-8、GBK、UTF-16 和混合换行；覆盖“第X章”、`Chapter N`、无标题长文本和空文件；覆盖中文弯引号、前后置“林舟说道”、无提示对白、代词不自动归属；别名测试确保“林舟”和“林师兄”只在人工确认映射后合并。

- [ ] **Step 2: 运行解析测试确认失败**

Run:
```powershell
uv run pytest tests/importers tests/parsing -v
```
Expected: FAIL，因为导入器和解析器不存在。

- [ ] **Step 3: 实现可解释解析管线**

编码检测使用有限候选顺序并验证可解码性；章节识别只接受高置信标题；对白解析保留原文顺序；角色提取仅接受名字加明确说话动词，证据保存匹配文本。低置信结果返回 `speaker_name=None`。

- [ ] **Step 4: 运行测试**

Run:
```powershell
uv run pytest tests/importers tests/parsing -v
```
Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add app/importers app/parsing tests/importers tests/parsing
git commit -m "feat: import and parse Chinese novel text"
```

---

### Task 4: 把导入、角色修正和音色分配串成项目服务

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/project_service.py`
- Create: `tests/services/test_project_service.py`

**Interfaces:**
- Consumes: `ProjectRepository`, `decode_txt`, `split_chapters`, `split_segments`, `resolve_explicit_speakers`
- Produces:
  - `ProjectService.create_from_txt(root: Path, title: str, source_path: Path) -> Project`
  - `ProjectService.fetch_workspace() -> ProjectWorkspace`
  - `ProjectService.assign_speaker(segment_ids: Sequence[int], role_id: int | None) -> None`
  - `ProjectService.create_or_merge_role(name: str, aliases: Sequence[str]) -> Role`
  - `ProjectService.assign_voice(role_id: int, voice_id: str, speed: float) -> None`
  - `ProjectService.rename_chapter(chapter_id: int, title: str) -> None`
  - `ProjectService.split_chapter(chapter_id: int, offset: int, new_title: str) -> tuple[Chapter, Chapter]`
  - `ProjectService.merge_chapters(chapter_ids: Sequence[int], title: str) -> Chapter`

- [ ] **Step 1: 写失败测试**

使用内置中文示例文本创建项目并断言章节、片段、角色数量；批量修改一组片段的角色；确认未分配片段不会被自动赋声；确认角色别名合并后仍指向同一角色；确认章节改名、按片段边界拆分和按阅读顺序合并不丢失片段。

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/services/test_project_service.py -v`
Expected: FAIL，因为项目服务不存在。

- [ ] **Step 3: 实现事务化项目服务**

创建项目在任何持久化前完成解码、解析和输入校验；批量角色修改、章节拆分和章节合并使用单个事务；拆分/合并后重新编号并保持导出文件名稳定；角色与音色保存为独立状态，没有音色时保持未分配。

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/services/test_project_service.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add app/services tests/services
git commit -m "feat: manage audiobook project workflow"
```

---

### Task 5: 实现可替换 TTS、片段缓存和 MP3 章节合成

**Files:**
- Create: `app/tts/__init__.py`
- Create: `app/tts/base.py`
- Create: `app/tts/fake_engine.py`
- Create: `app/tts/kokoro_engine.py`
- Create: `app/audio/__init__.py`
- Create: `app/audio/assembler.py`
- Create: `tests/tts/test_fake_engine.py`
- Create: `tests/tts/test_cache_key.py`
- Create: `tests/audio/test_assembler.py`

**Interfaces:**
- Consumes: `Segment`, `Role`
- Produces:
  - `TTSEngine.synthesize(text: str, voice_id: str, speed: float) -> AudioClip`
  - `AudioClip(samples: np.ndarray, sample_rate: int)`
  - `FakeTTSEngine`
  - `KokoroTTSEngine(model_path: Path, voices_path: Path, voices: Mapping[str, str])`
  - `chunk_text(text: str, max_chars: int = 180) -> list[str]`
  - `AudioCache(root: Path, model_version: str)`
  - `AudioCache.key(text: str, voice_id: str, speed: float) -> str`
  - `ChapterAssembler.render(chapters: Sequence[Chapter], segments: Sequence[Segment], roles: Mapping[int, Role], output_dir: Path) -> list[Path]`

- [ ] **Step 1: 写失败测试**

测试假引擎产生确定性 WAV；超长旁白优先在中文标点处切块且不丢字；相同文本/音色/语速/模型版本命中缓存；任意一项变化导致未命中；旁白、对白和段落间停顿顺序正确；一章输出可被 MP3 阅读器解析、时长与拼接结果一致且文件名符合要求。

- [ ] **Step 2: 运行测试确认失败**

Run:
```powershell
uv run pytest tests/tts tests/audio -v
```
Expected: FAIL，因为 TTS 和音频模块不存在。

- [ ] **Step 3: 实现 TTS 接口、缓存和音频流水线**

Kokoro 引擎延迟导入并延迟加载模型，配置缺失时给出明确错误；缓存先写临时文件再原子替换；使用 imageio-ffmpeg 获取可随依赖安装的 FFmpeg，不依赖系统 PATH；逐段合并，避免把整本书读入内存。

- [ ] **Step 4: 运行测试**

Run:
```powershell
uv run pytest tests/tts tests/audio -v
```
Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add app/tts app/audio tests/tts tests/audio
git commit -m "feat: synthesize and export cached chapter audio"
```

---

### Task 6: 支持章节生成进度、取消、失败记录和重试

**Files:**
- Create: `app/services/generation_service.py`
- Create: `tests/services/test_generation_service.py`
- Modify: `app/storage/repository.py`
- Modify: `app/domain/models.py`

**Interfaces:**
- Consumes: `ChapterAssembler`, `ProjectRepository`
- Produces:
  - `GenerationProgress(chapter_id: int, completed_segments: int, total_segments: int, message: str)`
  - `GenerationResult(chapter_id: int, status: ChapterStatus, output_path: Path | None, error: str | None)`
  - `GenerationService.generate(chapter_ids: Sequence[int], cancel_event: threading.Event, emit: Callable[[GenerationProgress], None]) -> list[GenerationResult]`
  - `GenerationService.retry(chapter_id: int, cancel_event: threading.Event, emit: Callable[[GenerationProgress], None]) -> GenerationResult`

- [ ] **Step 1: 写失败测试**

测试多章依次生成；取消后停止后续片段但保留已完成缓存；单章异常标记 FAILED 并继续下一章；重试只处理失败章节；没有音色的角色返回可定位错误。

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/services/test_generation_service.py -v`
Expected: FAIL，因为生成服务不存在。

- [ ] **Step 3: 实现生成协调和状态持久化**

每个阶段更新章节状态；取消只在片段边界生效；失败信息记录章节和片段上下文；重试不清理其他章节缓存。

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/services/test_generation_service.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add app/services/generation_service.py app/domain/models.py app/storage/repository.py tests/services/test_generation_service.py
git commit -m "feat: add resumable chapter generation jobs"
```

---

### Task 7: 实现可操作的 PySide6 三栏桌面界面

**Files:**
- Create: `app/ui/__init__.py`
- Create: `app/ui/main_window.py`
- Create: `app/ui/project_dialog.py`
- Create: `app/ui/models.py`
- Create: `app/workers/__init__.py`
- Create: `app/workers/generation_worker.py`
- Create: `tests/ui/test_main_window.py`
- Modify: `app/__main__.py`

**Interfaces:**
- Consumes: `ProjectService`, `GenerationService`, `QMediaPlayer`
- Produces:
  - `MainWindow.open_project(root: Path) -> None`
  - `MainWindow.current_chapter_ids() -> list[int]`
  - `GenerationWorker.start_generation(chapter_ids: Sequence[int]) -> None`
  - `GenerationWorker.cancel() -> None`
  - Qt signals `progress`, `finished`, `failed`
  - 项目设置中的 `last_chapter_id: int | None` 和 `last_filter: str`

- [ ] **Step 1: 写失败 UI 测试**

使用 `QT_QPA_PLATFORM=offscreen` 和 `pytest-qt`：创建并通过服务打开示例项目；章节列表显示章节；片段表显示旁白/对白和角色；批量选择后分配角色；切换音色后模型更新；章节改名、拆分和合并后列表刷新；点击生成时后台 worker 被启动且 UI 线程未被阻塞；重开项目恢复当前章节和筛选状态。

- [ ] **Step 2: 运行 UI 测试确认失败**

Run:
```powershell
$env:QT_QPA_PLATFORM="offscreen"
uv run pytest tests/ui/test_main_window.py -v
```
Expected: FAIL，因为窗口和 worker 不存在。

- [ ] **Step 3: 实现三栏窗口和后台线程**

左侧章节、整本/所选章节生成入口及改名/拆分/合并操作，中间可多选的片段表与说话人修改，右侧角色、别名、音色、短句试听及进度；工作线程只调用服务并通过 Qt signal 回传事件。项目切换章节或筛选时自动原子保存恢复状态。使用标准 logging 将异常摘要和任务上下文写入项目 `logs/app.log`。关闭窗口时请求取消并等待线程安全退出。

- [ ] **Step 4: 运行 UI 测试**

Run:
```powershell
$env:QT_QPA_PLATFORM="offscreen"
uv run pytest tests/ui/test_main_window.py -v
```
Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add app/ui app/workers app/__main__.py tests/ui
git commit -m "feat: add audiobook project desktop interface"
```

---

### Task 8: 接入 Kokoro 模型并完成端到端人工验收

**Files:**
- Create: `scripts/check_kokoro.py`
- Create: `docs/kokoro-setup.md`
- Create: `examples/sample-novel.txt`
- Create: `tests/integration/test_end_to_end.py`
- Modify: `app/tts/kokoro_engine.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: 前七个任务的全部公开接口
- Produces: 一条使用假 TTS 的可重复端到端测试；一份真实 Kokoro 模型配置和六音色检查脚本；启动与离线验收说明

- [ ] **Step 1: 写失败端到端测试**

从示例 TXT 创建项目，检查至少两个角色和一条未分配对白；批量修正角色；给两个角色分配不同假音色；修改一个角色后断言只有相关缓存失效；生成一章并验证 MP3；重新打开项目确认角色、音色和完成状态保留。

- [ ] **Step 2: 运行端到端测试确认失败**

Run: `uv run pytest tests/integration/test_end_to_end.py -v`
Expected: FAIL，直到完整流程接通。

- [ ] **Step 3: 接通示例项目、真实引擎配置和运行说明**

文档明确 Kokoro 模型放置位置、所需两个模型文件、六个音色 ID 的确认方式以及断网启动步骤；模型缺失时应用能打开已有项目，只在实际生成时提示配置问题。

- [ ] **Step 4: 运行自动化验证**

Run:
```powershell
$env:QT_QPA_PLATFORM="offscreen"
uv run pytest -q
```
Expected: 全部 PASS，且测试期间无网络访问。

- [ ] **Step 5: 执行真实模型冒烟与人工验收**

Run: `uv run python scripts/check_kokoro.py`
Expected: 六个中文音色各生成一条短试听；断网启动应用，使用示例 TXT 完成创建、角色修正、章节生成、MP3 播放和重开恢复。

- [ ] **Step 6: 提交**

```powershell
git add scripts/check_kokoro.py docs/kokoro-setup.md examples/sample-novel.txt tests/integration/test_end_to_end.py app/tts/kokoro_engine.py README.md
git commit -m "feat: complete offline audiobook MVP workflow"
```

---

## Completion Gate

- [ ] `uv run pytest -q` 全部通过。
- [ ] 真实 Kokoro 引擎在目标机器 CPU 上生成至少六个可区分中文音色。
- [ ] 断网时能重新打开项目并生成已经配置好的章节 MP3。
- [ ] `git status --short` 为空，所有实现任务均有独立提交。
