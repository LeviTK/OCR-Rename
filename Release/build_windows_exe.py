from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import __version__

VERSION = __version__
RELEASE_ROOT = PROJECT_ROOT / "Release"
BUILD_ROOT = RELEASE_ROOT / "build"
DIST_ROOT = RELEASE_ROOT / "dist"
ENTRY_SCRIPT = RELEASE_ROOT / "exe_entry.py"
APP_NAME = "OCR-Rename"
PACKAGE_NAME = f"OCR-Rename-windows-exe-v{VERSION}"
PYI_DIST_ROOT = BUILD_ROOT / "pyinstaller-windows-dist"
PYI_WORK_ROOT = BUILD_ROOT / "pyinstaller-windows-work"
PYI_SPEC_ROOT = BUILD_ROOT / "pyinstaller-windows-spec"
PACKAGE_DIR = DIST_ROOT / PACKAGE_NAME
ZIP_PATH = DIST_ROOT / f"{PACKAGE_NAME}.zip"

STATIC_FILES = [
    "README.md",
    "CHANGELOG.md",
    "SCRIPT_GUIDE.txt",
]

PACKAGE_FILE_RENAMES = {
    "项目指南.md": "PROJECT_GUIDE.md",
}

PACKAGE_DIRS = [
    "input",
]

REQUIRED_PATHS = [
    "OCR-Rename.exe",
    "_internal/tessdata",
    "tesseract/tesseract.exe",
    "input",
    "README.md",
    "CHANGELOG.md",
    "SCRIPT_GUIDE.txt",
    "PROJECT_GUIDE.md",
    "USAGE.txt",
    "VERSION.txt",
    "BUILD_MANIFEST.txt",
    "BUILD_REVIEW.txt",
]

UNEXPECTED_PATHS = [
    "tests",
    ".venv",
    ".git",
    "待处理图片",
    "开始重命名.bat",
    "launch.bat",
]

ALLOWED_INPUT_FILES = {
    ".gitkeep",
    "PUT_IMAGES_HERE.txt",
}


def clean_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            else:
                child.rmdir()
        path.rmdir()
    path.mkdir(parents=True, exist_ok=True)


def copy_dir(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", "*.pyo"),
    )


