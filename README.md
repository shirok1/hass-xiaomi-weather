# 小米天气 · Home Assistant

使用小米天气云端数据的 custom integration，支持 UI 配置、多城市、实时天气、日/小时/昼夜预报、完整空气质量、气象预警、短时降水、生活指数、昨日天气与台风摘要。每个城市每 15 分钟共享一次请求，预报及完整数据动作从缓存读取。

## 安装与配置

适配并测试于 **Home Assistant 2026.9.1 / Python 3.14.2+**。尚未验证旧版兼容性。

1. 将 `custom_components/xiaomi_weather` 整个目录复制到 HA 的 `/config/custom_components/xiaomi_weather`。
2. 重启 Home Assistant。
3. 在「设置 → 设备与服务 → 添加集成」搜索 **Xiaomi Weather**。
4. 选择位置来源，填写相关字段，最后在「确认位置」页提交。

| 位置来源 | 基本输入 | 折叠设置 |
| --- | --- | --- |
| 使用家庭或其他区域 | 默认选择“家庭”（`zone.home`），也可选其他区域 | 可指定城市名称或代码；留空自动匹配 |
| 搜索城市 | 城市名称、`101010100` 或 `weathercn:101010100` | 可同时指定经纬度；留空使用城市中心坐标 |
| 输入经纬度 | 纬度和经度，例如 `39.9042`、`116.4074` | 可指定城市名称或代码；留空自动匹配 |

城市名称、代码或坐标匹配成功后，始终显示包含地区和城市代码的可搜索候选列表；即使只有一个结果，也需要选择后再进入确认页。这是 HA 原生多步配置，不是输入过程中实时请求接口。城市代码指 `101` 开头的九位中国天气代码，不是行政区划代码。

确认页展示解析后的城市、代码和实际坐标。「显示设置」中可修改名称，选择区域时默认使用区域名称（如“家庭”）；其他新配置默认使用城市名称，其他重配置保留原名称。位置不正确时，勾选「重新选择位置」并提交即可回到来源选择。只有最后提交并成功验证天气后才保存；验证失败会停留在确认页，保留已选城市和名称，可直接重试。

区域页只使用区域坐标，不再与手动坐标竞争。区域坐标在提交区域选择时读取，确认保存后不会自动跟随区域移动；需要重新配置以更新。城市页的「指定坐标」是显式覆盖城市默认坐标，纬度和经度须一起填写。所有组合输入方式仍然支持，但只显示当前路径相关的字段。

目前只支持中国大陆 `weathercn` 城市。位置解析由小米完成，例如北京示例坐标可能匹配东城区，而直接填写 `101010100` 表示北京市；城市匹配粒度由服务端决定。两者都填写时由用户确保城市与坐标对应。

每个解析后的城市代码只能配置一次，不同输入方式匹配到同一城市时也会防止重复配置。配置菜单的「重新配置」复用上述来源选择和确认流程，不会把旧坐标或旧城市代码自动混入新输入；保存后自动重载。重配置必须仍属于原城市；变更城市请添加新的集成并移除旧城市，以保持实体身份稳定。已有配置无需迁移。实体名称可在 HA 中单独修改。

## 实体与预报

- 天气：天气状况、摄氏温度、体感温度、湿度、hPa 气压、km/h 风速、风向、UV 指数、有效的 km 能见度。
- 日预报：日期、最高/最低温度、白天天气、白天风速/风向、日降水概率；数量由服务端决定，实测 15 天。
- 小时预报：时间、温度、天气、风速/风向；风按自身时间戳对齐，实测 23 个时段。
- 昼夜预报：白天最高温与夜间最低温、各自的天气和风，分别以该地日出/日落为时段起点；实测响应可生成 30 个时段。全天降水概率不会冒充半天概率。
- 每个城市共 1 个天气实体和 29 个传感器，其中 4 个观测/更新时间、昨日系列、上一时段观测温度、逐日/逐小时预报 AQI 共 11 个传感器默认禁用；现有天气、AQI、PM2.5、PM10 实体身份保持不变。已启用的可选传感器在字段未返回时显示 unknown。

