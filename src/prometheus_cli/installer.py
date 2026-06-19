from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path

import httpx

DEFAULT_REPO = "FeverDream-dev/Prometheus"
DEFAULT_INSTALL_ROOT = Path.home() / ".local" / "share" / "prometheus"
DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
USER_DATA_HOME = Path(os.environ.get("PROMETHEUS_HOME", Path.home() / ".prometheus"))


def install_root() -> Path:
    return Path(os.environ.get("PROMETHEUS_INSTALL_ROOT", DEFAULT_INSTALL_ROOT))


def bin_dir() -> Path:
    return Path(os.environ.get("PROMETHEUS_BIN", DEFAULT_BIN_DIR))


def versions_dir() -> Path:
    return install_root() / "versions"


def wrapper_path() -> Path:
    return bin_dir() / "prometheus"


def user_data_home() -> Path:
    return USER_DATA_HOME


def current_version() -> str | None:
    link = versions_dir() / "current"
    target = link.resolve() if link.is_symlink() or link.exists() else None
    if target and target.is_dir():
        return target.name
    return None


def installed_versions() -> list[str]:
    base = versions_dir()
    if not base.is_dir():
        return []
    out: list[str] = []
    for child in sorted(base.iterdir()):
        if child.name == "current" or child.is_symlink():
            continue
        if child.is_dir() and (child / "venv").is_dir():
            out.append(child.name)
    return out


@dataclass
class VersionInfo:
    version: str
    is_release: bool
    source: str

    def __str__(self) -> str:
        return f"{self.version} ({self.source})"


def _looks_like_release(version: str) -> bool:
    return version not in ("main", "master")


def resolve_latest_version(
    repo: str = DEFAULT_REPO,
    client: httpx.Client | None = None,
) -> VersionInfo:
    own_client = client is None
    cl = client or httpx.Client(timeout=10.0, headers={"Accept": "application/vnd.github+json"})
    try:
        try:
            resp = cl.get(f"https://api.github.com/repos/{repo}/releases/latest")
            if resp.status_code == 200:
                tag = resp.json().get("tag_name", "")
                if tag:
                    return VersionInfo(tag, True, "github-releases-api")
        except httpx.HTTPError:
            pass
        tag = _git_latest_tag(repo)
        if tag:
            return VersionInfo(tag, True, "git-ls-remote")
    finally:
        if own_client:
            cl.close()
    return VersionInfo("main", False, "fallback")


def _git_latest_tag(repo: str) -> str | None:
    exe = shutil.which("git")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "ls-remote", "--tags", "--refs", f"https://github.com/{repo}.git", "refs/tags/v*"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    tags = [line.split("/")[-1] for line in out.stdout.splitlines() if line.strip()]
    if not tags:
        return None
    tags.sort(key=_version_key)
    return tags[-1]


def _version_key(v: str) -> tuple:
    parts = v.lstrip("v").split(".")
    key: list = []
    for p in parts:
        try:
            key.append((0, int(p)))
        except ValueError:
            key.append((1, p))
    return tuple(key)


def tarball_url(version: str, repo: str = DEFAULT_REPO) -> str:
    if version in ("main", "master"):
        return f"https://github.com/{repo}/archive/refs/heads/{version}.tar.gz"
    return f"https://github.com/{repo}/archive/refs/tags/{version}.tar.gz"


def sha256_url(version: str, repo: str = DEFAULT_REPO) -> str:
    return tarball_url(version, repo) + ".sha256"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_archive_dirname(version: str, repo: str = DEFAULT_REPO) -> str:
    name = repo.split("/")[-1]
    if version in ("main", "master"):
        return f"{name}-{version}"
    return f"{name}-{version.lstrip('v')}"


def _find_python() -> str:
    for cand in (sys.executable, "python3", "python3.11", "python3.12"):
        exe = shutil.which(cand) if cand != sys.executable else cand
        if not exe:
            continue
        ok = subprocess.run(
            [exe, "-c", "import sys; sys.exit(0 if sys.version_info[:2]>=(3,11) else 1)"],
            check=False,
        )
        if ok.returncode == 0:
            return exe
    raise RuntimeError("Python 3.11+ not available for venv creation.")


def _run(cmd: list[str], cwd: Path | None = None, runner=None) -> subprocess.CompletedProcess:
    run = runner or subprocess.run
    return run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)


@dataclass
class InstallResult:
    version: str
    install_dir: Path
    venv_dir: Path
    wrapper: Path
    verified: bool


