# 品牌资源来源

本集成使用 Home Assistant 官方 Xiaomi 品牌资源，与官方 `xiaomi`、`xiaomi_aqara` 集成所引用的资源一致。四张原图未经修改。

- 来源仓库：[home-assistant/brands](https://github.com/home-assistant/brands)
- 固定提交：[`5a4d2ffbbef0613a7c9327a063b490105508abbc`](https://github.com/home-assistant/brands/tree/5a4d2ffbbef0613a7c9327a063b490105508abbc/core_brands/xiaomi)
- 本地目录：`custom_components/xiaomi_weather/brand/`

| 本地文件 | 尺寸 | 官方原文件 | SHA-256 |
| --- | --- | --- | --- |
| `icon.png` | 256 × 256 | [下载原图](https://raw.githubusercontent.com/home-assistant/brands/5a4d2ffbbef0613a7c9327a063b490105508abbc/core_brands/xiaomi/icon.png) | `49915eb78191ecacce651dfe5527cc118189b6973b2e258069931398dd93c4a7` |
| `icon@2x.png` | 512 × 512 | [下载原图](https://raw.githubusercontent.com/home-assistant/brands/5a4d2ffbbef0613a7c9327a063b490105508abbc/core_brands/xiaomi/icon%402x.png) | `6620d754d49797918f5c09e5a7c9dec79237e8f6f392c42312b9e0b470d6b7eb` |
| `logo.png` | 931 × 256 | [下载原图](https://raw.githubusercontent.com/home-assistant/brands/5a4d2ffbbef0613a7c9327a063b490105508abbc/core_brands/xiaomi/logo.png) | `12f077643485a79d830c7b963641c1bf589d725d6504d298e7dd415b3b325c1c` |
| `logo@2x.png` | 1861 × 512 | [下载原图](https://raw.githubusercontent.com/home-assistant/brands/5a4d2ffbbef0613a7c9327a063b490105508abbc/core_brands/xiaomi/logo%402x.png) | `25a8aae2fa2561b44f670fe39db8379270e3d9f12dfa2034490d508c9b79f5c2` |

HA 2026.9.1 的自定义集成品牌接口按当前 integration domain 查找本地 `brand/` 文件，没有 manifest 配置可以将其映射到另一集成的图片地址，因此采用官方的随组件分发方式。方形 icon 用于集成列表，横版 logo 用于配置等页面；两者均提供高清版本。上游未提供专用深色图片，深色模式使用 HA 内置 fallback，无需运行时请求外网。

参考：[HA 品牌图片文档](https://developers.home-assistant.io/docs/core/integration/brand_images/)。正式进入 Core 时，应将图片放到官方 brands 仓库并移除组件内的 `brand/` 目录。
