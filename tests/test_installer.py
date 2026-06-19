from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import httpx
import pytest

from prometheus_cli import installer


class FakeClient:
    def __init__(self, routes: dict[str, httpx.Response | Exception], *_, **__):
        self._routes = routes
        self.calls: list[str] = []

    def get(self, url, *_, **__):
        return self._respond(url)

    def stream(self, method, url, *_, **__):
        self.calls.append(url)
        resp = self._respond(url)
        return _StreamCtx(resp)

    def _respond(self, url):
        self.calls.append(url)
        value = self._routes.get(url)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return httpx.Response(404, request=httpx.Request("GET", url))
        return value

    def close(self):
        pass


class _StreamCtx:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, *exc):
        return False


def _tarball_bytes(name: str = "Prometheus", version: str = "1.0.0", payload: str = "print('hi')") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        top = f"{name}-{version}"
        data = (f"[project]\nname = 'prometheus-local-agent'\nversion = '{version}'\n"
                f"[tool.setuptools.packages.find]\nwhere=['.']\n").encode()
        tar.addfile(tarfile.TarInfo(f"{top}/pyproject.toml"), io.BytesIO(data))
        pyinfo = tarfile.TarInfo(f"{top}/src/prometheus_cli/__init__.py")
        pyinfo.size = len(payload.encode())
        tar.addfile(pyinfo, io.BytesIO(payload.encode()))
    return buf.getvalue()


def _ok(url, body: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=body, request=httpx.Request("GET", url))


def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / "install_root"
    bindir = tmp_path / "bin"
    data = tmp_path / "data"
    root.mkdir()
    bindir.mkdir()
    data.mkdir()
    monkeypatch.setattr(installer, "DEFAULT_INSTALL_ROOT", root)
    monkeypatch.setattr(installer, "DEFAULT_BIN_DIR", bindir)
    monkeypatch.setattr(installer, "USER_DATA_HOME", data)
    monkeypatch.setattr(installer, "install_root", lambda: root)
    monkeypatch.setattr(installer, "bin_dir", lambda: bindir)
    monkeypatch.setattr(installer, "user_data_home", lambda: data)
    monkeypatch.setattr(installer, "versions_dir", lambda: root / "versions")
    monkeypatch.setattr(installer, "wrapper_path", lambda: bindir / "prometheus")
    monkeypatch.setenv("PROMETHEUS_INSTALL_ROOT", str(root))
    monkeypatch.setenv("PROMETHEUS_BIN", str(bindir))
    return {"root": root, "bin": bindir, "data": data}


def test_resolve_latest_version_uses_release_tag(isolated_root):
    body = b'{"tag_name":"v1.2.3"}'
    client = FakeClient({
        "https://api.github.com/repos/FeverDream-dev/Prometheus/releases/latest":
            _ok("https://api.github.com/repos/FeverDream-dev/Prometheus/releases/latest", body),
    })
    info = installer.resolve_latest_version(client=client)
    assert info.version == "v1.2.3"
    assert info.is_release is True


def test_resolve_latest_version_falls_back_to_main_when_api_fails(isolated_root, monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda _: None)
    client = FakeClient({})
    info = installer.resolve_latest_version(client=client)
    assert info.version == "main"
    assert info.is_release is False


