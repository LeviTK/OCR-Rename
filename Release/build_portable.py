from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
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
MACOS_ARCH = platform.machine().lower() or "unknown"
MACOS_PLATFORM = sysconfig.get_platform().replace("-", "_").replace(".", "_")

COMMON_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "CHANGELOG.md",
    "SCRIPT_GUIDE.txt",
]

PACKAGE_FILE_RENAMES = {
    "项目指南.md": "PROJECT_GUIDE.md",
}

COMMON_DIRS = [
    "src",
    "tessdata",
]

ALLOWED_INPUT_FILES = {
    ".gitkeep",
    "PUT_IMAGES_HERE.txt",
}

COMMON_WHEEL_PREFIXES = [
    "numpy-",
    "opencv_python-",
    "packaging-",
    "pillow-",
    "pyzbar-",
    "setuptools-",
    "wheel-",
    "zxing_cpp-",
]


@dataclass(frozen=True)
class PackageSpec:
    key: str
    package_name: str
    archive_name: str
    wheel_dir: Path
    include_files: list[str]
    include_dirs: list[str]
    required_paths: list[str]
    unexpected_paths: list[str]
    python_requirement: str
    launch_command: str
    package_type: str
    download_cmd: list[str]


def python_executable() -> str:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def build_specs() -> list[PackageSpec]:
    return [
        PackageSpec(
            key="windows",
            package_name=f"OCR-Rename-windows-portable-v{VERSION}",
            archive_name=f"OCR-Rename-windows-portable-v{VERSION}.zip",
            wheel_dir=BUILD_ROOT / "wheels-windows",
            include_files=COMMON_FILES + ["start.bat", "setup.bat", "run.bat"],
            include_dirs=COMMON_DIRS,
            required_paths=[
                "start.bat",
                "setup.bat",
                "run.bat",
                "input",
                "wheels",
                "USAGE.txt",
                "SCRIPT_GUIDE.txt",
                "PROJECT_GUIDE.md",
                "VERSION.txt",
                "BUILD_MANIFEST.txt",
                "BUILD_REVIEW.txt",
            ],
            unexpected_paths=[
                "tests",
                "install.sh",
                "install.ps1",
                "start.command",
                "setup.command",
                "run.command",
                "setup.sh",
                "run.sh",
                "待处理图片",
                "开始重命名.bat",
                "launch.bat",
                ".venv",
                ".git",
            ],
            python_requirement="Python 3.10 x64",
            launch_command="start.bat",
            package_type="windows-offline-bootstrap",
            download_cmd=[
                python_executable(),
                "-m",
                "pip",
                "download",
                "--dest",
                str(BUILD_ROOT / "wheels-windows"),
                "--only-binary=:all:",
                "--platform",
                "win_amd64",
                "--implementation",
                "cp",
                "--python-version",
                "310",
                "--abi",
                "cp310",
                "pillow",
                "opencv-python",
                "numpy",
                "pyzbar",
                "zxing-cpp",
                "setuptools>=68",
                "wheel",
                "packaging",
            ],
        ),
        PackageSpec(
            key="macos",
            package_name=f"OCR-Rename-macos-portable-v{VERSION}",
            archive_name=f"OCR-Rename-macos-portable-v{VERSION}.zip",
            wheel_dir=BUILD_ROOT / "wheels-macos",
            include_files=COMMON_FILES + ["start.command", "setup.command", "run.command", "setup.sh", "run.sh"],
            include_dirs=COMMON_DIRS,
            required_paths=[
                "start.command",
                "setup.command",
                "run.command",
                "setup.sh",
                "run.sh",
                "input",
                "wheels",
                "USAGE.txt",
                "SCRIPT_GUIDE.txt",
                "PROJECT_GUIDE.md",
                "VERSION.txt",
                "BUILD_MANIFEST.txt",
                "BUILD_REVIEW.txt",
            ],
            unexpected_paths=[
                "tests",
                "install.sh",
                "install.ps1",
                "start.bat",
                "setup.bat",
                "run.bat",
                "待处理图片",
                "开始重命名.bat",
                "launch.bat",
                ".venv",
                ".git",
            ],
            python_requirement="Python 3.10",
            launch_command="./start.command",
            package_type=f"macos-{MACOS_ARCH}-offline-bootstrap",
            download_cmd=[
                python_executable(),
                "-m",
                "pip",
                "download",
                "--dest",
                str(BUILD_ROOT / "wheels-macos"),
                "--only-binary=:all:",
                "--implementation",
                "cp",
                "--python-version",
                "310",
                "--abi",
                "cp310",
                "pillow",
                "opencv-python",
                "numpy",
                "pyzbar",
                "zxing-cpp",
                "setuptools>=68",
                "wheel",
                "packaging",
            ],
        ),
    ]


