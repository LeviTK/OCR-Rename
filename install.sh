#!/usr/bin/env bash
set -euo pipefail

REPO="${OCR_RENAME_REPO:-LeviTK/OCR-Rename}"
REF="${OCR_RENAME_REF:-main}"
INSTALL_ROOT="${OCR_RENAME_HOME:-$HOME/.local/share/ocr-rename}"
BIN_DIR="${OCR_RENAME_BIN_DIR:-}"
APP_DIR="$INSTALL_ROOT/app"
VENV_DIR="$INSTALL_ROOT/venv"
TMP_DIR=""

log() {
    printf '[ocr-rename] %s\n' "$*"
}

fail() {
    printf '[ocr-rename] %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}

trap cleanup EXIT

require_python() {
    local python_bin
    if command -v python3 >/dev/null 2>&1; then
        python_bin="python3"
    elif command -v python >/dev/null 2>&1; then
        python_bin="python"
    else
        fail "未检测到 Python，请先安装 Python 3.10+"
    fi

    if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
        fail "需要 Python 3.10+，当前版本不满足要求"
    fi
    printf '%s\n' "$python_bin"
}

choose_bin_dir() {
    if [ -n "$BIN_DIR" ]; then
        printf '%s\n' "$BIN_DIR"
        return
    fi

    case "$(uname -s)" in
        Darwin)
            if [ -d "/opt/homebrew/bin" ]; then
                printf '%s\n' "/opt/homebrew/bin"
            else
                printf '%s\n' "/usr/local/bin"
            fi
            ;;
        Linux)
            printf '%s\n' "$HOME/.local/bin"
            ;;
        *)
            fail "当前平台暂不支持 install.sh"
            ;;
    esac
}

ensure_macos_deps() {
    if [ "$(uname -s)" != "Darwin" ]; then
        return
    fi

    if ! command -v brew >/dev/null 2>&1; then
        log "未检测到 Homebrew，跳过 zbar / tesseract 自动安装"
        log "如需 OCR 兜底，请先安装 Homebrew 后执行: brew install zbar tesseract"
        return
    fi

    if [ "${OCR_RENAME_SKIP_SYSTEM_DEPS:-0}" = "1" ]; then
        log "已跳过系统依赖安装"
        return
    fi

    if ! brew list --versions zbar >/dev/null 2>&1; then
        log "安装 zbar..."
        if ! brew install zbar; then
            log "zbar 自动安装失败，请手动执行: brew install zbar"
        fi
    fi

    if ! brew list --versions tesseract >/dev/null 2>&1; then
        log "安装 tesseract..."
        if ! brew install tesseract; then
            log "tesseract 自动安装失败，请手动执行: brew install tesseract"
        fi
    fi
}

download_source() {
    local archive_url archive_path extract_root source_dir
    archive_url="https://codeload.github.com/${REPO}/tar.gz/refs/heads/${REF}"
    TMP_DIR="$(mktemp -d)"
    archive_path="$TMP_DIR/source.tar.gz"
    extract_root="$TMP_DIR/source"

    if command -v curl >/dev/null 2>&1; then
        log "下载项目源码: ${REPO}@${REF}"
        curl -fsSL "$archive_url" -o "$archive_path"
    elif command -v wget >/dev/null 2>&1; then
        log "下载项目源码: ${REPO}@${REF}"
        wget -qO "$archive_path" "$archive_url"
    else
        fail "未检测到 curl 或 wget，无法下载源码"
    fi

    mkdir -p "$extract_root"
    tar -xzf "$archive_path" -C "$extract_root"
    source_dir="$(find "$extract_root" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
    [ -n "$source_dir" ] || fail "下载完成但未找到源码目录"
    printf '%s\n' "$source_dir"
}

resolve_source_dir() {
    local source_override script_path script_dir

    source_override="${OCR_RENAME_SOURCE_DIR:-}"
    if [ -n "$source_override" ]; then
        [ -f "$source_override/pyproject.toml" ] || fail "OCR_RENAME_SOURCE_DIR 缺少 pyproject.toml: $source_override"
        printf '%s\n' "$source_override"
        return
    fi

    script_path="${BASH_SOURCE[0]:-}"
    if [ -n "$script_path" ] && [ -f "$script_path" ]; then
        script_dir="$(cd "$(dirname "$script_path")" && pwd)"
        if [ -f "$script_dir/pyproject.toml" ]; then
            printf '%s\n' "$script_dir"
            return
        fi
    fi

    download_source
}

copy_source_tree() {
    local source_dir="$1"
    rm -rf "$APP_DIR"
    mkdir -p "$APP_DIR"
    tar \
        --exclude=".git" \
        --exclude=".venv" \
        --exclude="__pycache__" \
        --exclude=".pytest_cache" \
        --exclude="build" \
        --exclude="dist" \
        -cf - -C "$source_dir" . | tar -xf - -C "$APP_DIR"
}

install_wrapper() {
    local target_bin="$1"
    local wrapper_path="$2"
    local tmp_wrapper

    mkdir -p "$(dirname "$wrapper_path")"
    tmp_wrapper="$(mktemp)"
    cat >"$tmp_wrapper" <<EOF
#!/usr/bin/env bash
exec "$target_bin" "\$@"
EOF
    chmod 755 "$tmp_wrapper"

    if [ -w "$(dirname "$wrapper_path")" ] || { [ ! -e "$wrapper_path" ] && [ -w "$(dirname "$wrapper_path")" ]; }; then
        install -m 755 "$tmp_wrapper" "$wrapper_path"
    elif command -v sudo >/dev/null 2>&1; then
        log "需要 sudo 以写入 $(dirname "$wrapper_path")"
        sudo install -m 755 "$tmp_wrapper" "$wrapper_path"
    else
        fail "没有权限写入 $(dirname "$wrapper_path")，请设置 OCR_RENAME_BIN_DIR 到可写目录"
    fi

    rm -f "$tmp_wrapper"
}

print_path_hint() {
    local install_bin_dir="$1"
    case ":$PATH:" in
        *":$install_bin_dir:"*)
            ;;
        *)
            log "当前 shell 的 PATH 尚未包含 $install_bin_dir"
            log "请把它加入 PATH，或重新打开终端后再执行 ocr-rename"
            ;;
    esac
}

main() {
    local python_bin source_dir install_bin_dir wrapper_path
    python_bin="$(require_python)"
    install_bin_dir="$(choose_bin_dir)"

    ensure_macos_deps

    log "准备安装目录: $INSTALL_ROOT"
    mkdir -p "$INSTALL_ROOT"
    source_dir="$(resolve_source_dir)"
    copy_source_tree "$source_dir"

    log "创建虚拟环境..."
    rm -rf "$VENV_DIR"
    "$python_bin" -m venv "$VENV_DIR"

    log "安装 Python 依赖..."
    "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
    "$VENV_DIR/bin/python" -m pip install -e "$APP_DIR"

    "$VENV_DIR/bin/ocr-rename" --help >/dev/null

    wrapper_path="$install_bin_dir/ocr-rename"
    install_wrapper "$VENV_DIR/bin/ocr-rename" "$wrapper_path"
    print_path_hint "$install_bin_dir"

    if ! command -v tesseract >/dev/null 2>&1; then
        log "未检测到 tesseract，条码/二维码识别仍可用，但 OCR 兜底能力受限"
    fi

    log "安装完成"
    log "现在可以直接执行: ocr-rename scan DIR"
}

main "$@"
