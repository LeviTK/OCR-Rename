# Release 构建说明

这个目录用于生成：

- `Windows + macOS` 两种离线包
- `Windows EXE` 免 Python 包

另外也支持生成 `Windows EXE` 免 Python 包。

## 构建命令

```bash
.venv/bin/python Release/build_portable.py
```

## 输出位置

```text
Release/dist/OCR-Rename-windows-portable-v<version>/
Release/dist/OCR-Rename-windows-portable-v<version>.zip
Release/dist/OCR-Rename-macos-portable-v<version>/
Release/dist/OCR-Rename-macos-portable-v<version>.zip
Release/dist/OCR-Rename-windows-exe-v<version>/
Release/dist/OCR-Rename-windows-exe-v<version>.zip
```

## Windows EXE 构建

这条链路用于生成目标机器无需安装 Python 的 Windows 可执行包。

在 Windows 上执行：

```bat
py -3.10 -m pip install -e .[build]
Release\build_windows_exe.bat
```

输出位置：

```text
Release/dist/OCR-Rename-windows-exe-v<version>/
Release/dist/OCR-Rename-windows-exe-v<version>.zip
```

说明：

- 入口程序是 `OCR-Rename.exe`
- 支持“拖文件夹到 exe 上”直接处理
- 没有参数时会进入交互提示模式
- 构建脚本会尝试从本机 `Tesseract-OCR` 安装目录或 `OCR_RENAME_TESSERACT_DIR` 打包 OCR 运行时
- `PyInstaller` 不是跨平台编译器，Windows EXE 必须在 Windows 上构建
- 推送 `v*` tag 时，可由 `.github/workflows/release-windows-exe.yml` 自动构建并上传到 GitHub Release

## 构建内容

- `start.bat`
- `start.command`
- `setup.bat`
- `setup.command`
- `run.bat`
- `run.command`
- `src/`
- `tessdata/`
- `input/`
- `wheels/`
- `USAGE.txt`
- `SCRIPT_GUIDE.txt`
- `PROJECT_GUIDE.md`
- `VERSION.txt`
- `BUILD_MANIFEST.txt`
- `BUILD_REVIEW.txt`

## Windows EXE 构建

本地 Windows 构建：

```bat
py -3.10 -m pip install -e .[build]
Release\build_windows_exe.bat
```

GitHub 构建：

- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/release-windows-exe.yml`

`exe` 包支持：

- 将文件夹直接拖到 `OCR-Rename.exe` 上
- 无参数启动后，进入交互提示模式

## 审查规则

构建脚本会自动检查：

- 关键启动文件是否存在
- `wheels/` 是否存在且不为空
- 包中是否误带 `tests/`、`install.sh`、`install.ps1`
- zip 包内是否包含必须文件
- macOS wheels 是否与构建机架构匹配