def clean_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            else:
                child.rmdir()
        path.rmdir()
    path.mkdir(parents=True, exist_ok=True)


def ensure_roots() -> None:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)


def wheels_ready(path: Path) -> bool:
    if not path.is_dir():
        return False
    names = {wheel.name for wheel in path.glob("*.whl")}
    return all(any(name.startswith(prefix) for name in names) for prefix in COMMON_WHEEL_PREFIXES)


def download_wheels(spec: PackageSpec) -> None:
    if wheels_ready(spec.wheel_dir):
        return
    clean_dir(spec.wheel_dir)
    subprocess.run(spec.download_cmd, check=True, cwd=PROJECT_ROOT)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


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


def zip_member_name(package_name: str, rel: str | Path) -> str:
    rel_path = PurePosixPath(str(rel).replace("\\", "/"))
    return str(PurePosixPath(package_name) / rel_path)


def normalize_package_files(package_dir: Path, spec: PackageSpec) -> None:
    for path in package_dir.rglob("*"):
        if not path.is_file():
            continue
        if spec.key == "windows" and path.suffix in {".bat", ".txt"}:
            normalize_eol(path, "\r\n")
        elif path.suffix in {".sh", ".command"}:
            normalize_eol(path, "\n")
            os.chmod(path, 0o755)


def usage_lines(spec: PackageSpec) -> list[str]:
    lines = [
        f"OCR-Rename {spec.key} offline package",
        "",
        f"Python requirement: {spec.python_requirement}",
        "Default input folder: input/",
        f"Launch command: {spec.launch_command}",
        "",
        "Usage:",
        "1. Put the images you want to rename into input/",
        f"2. Run {spec.launch_command}",
        "3. On the first run the package will create a local .venv from bundled wheels/",
        "4. Check input/ after processing finishes.",
        "",
        "Notes:",
        "- This package includes offline Python dependencies in wheels/.",
        "- It does not ship a prebuilt universal venv because venvs are platform-specific and path-sensitive.",
        "- If Tesseract is not installed, barcode/QR scanning still works, but OCR fallback will be limited.",
    ]
    if spec.key == "windows":
        lines.append("- In cmd use start.bat directly. Do not use ./start.bat.")
        lines.append("- See SCRIPT_GUIDE.txt for the difference between start, setup, and run.")
    else:
        lines.append(f"- This macOS package was built for: {MACOS_ARCH} ({MACOS_PLATFORM}).")
        lines.append("- On macOS you may need to allow .command files in System Settings if Gatekeeper blocks them.")
    return lines


