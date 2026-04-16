# mac M1 票据条形码 / 二维码识别方案

## 1. 安装系统依赖

```bash
brew install python zbar tesseract
```

> `pyzbar` 依赖 `zbar`；OCR 兜底依赖 `tesseract`。

## 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pillow opencv-python numpy pyzbar
pip install zxing-cpp  # 可选，但强烈建议，用于困难二维码
```

如果你需要中文 OCR 兜底：

```bash
brew install tesseract-lang
```

## 3. 目录结构建议

```text
003_HD/
  src/
  001-Pic/
    IMG_001.jpg
    IMG_002.jpg
  识别正确/
  未识别/
```

## 4. 先 dry-run

```bash
cd /path/to/003_HD
DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m src --dry-run
```

## 5. 正式执行

```bash
cd /path/to/003_HD
DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m src
```

## 6. 输出说明

- 当前实现按两轮执行：
- 第一轮：快速扫描，只尝试较少方向与较快预处理
- 第二轮：仅针对第一轮未命中的图片做深度扫描
- 结果只接受纯数字值
- 如果条形码与二维码都识别到相同数字，优先采用该共同值
- 如果只识别到单侧数字，则采用分数最高的数字值
- 如果两轮后都没有有效数字，则落到 `未识别`
- 如果图片本身无法打开，也会落到 `未识别`

## 7. 方案特点

- 自动尝试 0/90/180/270 四个方向
- 条形码与二维码都会参与最终值仲裁，不再采用“条码命中后直接跳过二维码”的流程
- 条形码优先扫描整图；二维码优先扫描整图、右上、左上等 ROI
- 针对粉纸蓝墨做蓝色通道分离、背景扣除、CLAHE、多阈值、多尺度增强
- 业务前提明确为“条码与二维码值一致，且均为数字”，因此每张图只输出一个最终数字值
- 可处理“只成功识别条码”或“只成功识别二维码”的图片
- 可处理“完全没有码”的图片
