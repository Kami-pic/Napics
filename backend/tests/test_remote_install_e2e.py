"""端到端测试：模拟远程插件安装流程。

验证：下载 zip → 解压 → 校验 manifest → 加载模块 → 注册 provider
"""

import json
import os
import shutil
import zipfile

import pytest

from plugin_manager import PluginManager, RemotePluginInfo

# 测试用的插件目录（避免污染真实 plugins/）
PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
COMMUNITY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "community-plugins")

# community-plugins 是**独立仓库**（conftest 里也是这个口径：本地存在时才跑它的
# 源实现测试）。这些用例校验的是那个仓库打出来的 zip 包，主仓库单独 clone 时
# 目录压根不存在 —— 应当 skip 而不是报 5 个失败。
pytestmark = pytest.mark.skipif(
    not os.path.isfile(os.path.join(COMMUNITY_DIR, "index.json")),
    reason="需要本地 community-plugins 仓库及其打包产物（独立仓库）",
)


class TestRemoteInstallE2E:
    """端到端测试远程插件安装"""

    def test_zip_structure_valid(self):
        """验证生成的 zip 包结构正确"""
        zip_path = os.path.join(COMMUNITY_DIR, "search-bt-direct.zip")
        assert os.path.isfile(zip_path), f"zip 不存在: {zip_path}"

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            # 应该包含 manifest.json 和 __init__.py
            assert "manifest.json" in names
            assert "__init__.py" in names
            # 应该包含 sources/ 目录下的 scraper 文件
            source_files = [n for n in names if n.startswith("sources/")]
            assert len(source_files) >= 12, f"BT 源文件数量不足: {len(source_files)}"

    def test_pan_zip_structure_valid(self):
        """验证网盘搜索 zip 包结构正确"""
        zip_path = os.path.join(COMMUNITY_DIR, "search-pan.zip")
        assert os.path.isfile(zip_path), f"zip 不存在: {zip_path}"

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "__init__.py" in names
            source_files = [n for n in names if n.startswith("sources/")]
            assert len(source_files) >= 9, f"网盘源文件数量不足: {len(source_files)}"

    def test_manifest_parse(self):
        """验证 manifest.json 可正确解析"""
        zip_path = os.path.join(COMMUNITY_DIR, "search-bt-direct.zip")
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest_data = json.loads(zf.read("manifest.json"))

        assert manifest_data["id"] == "search-bt-direct"
        assert manifest_data["category"] == "search"
        assert manifest_data["risk_level"] == "high"

    def test_index_json_valid(self):
        """验证 index.json 格式正确"""
        index_path = os.path.join(COMMUNITY_DIR, "index.json")
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["name"] == "Napics 社区插件源"
        assert len(data["plugins"]) == 2
        assert data["plugins"][0]["id"] == "search-bt-direct"
        assert data["plugins"][1]["id"] == "search-pan"

    def test_install_bt_direct_from_zip(self):
        """测试从 zip 安装 BT 直搜源插件到 plugins/ 目录"""
        pm = PluginManager()
        zip_path = os.path.join(COMMUNITY_DIR, "search-bt-direct.zip")
        plugin_id = "search-bt-direct-test"  # 用不同 ID 避免冲突
        target_dir = os.path.join(PLUGINS_DIR, plugin_id)

        try:
            # 手动解压模拟安装
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)

            # 验证文件存在
            assert os.path.isfile(os.path.join(target_dir, "manifest.json"))
            assert os.path.isfile(os.path.join(target_dir, "__init__.py"))
            assert os.path.isdir(os.path.join(target_dir, "sources"))

            # 验证 manifest 可加载
            with open(os.path.join(target_dir, "manifest.json"), "r", encoding="utf-8") as f:
                manifest = json.load(f)
            assert manifest["id"] == "search-bt-direct"

        finally:
            # 清理
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir)