def install_version(
    version: str | None = None,
    repo: str = DEFAULT_REPO,
    install_tui: bool = True,
    client: httpx.Client | None = None,
    runner=None,
    python_bin: str | None = None,
) -> InstallResult:
    if version is None:
        version = resolve_latest_version(repo, client).version
    is_release = _looks_like_release(version)
    install_dir = versions_dir() / version
    venv_dir = install_dir / "venv"
    install_dir.mkdir(parents=True, exist_ok=True)
    archive = install_dir / "source.tar.gz"

    own_client = client is None
    cl = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        url = tarball_url(version, repo)
        with cl.stream("GET", url) as r:
            r.raise_for_status()
            with archive.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
    finally:
        if own_client:
            cl.close()

    verified = _verify_or_fail(archive, version, is_release, repo, client)
    _extract(archive, install_dir, version, repo)
    src_dir = _locate_source(install_dir, version, repo)

    py = python_bin or _find_python()
    _run([py, "-m", "venv", str(venv_dir)], runner=runner)
    venv_py = str(venv_dir / "bin" / "python")
    _run([venv_py, "-m", "pip", "install", "--upgrade", "pip", "--quiet"], runner=runner)
    spec = f"{src_dir}[tui]" if install_tui else str(src_dir)
    _run([venv_py, "-m", "pip", "install", spec, "--quiet"], runner=runner)

    write_wrapper(venv_dir, version)
    _point_current(install_dir)
    archive.unlink(missing_ok=True)
    return InstallResult(version, install_dir, venv_dir, wrapper_path(), verified)


def _verify_or_fail(
    archive: Path, version: str, is_release: bool, repo: str, client: httpx.Client | None
) -> bool:
    actual = compute_sha256(archive).lower()
    expected = _fetch_expected_sha(version, repo, client)
    if expected:
        if actual != expected:
            archive.unlink(missing_ok=True)
            raise ChecksumMismatchError(version, expected, actual)
        return True
    if is_release:
        archive.unlink(missing_ok=True)
        raise MissingChecksumError(version)
    return False


def _fetch_expected_sha(version: str, repo: str, client: httpx.Client | None) -> str | None:
    own = client is None
    cl = client or httpx.Client(timeout=10.0, follow_redirects=True)
    try:
        try:
            resp = cl.get(sha256_url(version, repo))
            if resp.status_code == 200 and resp.text.strip():
                return resp.text.strip().split()[0].lower()
        except httpx.HTTPError:
            return None
    finally:
        if own:
            cl.close()
    return None


def _extract(archive: Path, dest: Path, version: str, repo: str) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(dest)


def _locate_source(dest: Path, version: str, repo: str) -> Path:
    primary = dest / expected_archive_dirname(version, repo)
    if primary.is_dir():
        return primary
    for child in dest.iterdir():
        if child.is_dir() and (child / "pyproject.toml").exists():
            return child
    raise RuntimeError(f"no source directory found in {dest}")


def write_wrapper(venv_dir: Path, version: str) -> None:
    wp = wrapper_path()
    wp.parent.mkdir(parents=True, exist_ok=True)
    target = venv_dir / "bin" / "prometheus"
    tmp = wp.with_suffix(".prometheus.tmp")
    tmp.write_text(
        "#!/usr/bin/env sh\n"
        f"# PROMETHEUS launcher (auto-generated). Version: {version}\n"
        f'exec "{target}" "$@"\n',
        encoding="utf-8",
    )
    tmp.chmod(0o755)
    tmp.replace(wp)


def _point_current(install_dir: Path) -> None:
    link = versions_dir() / "current"
    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(install_dir)
    except OSError:
        pass


@dataclass
class UninstallResult:
    removed_versions: list[str]
    removed_wrapper: bool
    removed_user_data: bool


def uninstall(
    version: str | None = None,
    purge: bool = False,
    runner=None,
) -> UninstallResult:
    removed_versions: list[str] = []
    base = versions_dir()
    if version:
        target = base / version
        if target.is_dir():
            shutil.rmtree(target)
            removed_versions.append(version)
    elif base.is_dir():
        for child in list(base.iterdir()):
            if child.is_dir() and (child / "venv").is_dir():
                shutil.rmtree(child)
                removed_versions.append(child.name)
        if base.exists():
            shutil.rmtree(base)

    wp = wrapper_path()
    removed_wrapper = False
    if wp.exists() or wp.is_symlink():
        wp.unlink()
        removed_wrapper = True

    root = install_root()
    if root.exists() and (root / "versions") == base and not (versions_dir()).exists():
        try:
            shutil.rmtree(root)
        except OSError:
            pass

    removed_user_data = False
    if purge:
        data = user_data_home()
        if data.exists():
            shutil.rmtree(data)
            removed_user_data = True

    return UninstallResult(removed_versions, removed_wrapper, removed_user_data)


def path_needs_bindir() -> bool:
    bd = str(bin_dir())
    return f":{bd}:" not in f":{os.environ.get('PATH', '')}:"


class ChecksumMismatchError(RuntimeError):
    def __init__(self, version: str, expected: str, actual: str) -> None:
        super().__init__(
            f"checksum mismatch for {version}: expected {expected}, got {actual}"
        )


class MissingChecksumError(RuntimeError):
    def __init__(self, version: str) -> None:
        super().__init__(
            f"release {version} has no published checksum; refusing to install unverified release"
        )


__all__ = [
    "DEFAULT_REPO",
    "InstallResult",
    "UninstallResult",
    "VersionInfo",
    "ChecksumMismatchError",
    "MissingChecksumError",
    "bin_dir",
    "compute_sha256",
    "current_version",
    "expected_archive_dirname",
    "install_root",
    "install_version",
    "installed_versions",
    "path_needs_bindir",
    "resolve_latest_version",
    "sha256_url",
    "tarball_url",
    "uninstall",
    "user_data_home",
    "versions_dir",
    "wrapper_path",
    "write_wrapper",
]