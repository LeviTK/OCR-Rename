# OCR Rename

当前主交付形态是：

- `Mac + Windows` 双平台离线包
- `Windows EXE` 免 Python 打包链

- 默认输入目录：`input/`
- Windows 启动脚本：`start.bat`
- macOS 启动脚本：`start.command`
- 运行本体：`src/` + `tessdata/` + 平台对应 `wheels/`

项目维护和结构说明见 [项目指南.md](/Users/linghunzhishouzhimiehun/Downloads/005-TS-R/003_HD/项目指南.md)。

工具会扫描指定目录中的图片，识别条形码/二维码里的单号，并将图片原地重命名为 `{码值}.jpg`。

## 当前功能

- 扫描一个图片目录
- 识别条形码和二维码中的纯数字单号
- 识别成功后原地重命名
- 支持 `--dry-run` 预览，不实际改名
- 保留两轮识别策略：快扫 + 深扫 + OCR 兜底

## 已删除的旧功能

- 配对命名
- 批量换号
- EXIF 方向烧录
- 递归扫描
- 扫描日志
- 移动归档

## 便携包使用

目录结构：

```text
OCR-Rename/
├── input/
├── start.bat
├── start.command
├── setup.bat
├── setup.command
├── run.bat
├── run.command
├── src/
├── tessdata/
├── wheels/
└── 其他程序文件
```

使用方式：

1. 把图片放进 `input/`
2. Windows 双击 `start.bat`
3. macOS 双击 `start.command`
4. 第一次运行会自动创建本地环境
5. 处理完成后回到 `input/` 查看结果

命令行方式：

Windows:

```bat
start.bat
```

macOS:

```bash
./start.command
```

不要在 Windows `cmd` 里写 `./start.bat`，那是 Unix shell 写法。

## 为什么不直接打包一个通用 venv

不直接这样做，原因有两个：

- `venv` 是平台相关的，Mac 和 Windows 不能共用
- `venv` 往往和创建时的绝对路径绑定，直接打包后换目录解压，容易失效

所以当前方案不是“塞一个通用 venv”，而是：

- `Windows`：带离线 `wheels/` 的自举包
- `macOS`：带离线 `wheels/` 的自举包

这样仍然是“包内自带运行依赖”，但比直接搬运一个通用 venv 更稳。

## Release 构建

执行下面的命令会生成带版本号的 `windows` 和 `macos` 两种离线包：

```bash
.venv/bin/python Release/build_portable.py
```

构建结果位于：

```text
Release/dist/OCR-Rename-windows-portable-v<version>/
Release/dist/OCR-Rename-windows-portable-v<version>.zip
Release/dist/OCR-Rename-macos-portable-v<version>/
Release/dist/OCR-Rename-macos-portable-v<version>.zip
```

## Windows EXE 构建

如果你要生成“用户机器无需安装 Python”的 Windows EXE，请在 Windows 上执行：

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

- 该包基于 `PyInstaller`，目标机器无需安装 Python
- 支持双击 `OCR-Rename.exe` 后在终端里拖入文件夹
- 也支持把文件夹直接拖到 `OCR-Rename.exe` 上运行
- 如果无参数启动，会进入交互提示模式
- 构建脚本会尝试打包本机安装的 `Tesseract`，从而避免目标机器再额外安装 OCR 依赖
- `PyInstaller` 官方不支持从 macOS 直接产出 Windows exe，所以这一步必须在 Windows 上执行
- 推送形如 `v<version>` 的 tag 后，GitHub Actions 会自动构建并发布 Windows EXE 到 GitHub Releases
- GitHub Actions 工作流文件是：
  - `.github/workflows/build-windows-exe.yml`
  - `.github/workflows/release-windows-exe.yml`
- CI 中会自动跳过 `Release\build_windows_exe.bat` 末尾的 `pause`

每个离线包包含：

- 启动脚本
- 本地安装脚本
- 运行所需源码和 `tessdata/`
- `input/`
- `USAGE.txt`
- `SCRIPT_GUIDE.txt`
- `PROJECT_GUIDE.md`
- `VERSION.txt`
- `wheels/` 离线依赖包

## 平台要求

- Windows 包：需要 `Python 3.10 x64`
- macOS 包：需要 `Python 3.10`
- macOS 离线 wheels 按构建机架构生成；如果你要给另一种 Mac 架构分发，需要在对应架构上重构一次 Release 包

这是当前离线依赖打包方案的约束。

## CLI 安装

如果你是开发者或想手动安装 CLI，仍然可以使用：

Mac / Linux:

```bash
./setup.sh
```

Windows:

```bat
setup.bat
```

或者手动安装：

```bash
python -m pip install -e .
```

## CLI 使用

扫描指定目录：

```bash
ocr-rename scan /path/to/images
```

预览模式：

```bash
ocr-rename scan /path/to/images --dry-run
```

也支持省略 `scan`，直接写目录：

```bash
ocr-rename /path/to/images
```

## CLI 命令

```bash
ocr-rename scan DIR [--dry-run]
```

| 参数 | 说明 |
|------|------|
| `DIR` | 要处理的图片目录；省略时默认 `./input` |
| `--dry-run` | 仅预览结果，不执行重命名 |

## 识别流程

1. 第一轮快扫：全图扫描 + 半图补扫
2. 第二轮深扫：二维码增强扫描
3. OCR 兜底：提取可能的数字单号
4. 命中后重命名，未命中则保持原名

## 项目结构

```text
003_HD/
├── input/
├── start.bat
├── start.command
├── setup.bat
├── setup.command
├── run.bat
├── run.command
├── install.sh
├── install.ps1
├── pyproject.toml
├── src/
│   ├── __main__.py
│   ├── pipeline.py
│   ├── barcode.py
│   ├── qrcode_scan.py
│   ├── ocr.py
│   ├── config.py
│   ├── models.py
│   └── utils.py
├── tests/
├── tessdata/
├── run.sh
├── setup.sh
└── requirements.txt
```