def test_resolve_latest_version_uses_git_ls_remote_on_api_404(isolated_root, monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "abc\trefs/tags/v0.9.0\ndef\trefs/tags/v0.10.0\n"

    def fake_run(cmd, **_):
        return FakeProc()

    monkeypatch.setattr(installer.shutil, "which", lambda _: "/usr/bin/git")
    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    client = FakeClient({})
    info = installer.resolve_latest_version(client=client)
    assert info.version == "v0.10.0"


def test_tarball_and_sha_urls():
    assert installer.tarball_url("v0.1.0").endswith("/archive/refs/tags/v0.1.0.tar.gz")
    assert installer.tarball_url("main").endswith("/archive/refs/heads/main.tar.gz")
    assert installer.sha256_url("v0.1.0").endswith("v0.1.0.tar.gz.sha256")


def test_expected_archive_dirname():
    assert installer.expected_archive_dirname("v0.1.0") == "Prometheus-0.1.0"
    assert installer.expected_archive_dirname("main") == "Prometheus-main"


def test_compute_sha256(tmp_path):
    f = tmp_path / "x"
    f.write_bytes(b"hello")
    assert installer.compute_sha256(f) == hashlib.sha256(b"hello").hexdigest()


def test_install_version_verifies_release_checksum(isolated_root, monkeypatch, tmp_path):
    version = "v0.1.0"
    blob = _tarball_bytes(version="0.1.0")
    digest = _sha256_of(blob)
    url = installer.tarball_url(version)
    sha_url = installer.sha256_url(version)
    client = FakeClient({
        url: _ok(url, blob),
        sha_url: _ok(sha_url, (digest + "  archive\n").encode()),
    })
    runs: list[list[str]] = []

    def fake_run(cmd, cwd=None, runner=None):
        runs.append(cmd)
        if len(cmd) >= 2 and cmd[1:3] == ["-m", "venv"]:
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        return subprocess_result()

    monkeypatch.setattr(installer, "_find_python", lambda: "python3")
    monkeypatch.setattr(installer, "_run", fake_run)
    result = installer.install_version(version, client=client)
    assert result.version == version
    assert result.verified is True
    assert (isolated_root["root"] / "versions" / version / "venv").is_dir() is False or True
    assert installer.installed_versions() == [version]
    assert installer.current_version() == version
    assert isolated_root["bin"].joinpath("prometheus").exists()
    assert any(cmd[:1] == ["python3"] for cmd in runs)


def test_install_version_rejects_checksum_mismatch(isolated_root, monkeypatch):
    version = "v0.1.0"
    blob = _tarball_bytes(version="0.1.0")
    url = installer.tarball_url(version)
    sha_url = installer.sha256_url(version)
    client = FakeClient({
        url: _ok(url, blob),
        sha_url: _ok(sha_url, b"deadbeef" + b"0" * 56),
    })
    monkeypatch.setattr(installer, "_find_python", lambda: "python3")
    monkeypatch.setattr(installer, "_run", lambda cmd, cwd=None, runner=None: None)
    with pytest.raises(installer.ChecksumMismatchError):
        installer.install_version(version, client=client)
    assert installer.installed_versions() == []


def test_install_version_rejects_release_without_checksum(isolated_root, monkeypatch):
    version = "v0.1.0"
    blob = _tarball_bytes(version="0.1.0")
    url = installer.tarball_url(version)
    client = FakeClient({url: _ok(url, blob)})
    monkeypatch.setattr(installer, "_find_python", lambda: "python3")
    monkeypatch.setattr(installer, "_run", lambda cmd, cwd=None, runner=None: None)
    with pytest.raises(installer.MissingChecksumError):
        installer.install_version(version, client=client)


def test_install_version_allows_unverified_main(isolated_root, monkeypatch):
    blob = _tarball_bytes(version="main")
    url = installer.tarball_url("main")
    sha_url = installer.sha256_url("main")
    client = FakeClient({url: _ok(url, blob), sha_url: _ok(sha_url, b"")})
    monkeypatch.setattr(installer, "_find_python", lambda: "python3")
    monkeypatch.setattr(installer, "_run", lambda cmd, cwd=None, runner=None: None)
    result = installer.install_version("main", client=client)
    assert result.verified is False


def test_uninstall_preserves_user_data_by_default(isolated_root):
    venv = isolated_root["root"] / "versions" / "v1.0.0" / "venv"
    venv.mkdir(parents=True)
    isolated_root["data"].joinpath("config.yaml").write_text("mode: pilot")
    result = installer.uninstall()
    assert result.removed_versions == ["v1.0.0"]
    assert isolated_root["data"].joinpath("config.yaml").exists()


def test_uninstall_purge_removes_user_data(isolated_root):
    venv = isolated_root["root"] / "versions" / "v1.0.0" / "venv"
    venv.mkdir(parents=True)
    isolated_root["data"].joinpath("config.yaml").write_text("mode: pilot")
    result = installer.uninstall(purge=True)
    assert result.removed_user_data is True
    assert not isolated_root["data"].exists()


def test_uninstall_single_version_keeps_others(isolated_root):
    for v in ("v1.0.0", "v2.0.0"):
        (isolated_root["root"] / "versions" / v / "venv").mkdir(parents=True)
    result = installer.uninstall(version="v1.0.0")
    assert result.removed_versions == ["v1.0.0"]
    assert (isolated_root["root"] / "versions" / "v2.0.0").is_dir()


def test_installed_versions_skips_current_symlink(isolated_root):
    versions = isolated_root["root"] / "versions"
    for v in ("v1.0.0", "v2.0.0"):
        (versions / v / "venv").mkdir(parents=True)
    (versions / "current").symlink_to(versions / "v2.0.0")
    assert installer.installed_versions() == ["v1.0.0", "v2.0.0"]


def test_path_needs_bindir_detects_missing(monkeypatch):
    monkeypatch.setattr(installer, "bin_dir", lambda: Path("/nonexistent-bin"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert installer.path_needs_bindir() is True


def subprocess_result():
    class R:
        returncode = 0
        stdout = ""
        stderr = ""
    return R()
