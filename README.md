# 票据条形码 / 二维码批量识别工具

这个版本只保留一个核心功能：扫描单个目录中的票据图片，识别条形码/二维码里的单号，并将图片原地重命名为 `{码值}.jpg`。

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

## 快速开始

### 安装

Mac / Linux:

```bash
./setup.sh
```

Windows:

```bat
setup.bat
```

### 运行

默认处理项目内的 `001-Pic/`:

```bash
./run.sh
```

或者显式指定图片目录：

```bash
./run.sh /path/to/images
```

直接调用 Python:

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m src --input /path/to/images
```

预览模式：

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m src --input /path/to/images --dry-run
```

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--input DIR` | 输入图片目录，默认 `./001-Pic` |
| `--dry-run` | 仅预览结果，不执行重命名 |

## 识别流程

1. 第一轮快扫：全图扫描 + 半图补扫
2. 第二轮深扫：二维码增强扫描
3. OCR 兜底：提取可能的数字单号
4. 命中后重命名，未命中则保持原名

## 项目结构

```text
003_HD/
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
