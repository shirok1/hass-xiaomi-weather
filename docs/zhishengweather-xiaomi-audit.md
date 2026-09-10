# 小米天气功能覆盖审计：对比 ZhishengWeather

> 后续实现已补齐本报告发现的数据入口：标准预报、30 个传感器以及完整响应动作。当前用法和数据边界见 [README](../README.md)。下文保留实施前的固定版本审计结果，作为对照依据。

审计日期：2026-09-10。上游固定版本 `bd2dd39c467ce886c7819ee364752ed12b2bbcc2`，本仓库版本 `75f7664bc0669557cba9d4dac3eb2db2804864c8`。上游 checkout：`/tmp/zhishengweather-audit.vFNL3a`。

**结论：我们尚未用尽现有小米响应。** 最大缺口是已有响应内的污染物、预警、预报扩展字段，以及昨日天气、生活指数和分钟降水。ZhishengWeather 也没有用尽响应：它漏掉逐日 AQI、分钟概率数组及若干昨日字段。其雷达、完整台风路径、历史天气、月球天文和部分遥测来自其他来源或本地计算，不能据此宣称小米接口提供这些功能。

这是一份固定版本源码对比，辅以两个城市的一次实时取样；不是小米全部 API、所有地区和所有天气状况的穷举。DTO 声明说明客户端“准备解析”，实际 mapper 说明“接入产品”，只有真实有效响应才能说明“当前接口返回”。三者不能互相替代。

## 已证实的接口范围

