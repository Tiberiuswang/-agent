# 🧊 冷链优化智能体（智谱 GLM-5.3-Flash + Streamlit）

## 功能
| 页面 | 能力 |
|---|---|
| 🚚 路线优化 | 多车、载重、时间窗；开门升温+保质期损耗纳入成本；路线图/温度曲线/成本对比 |
| 🌡️ 温度监控 | 拖动时间轴回放；越限、临界预警、趋势预测、开门过久、累计超温；放行/暂扣建议；支持上传 CSV |
| 🧊 库存效期 | 冷库 FEFO 出库分配；缺货、临期、过期提醒 |
| 📈 需求补货 | 趋势预测、安全库存、再订货点、货架期约束 |
| ✈️ 运输方式 | 卡车/铁路/航空：时效与总成本（运费+品质损耗） |
| 🤖 智能体 | 自然语言调用以上全部工具（GLM 函数调用），可附带当前方案 |

## 本地运行
    pip install -r requirements.txt
    streamlit run app.py
命令行版智能体：`ZHIPU_API_KEY=xxx python agent.py`

## 免费上线（Streamlit Community Cloud）
1. 把本目录推到 GitHub 公开仓库（`.gitignore` 已排除密钥）
2. 打开 share.streamlit.io → New app → 选仓库，Main file 填 `app.py`
3. Advanced settings → Secrets 粘贴：`ZHIPU_API_KEY = "你的密钥"`
4. Deploy，得到公开网址

## 接入真实数据
改 `tools.py`：`PRODUCTS`（货品温区/Q10/保质期）、成本系数（`_simulate` 里的 4.5元/km、8元/h、2元/分钟迟到罚金）、
`_km`（可换成高德/百度路径 API）；温度数据可替换为 IoT 平台接口。

## 注意
模型编码默认 `glm-5.3-flash`，以智谱控制台为准；所有物理/成本参数为示意值；疫苗药品的处置须遵守 GSP 与厂家规定。
