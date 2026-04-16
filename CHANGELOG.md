# Changelog

## v2.0 (2026-04-08)

### 新增功能

- **递归扫描** (`-r`): 自动发现并逐个处理子目录，支持按目录分组输出
- **目录跳过** (`--skip-dirs`): 逗号分隔指定跳过的子目录名
- **单图超时** (`--timeout`): 超过指定秒数自动跳过，不阻塞后续处理
- **扫描日志**: 自动生成 `.scan_log.json`，再次运行跳过已扫描文件和已命名文件
- **强制重扫** (`--force`): 忽略扫描日志重新处理所有文件
- **卸货标记符** (`--marker`): 配对模式下卸货照片使用可配置标记（默认 `X`），命名如 `{码值}_X.jpg`
- **CLI 子命令**: `scan` 扫描识别 + `rename` 批量换号
- **原地重命名** (默认模式): 识别成功后原地改名，失败保持原名不动
- **票据/卸货配对** (`--pair`): 按文件名排序自动配对，支持一票多卸货
- **批量换号** (`rename`): CSV 映射表 + 三层查重校验（重复原始号/重复目标号/文件冲突）
- **跨平台支持**: `run.sh`/`run.bat` + `setup.sh`/`setup.bat`，Windows 自动加载 libzbar DLL
- **OCR 自动配置**: 使用项目自带 tessdata，无需系统级配置

### 改进

- 识别引擎多层降级: zxing-cpp → OpenCV → pyzbar → Tesseract OCR
- 两轮扫描策略: 快扫（3步）筛出简单图片，深扫（5步）处理剩余
- 多线程并发处理（最多 4 worker）
- 二维码深扫: ROI 裁剪 + Lab-B 颜色分离 + 背景扣除 + 多尺度放大 + 多二值化
- stderr 抑制: fd-level dup2 屏蔽 zbar databar warning

### 项目结构

- 旧文档移入 `doc/` 目录
- 新增 `README.md` (使用指南) + `CHANGELOG.md`
- 新增 `src/scan_log.py` 扫描日志模块
- 新增 `src/pair.py` 配对逻辑
- 新增 `src/batch_rename.py` 批量换号
- 新增 `src/config.py` 平台配置

## v1.0 (2026-03-27)

### 初始版本

- 条形码识别: zxing-cpp + pyzbar 双引擎
- 二维码识别: zxing-cpp + OpenCV QRCodeDetector + pyzbar 三层解码
- OCR 兜底: Tesseract 提取"发货单号"附近数字
- 两轮扫描: 快速扫描 + 深度扫描
- 移动归档: 识别成功移入 `识别正确/`，失败移入 `未识别/`
- 码值仲裁: 条形码 + 二维码交叉验证，优先共同命中值
- 码值规则: 纯数字，优先 `4920` 开头 10 位