上游只定义三个小米端点：`wtr-v3/location/city/search`、`location/city/geo`、`weather/all`；天气调用明确传 `days=15`。未发现单独的分钟降水、历史、雷达或台风小米接口。[API 定义](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/XiaomiApi.kt#L13-L47)、[天气调用](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L519-L535)

搜索和反向地理编码均有实际调用；本仓库额外已有 `location/city/info`，所以地理定位方面并不落后于上游。[上游搜索调用](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/CityRepository.kt#L64-L87)、[上游定位调用](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/LocationSource.kt#L225-L236)

上游默认 AUTO 允许 Open-Meteo 补缺，手选 XIAOMI 才保持天气纯源；浏览其默认界面无法判断某个读数是不是小米提供。[来源选择与补全](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L39-L69)

## 功能对照

本仓库基线依据：[解析模型与映射](../custom_components/xiaomi_weather/api.py)、[Weather 实体与 forecast 输出](../custom_components/xiaomi_weather/weather.py)。这里“缺失”指未进入实体状态或预报输出；原始 HTTP 响应仍可能包含它。

| 功能 | 我们目前 | 上游实际小米映射 | 本次响应证据及判断 |
| --- | --- | --- | --- |
| 当前基础天气 | 温度、体感、湿度、气压、风、UV 等 | 对应字段；另声明并映射 visibility | 核心已覆盖；两地 visibility 都为空，不宜为对齐字段而承诺可用 |
| AQI | AQI、PM2.5、PM10 | 六项污染物、首要污染物、健康建议 | 两地均有 O₃、NO₂、SO₂、CO 和 suggest，可优先补充 |
| 气象预警 | 未解析/暴露 | 标题、详情、等级、发布时间、派生严重度 | 两地 alerts 为空；映射有证据，实际非空格式仍需取样 |
| 逐日预报 | 日期、高低温、白天天气 | 最多 15 天；兼顾 from/to 天气、风速、概率、日出日落、月相字段 | 两地风与日出日落有值，概率全 0，月相 null；应补预报扩展字段 |
| 逐小时预报 | 日期、温度、天气 | 最多 24 点；额外风速、AQI | 两地有小时风、23 点 AQI；时间对齐与单位须逐字段验证 |
| AQI 预报 | 未用 | 小时 AQI 已映射；逐日 AQI 未声明 | 两地逐日 15 点、逐时 23 点；属于双方仍可深挖的部分 |
| 分钟降水 | 未用 | 文案、value 序列、pubTime、kmNum | 两地有 120 个 0、有效发布时间及 status=0，但 isShow=false；有结构不等于已验证降雨事件 |
| 生活指数 | 未用 | 只取 carWash、sports，value=="0" 判适宜 | 两地有六项；另四项是 UV、湿度、体感、气压，主要为已有实况信息 |
| 昨日天气 | 未用 | 高低温、AQI、weatherEnd | 两地有值；date、weatherStart、昨日风和日出日落还可保留 |
| 台风简要 | 未用 | 名称、英文名、类型、中心风速 | 两地 typhoon 为空；DTO 和映射存在，但还缺非空接口证据 |
| 日月天文 | 日出日落仅用于内部日期/晴夜判断 | 太阳时间来自小米；月相/月出/月落缺失时本地计算 | 可考虑暴露太阳时间；月球天文不能算小米独有能力 |
| 历史、雷达、完整台风路径 | 未接入 | 其他数据源 | 不属于本次“小米未榨干”的直接缺口 |

上游映射证据：[实况、小时、AQI、预警](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L786-L860)、[逐日](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L732-L783)、[分钟、指数、昨日、台风](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L862-L904)。这些数据确有 UI 消费，例如[分钟卡](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/ui/home/HomeScreen.kt#L2074-L2100)、[生活指数](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/ui/home/HomeScreen.kt#L3299-L3316)、[昨日与台风卡入口](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/ui/home/HomeScreen.kt#L1119-L1120)。

## 容易误判的细节

1. **上游不是完整协议说明。** XiaomiModels.kt 明言“精简为需要的字段”，JSON 配置忽略未知字段。日风 direction、小时风 direction/datetime、预警 type、AQI pubTime、昨日 date/weatherStart、台风 code/lat/lon 虽有 DTO 声明，相关 mapper 没有全部传入产品模型；逐日 AQI 则连 DTO 都没有。[DTO](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/XiaomiModels.kt#L5-L186)、[忽略未知字段配置](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/XiaomiApi.kt#L49-L52)

2. **分钟数组不能直接照抄。** 上游把 `precipitation.value` 当作每分钟一点，时间取 precipitation.pubTime，未解析 status、isShow、precipitation.probability 或单位字段；maxProbability 实际是文本，不能当数值概率。本次两个无雨样本的 isShow=false，尚不能判断它是“无雨时隐藏”还是“数据不应展示”的协议标志，也未证明非零强度单位。[分钟 DTO](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/XiaomiModels.kt#L134-L154)、[分钟 mapper](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L917-L933)、[每分钟步长](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/model/Nowcast.kt#L60-L69)

3. **预报数组有独立时间轴。** 上游小时风和 AQI 按同一索引拼接温度序列，却忽略风 datetime 与 AQI 独立 pubTime。我们新增时应按时间对齐，避免错位；小时风缺少显式 unit，不能把实况风速单位直接当作协议保证。日概率在本次样本中全 0，具备字段不代表已验证降水天气下的有效性。[小时 DTO](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/XiaomiModels.kt#L72-L95)、[小时 mapper](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L808-L830)

4. **昼夜不能无脑映射成 twice_daily。** 上游将 from/to 两段天气合成“较显著天气”及转折描述；我们目前只用 from。可先保留夜间字段，是否暴露 Home Assistant twice_daily 需按其接口语义设计。[上游日天气映射](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L749-L779)

5. **六个 indices 不等于六个新生活指数。** 本次是 uvIndex、humidity、feelsLike、pressure、carWash、sports。上游只映射后两项；“0=适宜”是其客户端解释，仍需带其他值样本或可靠协议依据验证。[指数 mapper](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L880-L883)

6. **测试没有替代实时证据。** 检查到的小米专项测试覆盖日期归整、单位换算、观测发布时间、Open-Meteo 补缺等 helper；未发现涵盖上述所有字段的真实小米响应 fixture 或联机集成测试。本次未运行上游 Android 测试。[单位与时间测试](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/test/kotlin/com/zhisheng/weather/data/WeatherRepositoryTest.kt#L213-L234)

## 不能归到小米名下的上游功能

- **月相、月出、月落：** 小米 mapper 仅尝试读 moonPhase，随后调用 MoonCalc；本地算法补全缺项。[小米取数后的 enrich](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L532-L536)、[月球补算](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/MoonCalc.kt#L18-L33)
- **遥测与更长预报：** AUTO 的露点、云量、阵风、缺失能见度，以及缺失日/小时内容可由 Open-Meteo 补充。[实况补充](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L91-L117)、[预报补充](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L599-L627)
- **历史天气：** Open-Meteo archive；近七天通过其 forecast 的 past_days。[历史接口](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/HistoricalWeatherRepository.kt#L39-L57)、[近期接口](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/HistoricalWeatherRepository.kt#L92-L108)
- **雷达：** RainViewer 与彩云端点。[RainViewer](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/RadarRepository.kt#L24-L28)、[彩云](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/CaiyunRadarRepository.kt#L33-L41)
- **台风轨迹、风圈、多机构预报：** 浙江省水利厅 TyphoonList、TyphoonInfo；小米仅首页辅助摘要。[台风路径源](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/TyphoonRepository.kt#L88-L129)

## 实时取样

2026-09-10 22:45 左右（Asia/Hong_Kong），从本仓库客户端提取原请求参数，用系统 curl 发起 HTTPS 请求，取北京、广州各一次 weather/all；未运行 aiohttp 客户端。原始文件在 `/tmp/xiaomi-weather-audit-xaovq2ov/beijing.json` 与 `guangzhou.json`；它们是临时审计证据，不属于稳定测试 fixture。本报告记录结构与关键结果，不依赖临时文件永久存在。

- 两地六项污染物、昨日、六项 indices 均有返回。北京 AQI=24、PM2.5=12、PM10=24、O₃=66、NO₂=17、SO₂=2、CO=0.3；AQI pubTime 为 22:00。
- 两地日 AQI 15 点、小时 AQI 23 点；日降水概率全 0。
- 两地分钟 value 为 120 个 0，precipitation.probability 为 4 个 0；两层 status=0，有有效 pubTime，但 isShow=false。北京分钟 pubTime 为 22:45:59。
- 两地 visibility 空、moonPhase=null、alerts=[]、typhoon=[]。
- 昨日还返回 sunRise、sunSet、windDircStart/End、windSpeedStart/End，这些不在上游 XiaomiYesterday DTO 中。

这些样本证明当前响应中有可消费数据，不能证明预警、台风、分钟降雨强度及不同城市提供商在所有条件下都可靠。

原始样本 SHA-256：

- beijing.json：`73d7a85de9f73359dc217cdec313179ad1188ecec9e6f06fe85b58d95f3a6781`
- guangzhou.json：`d7a16a9ef4d5961aab5126f2940906cf8870915e17b71844bd44b2ef95b085d9`

## 建议实施顺序

**P1：优先补已有数据、接入成本较低的字段。** 四项遗漏污染物及健康建议；日降水概率/日风、小时风；保留昼夜天气、暴露日出日落。实现时校验状态、缺省值、单位和时间轴。预警价值高，应同时找非空有效样本，确认等级、时间与区域后接入。

Home Assistant 的 forecast 已支持 `native_wind_speed`、`wind_bearing` 与百分比 `precipitation_probability`；`twice_daily` 必须提供 `is_daytime`，不能直接把 from/to 原样塞入。参见[官方 Weather entity 文档](https://developers.home-assistant.io/docs/core/entity/weather/#forecast-data)。污染物单位也须分清：上游中国口径把 CO 定为 mg/m³，其余五项定为 μg/m³，接入时应核验并正确声明，不能统一套用同一单位。[上游单位表](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L30-L37)

同时可保留各数据块的观测/发布时间，改善新鲜度判断。本仓库 current.pubTime 只参与晴夜判断，aqi.pubTime、updateTime 未暴露；上游明确优先使用源观测时间，避免把下载时间当成天气更新时间。参见[上游更新时间映射](https://github.com/zhishengplus/ZhishengWeather/blob/bd2dd39c467ce886c7819ee364752ed12b2bbcc2/app/src/main/kotlin/com/zhisheng/weather/data/WeatherRepository.kt#L1097-L1101)。

**P2：补有产品价值的扩展。** 昨日天气、洗车/运动指数、日小时 AQI 曲线；分钟文案可先研究接入，强度序列须先核验 isShow、非零数据单位及发布时间。HA 的实体/属性组织需单独设计，避免把每个字段无差别做成常驻实体。

**待证据再做：** 台风摘要的非空格式、分钟概率四点的时间语义、更多地区的真实能见度和月相。不要为了追平对方界面引入其他天气源，那是另一项产品决策。

本次仅完成审计，未修改产品代码。