def copy_input_dir(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for name in sorted(ALLOWED_INPUT_FILES):
        candidate = src / name
        if candidate.is_file():
            shutil.copy2(candidate, dst / name)


def normalize_eol(path: Path, newline: str) -> None:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    path.write_text(normalized, encoding="utf-8", newline="")


def normalize_package_files(package_dir: Path) -> None:
    for path in package_dir.rglob("*"):
        if path.is_file() and path.suffix == ".txt":
            normalize_eol(path, "\r\n")


def zip_member_name(package_name: str, rel: str | Path) -> str:
    rel_path = PurePosixPath(str(rel).replace("\\", "/"))
    return str(PurePosixPath(package_name) / rel_path)


def find_tesseract_dir() -> Path:
    candidates: list[Path] = []
    env_dir = os.environ.get("OCR_RENAME_TESSERACT_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend(
        [
            Path(r"C:\Program Files\Tesseract-OCR"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR"),
        ]
    )
    for candidate in candidates:
        if (candidate / "tesseract.exe").is_file():
            return candidate
    raise RuntimeError(
        "Tesseract runtime was not found. Install Tesseract or set OCR_RENAME_TESSERACT_DIR."
    )


def run_pyinstaller() -> Path:
    clean_dir(PYI_DIST_ROOT)
    clean_dir(PYI_WORK_ROOT)
    clean_dir(PYI_SPEC_ROOT)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--console",
        "--name",
        APP_NAME,
        "--distpath",
        str(PYI_DIST_ROOT),
        "--workpath",
        str(PYI_WORK_ROOT),
        "--specpath",
        str(PYI_SPEC_ROOT),
        "--paths",
        str(PROJECT_ROOT),
        "--collect-binaries",
        "pyzbar",
        "--collect-data",
        "pyzbar",
        "--collect-binaries",
        "zxingcpp",
        "--collect-binaries",
        "cv2",
        "--hidden-import",
        "pyzbar.pyzbar",
        "--hidden-import",
        "zxingcpp",
        "--add-data",
        f"{PROJECT_ROOT / 'tessdata'};tessdata",
        str(ENTRY_SCRIPT),
    ]
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    app_dir = PYI_DIST_ROOT / APP_NAME
    if not app_dir.is_dir():
        raise RuntimeError(f"PyInstaller output is missing: {app_dir}")
    return app_dir


def copy_tesseract_runtime(src_dir: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for child in sorted(src_dir.iterdir()):
        if child.name.lower() == "tessdata":
            continue
        target = dst_dir / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def usage_lines() -> list[str]:
    return [
        "OCR-Rename Windows EXE package",
        "",
        "Usage:",
        "1. Drag a folder directly onto OCR-Rename.exe.",
        "2. Or double-click OCR-Rename.exe with no arguments, then enter a folder path interactively.",
        "3. Press Enter on an empty prompt to use the bundled input/ folder.",
        "4. The app renames images in place.",
        "",
        "Notes:",
        "- This package bundles Python runtime dependencies.",
        "- This package bundles Tesseract runtime files under tesseract/.",
        "- No Python installation is required on the target Windows machine.",
        "- See SCRIPT_GUIDE.txt for the difference between EXE mode and the source-package scripts.",
        "- Set OCR_RENAME_NO_PAUSE=1 if you do not want the console window to wait before closing.",
    ]


def write_release_files(package_dir: Path) -> None:
    built_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (package_dir / "VERSION.txt").write_text(
        "\n".join(
            [
                "project: OCR-Rename",
                f"version: {VERSION}",
                "package_type: windows-pyinstaller-exe",
                f"built_at: {built_at}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package_dir / "USAGE.txt").write_text("\n".join(usage_lines()) + "\n", encoding="utf-8")


def write_manifest(package_dir: Path) -> None:
    lines = []
    for path in sorted(package_dir.rglob("*")):
        rel = path.relative_to(package_dir)
        suffix = "/" if path.is_dir() else ""
        lines.append(f"{rel}{suffix}")
    (package_dir / "BUILD_MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_report(package_dir: Path, issues: list[str]) -> None:
    lines = [
        f"version: {VERSION}",
        f"reviewed_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    if issues:
        lines.append("result: failed")
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("result: passed")
        lines.append("- EXE launcher is present")
        lines.append("- Bundled tesseract runtime is present")
        lines.append("- Input folder and release guides are present")
        lines.append("- Zip archive was generated and spot-checked")
    (package_dir / "BUILD_REVIEW.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_zip(package_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(package_dir)
            zf.write(path, arcname=zip_member_name(package_dir.name, rel))


def review_package(package_dir: Path, zip_path: Path) -> list[str]:
    issues: list[str] = []

    for rel in REQUIRED_PATHS:
        if not (package_dir / rel).exists():
            issues.append(f"missing required path: {rel}")

    for rel in UNEXPECTED_PATHS:
        if (package_dir / rel).exists():
            issues.append(f"unexpected packaged path: {rel}")

    input_dir = package_dir / "input"
    if input_dir.is_dir():
        for path in sorted(input_dir.iterdir()):
            if path.name not in ALLOWED_INPUT_FILES:
                issues.append(f"unexpected packaged input file: input/{path.name}")

    if not zip_path.exists():
        issues.append("zip archive missing")
        return issues

    with ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        for rel in REQUIRED_PATHS:
            expected = zip_member_name(package_dir.name, rel)
            if expected not in names and not any(name.startswith(f"{expected}/") for name in names):
                issues.append(f"zip missing path: {rel}")

    return issues


def stage_package(app_dir: Path, tesseract_dir: Path) -> None:
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    clean_dir(PACKAGE_DIR)

    shutil.copytree(app_dir, PACKAGE_DIR, dirs_exist_ok=True)
    copy_tesseract_runtime(tesseract_dir, PACKAGE_DIR / "tesseract")

    for name in STATIC_FILES:
        shutil.copy2(PROJECT_ROOT / name, PACKAGE_DIR / name)
    for src_name, dst_name in PACKAGE_FILE_RENAMES.items():
        shutil.copy2(PROJECT_ROOT / src_name, PACKAGE_DIR / dst_name)
    for name in PACKAGE_DIRS:
        if name == "input":
            copy_input_dir(PROJECT_ROOT / name, PACKAGE_DIR / name)
        else:
            copy_dir(PROJECT_ROOT / name, PACKAGE_DIR / name)

    write_release_files(PACKAGE_DIR)
    write_review_report(PACKAGE_DIR, [])
    write_manifest(PACKAGE_DIR)
    normalize_package_files(PACKAGE_DIR)
    build_zip(PACKAGE_DIR, ZIP_PATH)

    issues = review_package(PACKAGE_DIR, ZIP_PATH)
    write_review_report(PACKAGE_DIR, issues)
    write_manifest(PACKAGE_DIR)
    normalize_package_files(PACKAGE_DIR)
    build_zip(PACKAGE_DIR, ZIP_PATH)

    final_issues = review_package(PACKAGE_DIR, ZIP_PATH)
    if final_issues:
        write_review_report(PACKAGE_DIR, final_issues)
        write_manifest(PACKAGE_DIR)
        normalize_package_files(PACKAGE_DIR)
        build_zip(PACKAGE_DIR, ZIP_PATH)
        raise RuntimeError("\n".join(final_issues))


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit(
            "PyInstaller cannot produce a Windows exe from macOS/Linux. Run this builder on Windows or use GitHub Actions."
        )

    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit("PyInstaller is missing. Run: py -3.10 -m pip install -e .[build]") from exc

    tesseract_dir = find_tesseract_dir()
    app_dir = run_pyinstaller()
    stage_package(app_dir, tesseract_dir)

    print(f"[build:windows-exe] package: {PACKAGE_DIR}")
    print(f"[build:windows-exe] zip: {ZIP_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
