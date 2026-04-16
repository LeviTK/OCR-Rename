# 票据条形码 / 二维码批量识别工具

自动识别票据照片上的条形码/二维码单号（`4920` 开头 10 位数字），支持原地重命名、票据卸货配对、批量换号，适用于物流票据图片处理场景。

## 快速开始

### 首次安装

**Mac / Linux:**
```bash
./setup.sh
```

**Windows:**
```batch
setup.bat
```

### 运行识别

将图片放入 `001-Pic/` 文件夹，然后运行：

```bash
# Mac / Linux
./run.sh scan --input ./001-Pic

# 或直接调用
DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m src scan --input ./001-Pic
```

## 命令参考

### scan — 扫描识别

```bash
# 基本用法：扫描并原地重命名（默认模式）
./run.sh scan --input /path/to/images

# 递归扫描子目录
./run.sh scan --input ./001-Pic -r

# 递归 + 跳过指定子目录
./run.sh scan --input ./001-Pic -r --skip-dirs 已处理,归档

# 设置单图超时（秒），超时自动跳过
./run.sh scan --input ./001-Pic -r --timeout 60

# 强制重扫（忽略扫描日志）
./run.sh scan --input ./001-Pic --force

# 票据 + 卸货照片配对模式
./run.sh scan --input ./001-Pic --pair

# 自定义卸货照片标记符（默认 X）
./run.sh scan --input ./001-Pic --pair --marker HD

# 移动归档模式（旧行为：成功→识别正确/，失败→未识别/）
./run.sh scan --input ./001-Pic --move

# 预览模式（不执行任何文件操作）
./run.sh scan --input ./001-Pic --dry-run
```

**scan 参数一览:**

| 参数 | 说明 |
|------|------|
| `--input DIR` | 输入图片文件夹（默认 `./001-Pic`） |
| `-r, --recursive` | 递归扫描子目录 |
| `--skip-dirs A,B` | 跳过指定子目录名（逗号分隔） |
| `--timeout N` | 单张图片处理超时秒数，超时跳过 |
| `--force` | 忽略扫描日志，强制重新扫描 |
| `--pair` | 启用票据 + 卸货照片配对命名 |
| `--marker X` | 卸货照片标记符（默认 `X`，如 `{码值}_X.jpg`） |
| `--move` | 移动归档模式（旧行为） |
| `--dry-run` | 预览模式，不执行文件操作 |

### rename — 批量换号

```bash
# CSV 批量替换单号
./run.sh rename --mapping map.csv --input /path/to/images

# 单条替换
./run.sh rename --from 4920174528 --to 5030284639 --input /path/to/images

# 预览
./run.sh rename --mapping map.csv --input /path/to/images --dry-run
```

CSV 格式：
```csv
原始单号,新单号
4920174528,5030284639
4920512130,5030399001
```

## 处理流程

```
输入图片
    │
    ▼
┌── 第一轮 · 快速扫描 ──────────────────────┐
│  ① 读取图片 + EXIF 修正                    │
│  ② 全图快扫（条形码 + 二维码，多方向旋转）  │
│  ③ 半图补扫（上半 / 下半）                  │
│  → 成功: 原地重命名为 {码值}.jpg            │
│  → 未识别: 进入第二轮                       │
└────────────────────────────────────────────┘
    │
    ▼
┌── 第二轮 · 深度扫描 ──────────────────────┐
│  ④ 二维码深扫（ROI + 颜色分离 + 多尺度）   │
│  ⑤ OCR 兜底（Tesseract 提取数字）          │
│  → 成功: 原地重命名                        │
│  → 失败: 保持原名不动                      │
└────────────────────────────────────────────┘
```

## 识别引擎

| 层级 | 引擎 | 说明 |
|------|------|------|
| 主力 | zxing-cpp | 条形码 + 二维码快速解码 |
| 补充 | OpenCV QRCodeDetector | 二维码补充解码 |
| 兜底 | pyzbar (libzbar) | 条形码 + 二维码兜底 |
| 最终兜底 | Tesseract OCR | 提取"发货单号"附近的数字 |

码值规则：只接受纯数字，优先匹配 `4920` 开头 10 位（`49\d{8}`）。条形码 + 二维码交叉验证时置信度最高。

## 配对命名格式

使用 `--pair` 模式时，按文件名排序，识别到码值的为票据，紧随其后无码值的为卸货照片：

| 类型 | 命名格式 | 示例 |
|------|---------|------|
| 票据照片 | `{码值}.jpg` | `4920174528.jpg` |
| 卸货照片（第1张） | `{码值}_{标记}.jpg` | `4920174528_X.jpg` |
| 卸货照片（第2张） | `{码值}_{标记}_2.jpg` | `4920174528_X_2.jpg` |

标记符通过 `--marker` 自定义，默认为 `X`。

## 扫描日志

工具会在输入目录下生成 `.scan_log.json`，记录每个已扫描文件的状态。再次运行时自动跳过：
- 文件名已匹配有效码值格式的（如 `4920xxxxxx.jpg`）
- 日志中记录过的文件（含失败/超时的）

使用 `--force` 忽略日志强制重扫。

## 目录结构

```
003_HD/
├── src/                 # 源码
│   ├── __main__.py      # CLI 入口（子命令路由）
│   ├── pipeline.py      # 扫描识别主流程
│   ├── barcode.py       # 条形码识别
│   ├── qrcode_scan.py   # 二维码识别
│   ├── ocr.py           # OCR 兜底
│   ├── pair.py          # 票据/卸货配对
│   ├── batch_rename.py  # 批量换号
│   ├── scan_log.py      # 扫描日志
│   ├── config.py        # 平台配置
│   ├── models.py        # 数据模型
│   └── utils.py         # 工具函数
├── tests/               # 单元测试
├── tessdata/            # Tesseract OCR 训练数据
├── doc/                 # 开发文档与历史资料
├── 001-Pic/             # 待识别图片输入目录
├── run.sh / run.bat     # 启动脚本
├── setup.sh / setup.bat # 首次安装脚本
└── requirements.txt     # Python 依赖
```

## 系统要求

- Python 3.9+
- macOS: `brew install zbar tesseract`
- Windows: 需安装 Tesseract OCR，pyzbar DLL 自动加载
