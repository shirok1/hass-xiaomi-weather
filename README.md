# 小米天气 · Home Assistant

使用小米天气云端数据的 custom integration，支持 UI 配置、多城市、实时天气、日预报、小时预报以及中国 AQI、PM2.5、PM10。每个城市每 15 分钟共享一次请求，预报服务从缓存读取。

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

城市名称提交后，如有多个结果，会显示包含地区和城市代码的可搜索候选列表；只有一个结果时直接进入确认页。这是 HA 原生多步配置，不是输入过程中实时请求接口。城市代码指 `101` 开头的九位中国天气代码，不是行政区划代码。

确认页展示解析后的城市、代码和实际坐标。「显示设置」中可修改名称，新配置默认使用城市名称，重配置默认保留原名称。位置不正确时，勾选「重新选择位置」并提交即可回到来源选择。只有最后提交并成功验证天气后才保存；验证失败会停留在确认页，保留已选城市和名称，可直接重试。

区域页只使用区域坐标，不再与手动坐标竞争。区域坐标在提交区域选择时读取，确认保存后不会自动跟随区域移动；需要重新配置以更新。城市页的「指定坐标」是显式覆盖城市默认坐标，纬度和经度须一起填写。所有组合输入方式仍然支持，但只显示当前路径相关的字段。

目前只支持中国大陆 `weathercn` 城市。位置解析由小米完成，例如北京示例坐标可能匹配东城区，而直接填写 `101010100` 表示北京市；城市匹配粒度由服务端决定。两者都填写时由用户确保城市与坐标对应。

每个解析后的城市代码只能配置一次，不同输入方式匹配到同一城市时也会防止重复配置。配置菜单的「重新配置」复用上述来源选择和确认流程，不会把旧坐标或旧城市代码自动混入新输入；保存后自动重载。重配置必须仍属于原城市；变更城市请添加新的集成并移除旧城市，以保持实体身份稳定。已有配置无需迁移。实体名称可在 HA 中单独修改。

## 实体与预报

- 天气：天气状况、摄氏温度、体感温度、湿度、hPa 气压、km/h 风速、风向、UV 指数。
- 日预报：日期、最高/最低温度、白天天气状况；数量由服务端决定，实测 15 天。
- 小时预报：时间、温度、天气状况；数量由服务端决定，实测 23 个时段。
- 传感器：中国空气质量指数、PM2.5、PM10（µg/m³）。中国 AQI 不能直接当作美国 EPA AQI 使用。

预报通过 HA 的标准 `weather.get_forecasts` 提供，不写入 state attributes：

```yaml
action: weather.get_forecasts
target:
  entity_id: weather.beijing
data:
  type: daily # 或 hourly
```

实际实体 ID 以 HA 创建的结果为准。预报时间输出 UTC，按数据源提供的时区解释；晴天/晴夜依据所选位置的日出日落计算。日预报采用白天天气码。

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

`uv.lock` 固定环境；`homeassistant-stubs==2026.9.1` 同时固定 HA 运行时。ty 检查组件及测试，不全局忽略诊断。pytest 使用真实 Home Assistant 测试框架、真实本地 aiohttp HTTP 测试服务和去除冗余字段的实际接口 fixture；常规测试不请求小米服务。覆盖率门槛为 95%。GitHub Actions 执行同样的检查。

## 上游质量与提交边界

实现遵循 config flow、typed `ConfigEntry.runtime_data`、共享 `DataUpdateCoordinator`、异步 session 注入、实体唯一 ID、翻译、重配置、卸载及诊断等 HA 模式。详情见 `docs/quality.md`。

这不是已进入 Home Assistant Core 的集成，也不声明取得官方质量等级。正式提交 Core 前还需要：将独立于 HA 的 `api.py` 发布为有版本的外部 Python 库并引用；发布 `shirok1/hass-xiaomi-weather` 仓库；处理品牌资源、官方文档和 Core 仓库的 hassfest/完整 CI；确认维护与数据源接入方案可被上游接受。维护者为 `@shirok1`，仓库地址采用 `https://github.com/shirok1/hass-xiaomi-weather`。

参考：[HA 天气实体](https://developers.home-assistant.io/docs/core/entity/weather/)、[数据获取](https://developers.home-assistant.io/docs/integration_fetching_data/)、[集成质量标准](https://developers.home-assistant.io/docs/core/integration-quality-scale/)。
