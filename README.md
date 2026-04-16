# 票据条形码 / 二维码批量识别 CLI

这个项目已经打包成一个可安装的命令行工具。安装后可以直接在终端执行：

```bash
ocr-rename scan DIR
```

它会扫描指定目录中的图片，识别条形码/二维码里的单号，并将图片原地重命名为 `{码值}.jpg`。

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

## 一键安装

### macOS

```bash
curl -fsSL https://raw.githubusercontent.com/LeviTK/OCR-Rename/main/install.sh | bash
```

安装脚本会：

- 自动检查 Python 3.10+
- 在 macOS 上自动安装 `zbar` 和 `tesseract`（如果本机已安装 Homebrew）
- 创建独立运行环境
- 把 `ocr-rename` 命令安装到终端可直接调用的位置

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/LeviTK/OCR-Rename/main/install.ps1 | iex"
```

安装脚本会：

- 自动检查 Python 3.10+
- 创建独立运行环境
- 把 `ocr-rename` 命令加入当前用户 PATH

### 本地源码安装

如果你已经把仓库下载到本地，也可以继续使用项目内脚本：

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

## 使用

扫描指定目录：

```bash
ocr-rename scan /path/to/images
```

预览模式：

```bash
ocr-rename scan /path/to/images --dry-run
```

不激活虚拟环境时，也可以显式调用虚拟环境里的 CLI：

```bash
.venv/bin/ocr-rename scan /path/to/images
```

Windows:

```bat
.venv\Scripts\ocr-rename.exe scan "D:\images"
```

项目里保留了兼容脚本：

```bash
./run.sh /path/to/images
```

```bat
run.bat "D:\images"
```

## CLI 命令

```bash
ocr-rename scan DIR [--dry-run]
```

| 参数 | 说明 |
|------|------|
| `DIR` | 要处理的图片目录；省略时默认 `./001-Pic` |
| `--dry-run` | 仅预览结果，不执行重命名 |

## 识别流程

1. 第一轮快扫：全图扫描 + 半图补扫
2. 第二轮深扫：二维码增强扫描
3. OCR 兜底：提取可能的数字单号
4. 命中后重命名，未命中则保持原名

## 依赖说明

- macOS 一键安装会自动尝试安装 `zbar` 和 `tesseract`
- Windows 一键安装默认不强制安装 `tesseract`，没有它也能跑条形码/二维码识别，但 OCR 兜底能力会受限
- 如果仓库保持私有，`raw.githubusercontent.com` 的一键安装只对有权限的用户生效；要公开分发，仓库需要改成 public 或单独发布安装包

## 项目结构

```text
003_HD/
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
├── run.bat
├── setup.sh
├── setup.bat
└── requirements.txt
```