def write_release_files(package_dir: Path, spec: PackageSpec) -> None:
    built_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (package_dir / "VERSION.txt").write_text(
        "\n".join(
            [
                "project: OCR-Rename",
                f"version: {VERSION}",
                f"package_type: {spec.package_type}",
                f"built_at: {built_at}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package_dir / "USAGE.txt").write_text("\n".join(usage_lines(spec)) + "\n", encoding="utf-8")


def write_manifest(package_dir: Path) -> None:
    lines = []
    for path in sorted(package_dir.rglob("*")):
        rel = path.relative_to(package_dir)
        suffix = "/" if path.is_dir() else ""
        lines.append(f"{rel}{suffix}")
    (package_dir / "BUILD_MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_report(package_dir: Path, issues: list[str]) -> None:
    report = package_dir / "BUILD_REVIEW.txt"
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
        lines.append("- Required launcher files are present")
        lines.append("- Offline wheels are bundled")
        lines.append("- No unexpected development-only files were packaged")
        lines.append("- Zip archive was generated and spot-checked")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_zip(package_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(package_dir)
            zf.write(path, arcname=zip_member_name(package_dir.name, rel))


def review_package(spec: PackageSpec, package_dir: Path, zip_path: Path) -> list[str]:
    issues: list[str] = []

    for rel in spec.required_paths:
        if not (package_dir / rel).exists():
            issues.append(f"missing required path: {rel}")

    wheels = list((package_dir / "wheels").glob("*.whl"))
    if not wheels:
        issues.append("wheel bundle is empty")
    else:
        names = {wheel.name for wheel in wheels}
        for prefix in COMMON_WHEEL_PREFIXES:
            if not any(name.startswith(prefix) for name in names):
                issues.append(f"missing wheel: {prefix}*.whl")

    for rel in spec.unexpected_paths:
        if (package_dir / rel).exists():
            issues.append(f"unexpected packaged path: {rel}")

    input_dir = package_dir / "input"
    if input_dir.is_dir():
        for path in sorted(input_dir.iterdir()):
            if path.name not in ALLOWED_INPUT_FILES:
                issues.append(f"unexpected packaged input file: input/{path.name}")

    if not zip_path.exists():
        issues.append("zip archive missing")
    else:
        with ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            for rel in spec.required_paths:
                if rel == "input" or rel == "wheels":
                    continue
                expected = zip_member_name(package_dir.name, rel)
                if expected not in names and not any(name.startswith(f"{expected}/") for name in names):
                    issues.append(f"zip missing path: {rel}")

    return issues


def stage_package(spec: PackageSpec) -> tuple[Path, Path]:
    package_dir = DIST_ROOT / spec.package_name
    zip_path = DIST_ROOT / spec.archive_name

    clean_dir(package_dir)

    for name in spec.include_files:
        copy_file(PROJECT_ROOT / name, package_dir / name)
    for src_name, dst_name in PACKAGE_FILE_RENAMES.items():
        copy_file(PROJECT_ROOT / src_name, package_dir / dst_name)
    for name in spec.include_dirs:
        copy_dir(PROJECT_ROOT / name, package_dir / name)
    copy_input_dir(PROJECT_ROOT / "input", package_dir / "input")

    copy_dir(spec.wheel_dir, package_dir / "wheels")
    write_release_files(package_dir, spec)
    write_review_report(package_dir, [])
    write_manifest(package_dir)
    normalize_package_files(package_dir, spec)
    build_zip(package_dir, zip_path)

    issues = review_package(spec, package_dir, zip_path)
    write_review_report(package_dir, issues)
    write_manifest(package_dir)
    normalize_package_files(package_dir, spec)
    build_zip(package_dir, zip_path)

    final_issues = review_package(spec, package_dir, zip_path)
    if final_issues:
        write_review_report(package_dir, final_issues)
        write_manifest(package_dir)
        normalize_package_files(package_dir, spec)
        build_zip(package_dir, zip_path)
        raise RuntimeError("\n".join(final_issues))

    return package_dir, zip_path


def main() -> int:
    ensure_roots()
    results: list[tuple[str, Path, Path]] = []

    for spec in build_specs():
        download_wheels(spec)
        package_dir, zip_path = stage_package(spec)
        results.append((spec.key, package_dir, zip_path))

    for key, package_dir, zip_path in results:
        print(f"[build:{key}] package: {package_dir}")
        print(f"[build:{key}] zip: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