| 传感器 | 状态与附加信息 |
| --- | --- |
| AQI、六项污染物 | 中国 AQI；PM2.5、PM10、O₃、NO₂、SO₂ 为 μg/m³，CO 为 mg/m³；附发布时间、来源和污染物说明 |
| 首要污染物、空气质量建议 | 来源文本；长建议的完整内容在 `description` 属性，状态最多 255 字符 |
| 逐日/逐小时 AQI | 默认禁用，可按需启用。状态是预报序列第一点，`forecast` 属性为带 UTC 时间的完整序列；独立使用 AQI 发布时间，缺失点保留 null，不压缩时间轴 |
| 天气预警、台风数量 | 状态为数量，`items` 属性保留每条记录的所有字段，包括类型、等级、详情、时间、坐标和编号（以实际返回为准）；空数组为 0，缺失或无效列表为 unknown |
| 短时降水预报 | 状态为来源文案；属性保留整个 `minutely` 块，包括降水数组、概率数组、雨雪类型、状态和显示标志 |
| 雨区距离 | `kmNum` 原值，km；数据源返回 0 就保留 0，不据此推断正在下雨 |
| 洗车/运动代码 | 单独提供原始代码，不把未经验证的代码翻译为“适宜”；完整指数列表通过 `xiaomi_weather.get_data` 读取 |
| 昨日天气、昨日高低温、昨日 AQI | 共 4 个，默认禁用，可按需启用。昨日天气状态是数据源日期；属性保留昨日天气码、风、日出日落及其他字段；高低温和 AQI 可直接用于自动化 |
| 上一时段观测温度 | 默认禁用，可按需启用。`preHour` 中最新有效观测的温度，`observations` 属性保留全部历史观测；不作为当前实况 |
| 日出、日落、月相 | 对应实况当地日期；太阳时间采用 UTC timestamp，月相使用来源字符串，不自行计算补值 |
| 天气/空气质量/短时降水观测时间、数据源更新时间 | 归类为诊断实体，默认禁用，可按需启用；来源时间戳支持在自动化中判断数据年龄，下载成功不会把旧数据变成新观测 |

