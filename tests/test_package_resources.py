from __future__ import annotations



from prometheus_cli.resources import (
    copy_default_user_config,
    get_default_bundles_dir,
    get_default_bundles_v1_dir,
    get_default_config_path,
    get_default_i18n_dir,
    get_default_prompts_dir,
    get_default_schemas_dir,
    get_resource_root,
    list_packaged_bundles,
    list_packaged_bundles_v1,
    resolve_bundles_dir,
    resolve_bundles_v1_dir,
)


class TestResourceRoot:
    def test_root_exists_and_is_directory(self):
        root = get_resource_root()
        assert root.is_dir(), f"resource root {root} is not a directory"

    def test_root_is_inside_package(self):
        root = get_resource_root()
        assert "prometheus_cli" in root.parts


class TestBundleDirs:
    def test_v2_bundles_dir_has_yaml_files(self):
        bundles = list_packaged_bundles()
        assert len(bundles) >= 8, f"expected >= 8 v2 bundles, got {len(bundles)}"
        names = [p.name for p in bundles]
        assert any("spark" in n for n in names)
        assert any("ember" in n for n in names)
        assert any("forge" in n for n in names)

    def test_v1_bundles_dir_has_yaml_files(self):
        bundles = list_packaged_bundles_v1()
        assert len(bundles) >= 4, f"expected >= 4 v1 bundles, got {len(bundles)}"

    def test_v2_bundles_are_valid_yaml(self):
        import yaml
        for path in list_packaged_bundles():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
            assert "id" in data, f"{path.name} missing 'id'"
            assert "schema_version" in data, f"{path.name} missing 'schema_version'"

    def test_get_default_bundles_dir_returns_directory(self):
        d = get_default_bundles_dir()
        assert d.is_dir()

    def test_get_default_bundles_v1_dir_returns_directory(self):
        d = get_default_bundles_v1_dir()
        assert d.is_dir()


class TestOtherResourceDirs:
    def test_prompts_dir(self):
        d = get_default_prompts_dir()
        files = list(d.glob("*")) if d.is_dir() else []
        assert len(files) >= 1, f"expected prompts, got {len(files)} in {d}"

    def test_schemas_dir(self):
        d = get_default_schemas_dir()
        files = list(d.glob("*")) if d.is_dir() else []
        assert len(files) >= 1, f"expected schemas, got {len(files)} in {d}"

    def test_i18n_dir(self):
        d = get_default_i18n_dir()
        files = list(d.glob("*")) if d.is_dir() else []
        assert len(files) >= 1, f"expected i18n files, got {len(files)} in {d}"

    def test_default_config_path(self):
        p = get_default_config_path()
        assert p.is_file(), f"default config not found at {p}"


class TestResolveBundlesDir:
    def test_explicit_wins(self, tmp_path):
        result = resolve_bundles_dir(explicit=tmp_path)
        assert result == tmp_path

    def test_falls_back_to_packaged_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / "fake_home"))
        result = resolve_bundles_dir()
        assert result == get_default_bundles_dir()

    def test_user_home_takes_precedence_over_packaged(self, tmp_path, monkeypatch):
        user_home = tmp_path / "prometheus_home"
        user_bundles = user_home / "bundles"
        user_bundles.mkdir(parents=True)
        (user_bundles / "my-bundle.yaml").write_text("id: my-bundle\n", encoding="utf-8")
        monkeypatch.setenv("PROMETHEUS_HOME", str(user_home))
        monkeypatch.chdir(tmp_path)
        result = resolve_bundles_dir()
        assert result == user_bundles

    def test_v1_resolve_explicit(self, tmp_path):
        result = resolve_bundles_v1_dir(explicit=tmp_path)
        assert result == tmp_path

    def test_v1_falls_back_to_packaged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / "fake_home"))
        result = resolve_bundles_v1_dir()
        assert result == get_default_bundles_v1_dir()


class TestCopyDefaultUserConfig:
    def test_copies_bundles_into_target(self, tmp_path):
        copied = copy_default_user_config(tmp_path / "user_config")
        assert len(copied) > 0
        v2_dest = tmp_path / "user_config" / "bundles_v2"
        assert v2_dest.is_dir()
        assert len(list(v2_dest.glob("*.yaml"))) >= 8

    def test_does_not_overwrite_existing(self, tmp_path):
        dest = tmp_path / "user_config"
        dest_v2 = dest / "bundles_v2"
        dest_v2.mkdir(parents=True)
        existing = dest_v2 / "01-spark-cpu-8gb.yaml"
        existing.write_text("custom: content\n", encoding="utf-8")

        copy_default_user_config(dest, overwrite=False)

        assert existing.read_text() == "custom: content\n"

    def test_overwrite_replaces_existing(self, tmp_path):
        dest = tmp_path / "user_config"
        dest_v2 = dest / "bundles_v2"
        dest_v2.mkdir(parents=True)
        existing = dest_v2 / "01-spark-cpu-8gb.yaml"
        existing.write_text("custom: content\n", encoding="utf-8")

        copy_default_user_config(dest, overwrite=True)

        assert "custom: content" not in existing.read_text()


class TestNoWeights:
    WEIGHT_EXTS = {".bin", ".gguf", ".pt", ".pth", ".onnx", ".safetensors"}

    def test_no_model_weights_in_resources(self):
        root = get_resource_root()
        leaked = [f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in self.WEIGHT_EXTS]
        assert leaked == [], f"found weight files in resources: {leaked}"
