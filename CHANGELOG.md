# Changelog

## v3.6.2 (2026-04-17)

- 修复 `Release/build_windows_exe.py` 对 PyInstaller onedir 目录布局的错误校验，改为检查 `_internal/tessdata`
- 修复 Windows 下 zip 审查路径分隔符不一致导致所有文件被误判为缺失的问题

## v3.6.1 (2026-04-17)

- 修复 `release-windows-exe.yml` 的 GitHub Actions 运行问题：升级到 `actions/checkout@v5`、`actions/setup-python@v6`
- 修复 `Release/build_windows_exe.bat` 在 CI 环境中执行时可能被 `pause` 卡住或返回非零退出码的问题
- 修复 `release-windows-exe.yml` 在 `workflow_dispatch` 下仍错误执行 tag 校验的问题

## v3.6.0 (2026-04-17)

- 明确支持 Windows `exe` 两种启动方式：直接拖拽文件夹到 `OCR-Rename.exe`，或无参数启动后进入交互提示模式
- 补强 `Release/build_windows_exe.py`，让 `exe` 包产出 `input/`、`SCRIPT_GUIDE.txt`、`PROJECT_GUIDE.md`、`BUILD_MANIFEST.txt`、`BUILD_REVIEW.txt`
- 补强 GitHub Actions 的 Windows `exe` 构建与发布链路，使其更适合通过 GitHub Releases 对外分发
- 将 GitHub Actions 升级到 `actions/checkout@v5`、`actions/setup-python@v6`，并让 `build_windows_exe.bat` 在 CI 中跳过 `pause`

## v3.5.0 (2026-04-17)

- 统一改为 ASCII 入口脚本：`start.bat`、`start.command`、`setup.command`、`run.command`
- 默认输入目录改为 `input/`，同时保留对 `待处理图片/` 和 `001-Pic/` 的兼容回退
- Release 构建升级为 `Windows + macOS` 双平台离线包，并补充“为什么不直接打包通用 venv”的说明
- 便携版启动脚本改为优先使用 `.venv` 内的 `python -m src`，降低平台包装脚本失效风险

## v3.4.1 (2026-04-17)

- 新增 `launch.bat` 作为纯 ASCII 的 Windows 启动入口
- 文档和 Release 使用说明补充 `cmd` 下应直接执行 `launch.bat` 或 `开始重命名.bat`
- 避免用户在 `cmd` 中误用 `./开始重命名.bat`

## v3.4 (2026-04-17)

- 新增 `项目指南.md`，整理当前代码结构、运行边界和冗余分析
- 新增 `Release/` 构建链路，生成带版本号的 Windows 便携版目录和 zip 压缩包
- 便携版构建加入离线 `wheels/`，`setup.bat` 可优先使用本地依赖安装
- 便携版产物自动写入 `版本.txt`、`使用说明.txt` 和构建审查报告

## v3.3 (2026-04-17)

- 将 Windows 便携版调整为主方案，新增 `待处理图片/` 和 `开始重命名.bat`
- 默认输入目录改为 `待处理图片/`，保留对旧 `001-Pic/` 的兼容回退
- `开始重命名.bat` 支持首次运行自动调用本地安装，再执行重命名

## v3.2 (2026-04-16)

- 新增 `install.sh` 和 `install.ps1`，支持 GitHub 一键安装 CLI
- README 补充远程安装命令，安装后可直接执行 `ocr-rename scan DIR`
- 保留 `setup.sh` / `setup.bat` 作为本地源码安装入口

## v3.1 (2026-04-16)

- 将项目打包为可安装 CLI，新增 `pyproject.toml`
- 提供终端命令 `ocr-rename scan DIR`
- 更新 Mac / Windows 安装脚本，安装后直接生成 CLI 命令
- 保留 `run.sh` / `run.bat` 作为兼容包装器

## v3.0 (2026-04-16)

- 将项目收缩为单一主功能：扫描单个目录并原地重命名票据图片
- 删除配对命名、批量换号、方向烧录、递归扫描、扫描日志、移动归档等附加功能
- 删除对应模块、测试和历史文档，保留核心识别链路
- 简化 CLI，仅保留 `--input` 和 `--dry-run`

## v2.0 (2026-04-08)

- 引入多轮扫描、配对命名、批量换号和扫描日志

## v1.0 (2026-03-27)

- 初始版二维码/条形码识别与归档流程