默认启用状态遵循 [HA 实体注册机制](https://developers.home-assistant.io/docs/core/entity/#registry-properties)，仅在首次注册实体时生效。升级会保留已有实体的启用/禁用状态；已启用的上述 11 个传感器如需停用，可在「设置 → 设备与服务 → 实体」中手动禁用。禁用传感器不影响完整数据动作读取对应源数据。

中国 AQI 不能直接当作美国 EPA AQI 使用。上述预报 AQI 与昨日/上一时段观测不配置实况测量统计，避免将不同时间的数据混进当前测量的长期统计。按需启用后，普通历史仍按 HA 状态更新时间记录，不会依据源时间戳回填过去的观测；AQI 预报传感器的历史表示预报值变化，不是实际 AQI 历史。诊断分类本身也不会排除 Recorder 记录。

不再提供“天气指数数量”传感器；升级重载时会移除旧实体注册项。列表长度不是小米返回的一项指数等级。完整响应 fixture 中该列表有 6 项：`uvIndex`、`humidity`、`feelsLike`、`pressure`、`carWash`、`sports`，各项为 `type/value` 对象。完整数据动作中列表路径为 `data.indices.indices`；外层另有 `status` 和 `pubTime`，本次样本的 `pubTime` 为空。

2026-09-10 查阅的[小米官方天气文档](https://zhuti.designer.xiaomi.com/docs/blog/weatherApi.html)描述的是 Android `content://weather/actualWeatherData` 主题读取接口，没有定义本集成 HTTP 接口的洗车/运动代码。[ZhishengWeather 的固定版本实现](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L880-L883)把两者的字符串 `"0"` 判为适宜，其他非空值判为不适宜；这是该客户端的实现，不是小米官方代码表。本次检索未找到完整、可核验的小米代码定义，因此这两个传感器继续保留原始代码，不套用其他天气服务的等级表。

预报通过 HA 的标准 `weather.get_forecasts` 提供，不写入 state attributes：

```yaml
action: weather.get_forecasts
target:
  entity_id: weather.beijing
data:
  type: daily # 或 hourly、twice_daily
```

实际实体 ID 以 HA 创建的结果为准。预报时间输出 UTC，按数据源提供的时区解释；晴天/晴夜依据所选位置的日出日落计算。日预报采用白天天气码。

### 原生天气详情的范围

天气实体遵循 [HA 官方 WeatherEntity 规范](https://developers.home-assistant.io/docs/core/entity/weather/)，参照 Core 2026.9.1 中官方标为 [Platinum 的 Google Weather](https://www.home-assistant.io/integrations/google_weather/) 的[天气实现](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/google_weather/weather.py)：实况使用标准属性，单位转换交给 HA，三类天气预报通过标准预报接口提供。

目前小米响应中语义明确、能够对应标准天气属性的字段已接入，见上方“天气”列表。默认天气详情能显示哪些项目由 HA 前端决定；缺失的能见度等数据不会补值。当前响应没有可用的云量、露点或阵风数据；空气质量中的 O₃ 浓度保留在带明确单位的传感器中，不仅凭字段同名映射到天气的 `ozone`。

AQI、污染物、预警、短时降水、生活指数等通过各自传感器读取，完整提供商响应通过下方动作按需获取。天气实体不重复挂载这些状态、原始数据块或序列。HA 允许集成定义额外属性，但这里采用标准天气字段，避免重复存储与独立的单位处理。

## 读取全部小米数据

`xiaomi_weather.get_data` 返回所选天气实体最近一次成功获取的**完整响应副本**，包括 `current`、`forecastDaily`、`forecastHourly`、`aqi`、`minutely`、`indices`、`alerts`、`typhoon`、`yesterday`、`preHour`，以及 `sourceMaps`、`brandInfo`、`url`、`chs`、`updateTime` 和将来新增的字段。只读缓存，不增加请求；实体不可用或已卸载时不能通过该动作读取旧缓存。

```yaml
action: xiaomi_weather.get_data
target:
  entity_id: weather.beijing
response_variable: xiaomi
```

结果按实体 ID 分组，完整响应位于 `xiaomi['weather.beijing']['data']`。例如：

```jinja
{{ xiaomi['weather.beijing']['data']['forecastDaily']['aqi']['value'] }}
{{ xiaomi['weather.beijing']['data']['minutely']['precipitation']['probability'] }}
```

此动作保留原始单位、缺失标记、状态和提供商字段，不执行归一化；使用其结果时须检查对应数据块的 `status`、时间及字段是否存在。完整响应按需返回，不会作为一个大属性持续写入实体状态；传感器上的预警、短时降水、AQI 序列等公开属性按 HA 的 Recorder 配置记录。

短时降水的 `value`、`probability`、`isShow` 等已完整开放，但尚无有效非零降雨样本确认强度单位和四点概率的时间粒度，因此不标成 mm/h，也不生成“几分钟后必定下雨”的计算结果。洗车/运动保留代码，月相和能见度缺失则为空。小米返回的台风摘要全部保留；其他服务的雷达、台风轨迹、历史档案和本地月球天文计算不在本集成中。

## 故障处理与数据边界

首次请求失败时 HA 自动重试设置；后续轮询失败会使实体 unavailable，成功后自动恢复。HTTP 请求超时 20 秒，无内部循环重试。未知天气码不会伪装成晴天；空值、非有限数字与 `-999` 缺失值不会显示成零。可选空气质量数据缺失时传感器显示 unknown；缺少预报时返回空列表。

无法配置时检查城市代码、坐标、DNS 及到 `weatherapi.market.xiaomi.com:443` 的连接。持续 unavailable 时检查 Home Assistant 日志。重新配置会验证连接。移除集成可停止轮询；无需清理外部账户。

小米接口由天气客户端使用，**不是具有公开稳定性承诺的官方开发者 API**；可能改变字段、限流、返回缓存数据或停止服务。当前没有数据新鲜度保证。无小米账号或用户 API 密钥需求，内置参数来自客户端协议。位置坐标和城市代码会发送给小米；诊断下载只包含更新成功状态和预报条数，不包含名称、坐标、城市代码或原始响应。

## 开发与检查

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked ty check
uv run --locked pytest
```

`uv.lock` 固定环境；`homeassistant-stubs==2026.9.1` 同时固定 HA 运行时。ty 检查组件及测试，不全局忽略诊断。pytest 使用真实 Home Assistant 测试框架、真实本地 aiohttp HTTP 测试服务、精简及完整实际响应 fixture。非空预警/台风、非零降雨等测试使用明确标注的模拟数据，不代表已经验证此类实时天气。常规测试不请求小米服务。覆盖率门槛为 95%。GitHub Actions 执行同样的检查。

## 上游质量与提交边界

实现遵循 config flow、typed `ConfigEntry.runtime_data`、共享 `DataUpdateCoordinator`、异步 session 注入、实体唯一 ID、翻译、重配置、卸载及诊断等 HA 模式。详情见 `docs/quality.md`。

这不是已进入 Home Assistant Core 的集成，也不声明取得官方质量等级。正式提交 Core 前还需要：将独立于 HA 的 `api.py` 发布为有版本的外部 Python 库并引用；发布 `shirok1/hass-xiaomi-weather` 仓库；处理品牌资源、官方文档和 Core 仓库的 hassfest/完整 CI；确认维护与数据源接入方案可被上游接受。维护者为 `@shirok1`，仓库地址采用 `https://github.com/shirok1/hass-xiaomi-weather`。

参考：[HA 天气实体](https://developers.home-assistant.io/docs/core/entity/weather/)、[数据获取](https://developers.home-assistant.io/docs/integration_fetching_data/)、[集成质量标准](https://developers.home-assistant.io/docs/core/integration-quality-scale/)。


## 集成图标

采用 Home Assistant 官方 Xiaomi 品牌资源，与官方 `xiaomi`、`xiaomi_aqara` 集成一致，包含方形 icon、横版 logo 及各自的高清 PNG。HA 没有为自定义域名直接引用另一个集成品牌图片的配置项，因此按官方支持方式将原图随组件放入 `brand/`，无需运行时下载；深色模式由 HA 原生回退处理。

图片来源、固定版本和校验值见 [品牌资源说明](docs/brand-assets.md)。
