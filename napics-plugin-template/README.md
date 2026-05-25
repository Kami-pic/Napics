# napics-plugin-template

Napics 插件开发模板 — 快速创建自定义插件。

## 使用方法

1. 点击 GitHub 上的 "Use this template" 创建你的插件仓库
2. 修改 `manifest.json` 中的插件信息
3. 在 `__init__.py` 中实现你的逻辑
4. 打包为 zip 发布到你的 GitHub Releases

## 目录结构

```
my-plugin/
├── manifest.json    # 插件声明（必须）
├── __init__.py      # 注册入口（必须）
└── README.md        # 说明文档
```

## 发布

1. 将插件目录打包为 zip（zip 内根目录为插件目录名）
2. 创建 GitHub Release 并上传 zip
3. 创建 `index.json` 描述你的插件源
4. 用户在 napics 插件中心添加你的源 URL 即可安装

### index.json 示例

```json
{
    "name": "我的插件源",
    "version": "1.0.0",
    "description": "自定义插件集合",
    "plugins": [
        {
            "id": "my-plugin",
            "name": "我的插件",
            "version": "1.0.0",
            "description": "一个自定义搜索源",
            "category": "search",
            "icon": "🔍",
            "risk_level": "low",
            "download_url": "https://github.com/你的用户名/my-plugin/releases/download/v1.0.0/my-plugin.zip",
            "sha256": ""
        }
    ]
}
```

## 开发文档

完整开发指南见 [PLUGIN_DEV_GUIDE.md](https://github.com/nicq/napics/blob/main/backend/plugins/PLUGIN_DEV_GUIDE.md)
