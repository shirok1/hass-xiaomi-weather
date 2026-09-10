# 质量说明

以下是本仓库实现与验证范围，不是官方质量等级认证。

| 范围 | 实现与验证 |
| --- | --- |
| UI 设置 | 位置来源分流、折叠组合输入、名称候选补全、确认结果、失败原地重试、每城市唯一配置、中英文表单 |
| 生命周期 | 首次刷新后加载平台、首次失败重试、平台卸载与 coordinator 订阅清理 |
| 轮询 | 每城市一个 coordinator、15 分钟更新、共享快照、对外深复制结构化数据、相同数据不重复推送 |
| 天气 | 原生单位、日/小时/昼夜预报、内存缓存、更新通知、UTC 时间、日出日落判定、小时风按时间匹配 |
| 扩展数据 | 30 个传感器、完整空气质量、日小时 AQI 独立时间轴、预警/台风列表、降水原始序列、昨日/上一时段观测、全部指数、源时间戳 |
| 天气实体属性 | 仅 HA 标准天气属性及通用实体元数据；单位转换由 HA 处理，扩展传感器状态与原始响应不重复挂载；测试约束状态字段及用户单位覆盖 |
| 完整响应动作 | 标准 HA 实体服务与实体访问校验、支持多目标、只读缓存、深复制、未加载/不可用时不能读取旧值 |
| 实体 | 唯一 ID、service device、has_entity_name、传感器 device/state class；4 个观测/更新时间归类诊断；昨日系列、上一时段温度及日/小时预报 AQI 共 7 个默认禁用，沿用 HA 注册机制保留已有启用设置 |
| 异常 | 超时/HTTP/JSON/结构错误转换、unavailable 与恢复、缺失值显示 unknown |
| 配置变更 | 三种位置输入方式均可重配置，同城解析后重载；城市变化以新条目表示 |
| 隐私 | 诊断字段白名单，不返回位置、名称或服务端原文 |
| 环境 | uv lock、HA 与 stubs 版本一致、Ruff、ty、pytest 覆盖率门槛 |

## Core 天气实现参照

参照版本为 Home Assistant Core **2026.9.1**：[Google Weather](https://www.home-assistant.io/integrations/google_weather/) 官方质量等级为 Platinum，其 [weather.py](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/google_weather/weather.py) 使用原生天气属性及缓存预报，没有提供商数据汇总的 `extra_state_attributes`。本集成沿用这一边界，按 [WeatherEntity 规范](https://developers.home-assistant.io/docs/core/entity/weather/) 提供有可靠源数据的标准字段。云量、露点、阵风等缺少源数据时不派生补值；污染物浓度通过有明确单位的传感器提供。此参照不代表本集成获得同等认证。

## 当前限制

客户端协议尚无小米官方开发者文档，天气码映射基于 weathercn 编码约定。真实响应的成功调用证明当前接入可用，不证明其他地区和天气现象已全部实测。只支持 weathercn 中国大陆城市。

日概率按百分数解释，`1` 保持为 1%，不自动猜测为 100%；小时风缺少 unit 时按现有 weathercn 客户端约定使用 km/h，显式未知单位不标为 km/h。污染物采用中国数据源的浓度单位：CO 为 mg/m³，其余五项为 μg/m³。这些属于客户端协议约定，而非小米官方稳定性承诺；[对照实现与来源](zhishengweather-xiaomi-audit.md)保留在审计报告中。

未验证语义的分钟强度、四点概率、显示标志、生活指数代码均以原值开放，不虚构单位、粒度或标签。预警与台风接受完整记录，非空格式通过合成数据验证；不声称已经实测有效预警/台风事件。月相/能见度只在数据源有值时显示。完整数据动作保留原始状态和缺失标记，使用方须按提供商语义解释；诊断仍执行原有字段白名单。

`api.py` 不依赖 Home Assistant，方便单独发布与维护。但当前仍随 custom component 分发；Core 接入要求的外部库发布尚未完成。维护者为 `@shirok1`，发布地址采用 `shirok1/hass-xiaomi-weather`。本仓库不冒用官方品牌认证或 quality_scale 等级。

## 验证 fixture

`tests/fixtures/weather.json` 来自 2026-09-08 对小米 HTTPS 接口的实际响应，城市参数为北京示例坐标。仅保留使用的天气、预报及三项空气质量相关数据。测试固定响应，不依赖今天的天气变化。

`tests/fixtures/weather_full.json` 是 2026-09-10 22:45 左右使用北京公开示例坐标和现有请求参数，通过系统 curl 获取的完整响应（含全部数据源元信息），SHA-256 为 `73d7a85de9f73359dc217cdec313179ad1188ecec9e6f06fe85b58d95f3a6781`。原样保留，预警与台风为空，分钟降水全零。扩展测试在内存中单独构造非空预警、台风和非零降雨，不修改实测 fixture，也不将其误标为实时证据。
