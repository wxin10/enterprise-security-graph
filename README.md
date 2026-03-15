# 基于 Neo4j 的企业网络恶意行为识别与封禁系统

## 1. 项目简介
本项目是一个面向企业网络安全场景的毕业设计系统，目标是利用 Neo4j 构建企业安全行为图谱，将原始日志中的用户、主机、IP、会话、事件、告警和封禁动作关联起来，形成“可查询、可追踪、可告警、可处置”的安全分析闭环。

系统最终将围绕以下核心能力展开：
1. 构建企业网络安全行为图谱。
2. 基于日志识别异常登录、横向移动、暴力破解、高频访问等恶意行为。
3. 提供风险评分、告警展示、攻击关系追踪和可视化分析能力。
4. 提供自动封禁、人工复核、审计留痕和后续回滚能力。
5. 为毕业论文撰写和答辩演示提供完整的工程化材料。

当前仓库处于第一阶段“需求与建模”，本轮只完成建模相关文档、Neo4j Schema 与示例数据设计，暂不实现前端和后端业务代码。

## 2. 技术栈
- 后端：Python + Flask
- 前端：Vue3 + Element Plus + ECharts
- 图数据库：Neo4j
- 数据处理：Python
- 数据交换格式：CSV / JSON
- 接口风格：RESTful API

## 3. 第一阶段交付内容
第一阶段聚焦“系统需求梳理 + 图谱模型落地 + 数据文件设计”，本次交付包含以下内容：

1. 完善项目总说明文档 `README.md`。
2. 生成数据字典文档 `docs/data_dictionary.md`。
3. 生成图模型设计文档 `docs/graph_model.md`。
4. 生成 Neo4j 初始化脚本 `neo4j/init_schema.cypher`。
5. 生成 `data/processed/` 下的示例 CSV 文件，作为第二阶段数据清洗与入库的输入模板。

## 4. 系统总体思路
本系统采用“日志标准化 -> 图谱建模 -> 恶意行为识别 -> 告警联动 -> 封禁审计”的分层思路。

### 4.1 数据流转路径
1. 从认证日志、VPN 日志、主机日志、防火墙日志等来源采集原始日志。
2. 对日志进行清洗、补全、标准化，统一时间格式、字段命名和主键编码。
3. 将标准化结果拆分为节点 CSV 和关系 CSV。
4. 导入 Neo4j，形成企业网络安全行为图谱。
5. 在图谱上执行规则匹配、阈值检测、路径追踪和风险评分。
6. 将告警结果和封禁动作再次写回图数据库，支持追溯与展示。

### 4.2 第一阶段图谱核心对象
本阶段先定义最小可用图谱模型，后续功能均在该模型上扩展：

| 类型 | 标签 | 说明 |
| --- | --- | --- |
| 节点 | `User` | 企业用户、运维账号、普通员工账号 |
| 节点 | `Host` | 服务器、终端、数据库等资产 |
| 节点 | `IP` | 内网地址、外网地址、VPN 地址 |
| 节点 | `Session` | 一次登录或访问会话 |
| 节点 | `Event` | 由日志抽取出的安全事件 |
| 节点 | `Rule` | 检测规则或策略规则 |
| 节点 | `Alert` | 告警结果 |
| 节点 | `BlockAction` | 封禁或处置动作 |

## 5. 目录结构说明
当前工程目录按照毕业设计项目进行标准化组织：

```text
enterprise-security-graph/
├─ backend/                # 后端 Flask 代码（后续阶段实现）
├─ data/
│  ├─ raw/                 # 原始日志样例
│  └─ processed/           # 清洗后的节点/关系 CSV（本阶段已设计）
├─ deploy/                 # 启动说明与部署文件
├─ docs/                   # 系统设计、任务计划、接口文档、测试文档
├─ frontend/               # 前端 Vue3 代码（后续阶段实现）
├─ neo4j/                  # Schema、导入和查询相关 Cypher
├─ scripts/                # 清洗、抽取、导入、识别、封禁脚本
├─ tests/                  # 测试脚本与测试说明
├─ AGENTS.md               # 协作约束与开发规范
└─ README.md               # 项目总说明
```

说明：
1. 后续标准化目录以 `data/processed/` 为准。
2. 若仓库中历史上存在 `data/raw/processed/` 之类的嵌套目录，应视为临时目录，不作为正式导入路径。

## 6. 本阶段示例数据设计
为便于第二阶段直接编写导入脚本，本阶段在 `data/processed/` 下提供了“节点文件 + 关系文件”两类示例 CSV。

### 6.1 节点 CSV
- `users.csv`
- `hosts.csv`
- `ips.csv`
- `sessions.csv`
- `events.csv`
- `rules.csv`
- `alerts.csv`
- `block_actions.csv`

### 6.2 关系 CSV
- `rel_user_initiates_session.csv`
- `rel_session_uses_source_ip.csv`
- `rel_session_accesses_host.csv`
- `rel_session_generates_event.csv`
- `rel_event_triggers_alert.csv`
- `rel_alert_hit_rule.csv`
- `rel_block_disposes_alert.csv`
- `rel_block_targets_ip.csv`

这些 CSV 已与数据字典和图模型文档保持一致，后续只需根据相同表头编写清洗与导入脚本即可。

## 7. 建模与论文可写点
本项目的建模设计具有以下论文表达价值：
1. 将分散的原始日志抽象为“实体 + 行为 + 告警 + 处置”的图结构，增强安全事件之间的关联表达能力。
2. 引入 `Session` 节点承载访问上下文，便于描述“谁从哪个 IP 在什么时间访问了哪台主机”。
3. 引入 `Event -> Alert -> BlockAction` 链路，使检测、告警和处置过程天然可追溯。
4. 通过节点属性中的 `risk_score`、`severity`、`critical_level` 等字段，为后续风险评分模型提供结构化输入。

## 8. 兼容性与实现提醒
为保证后续阶段顺利推进，当前阶段先给出以下工程提醒：

1. 推荐使用 Neo4j 5.x。
   当前 `neo4j/init_schema.cypher` 使用 `IF NOT EXISTS` 语法，适配 Neo4j 5.x 更稳妥。
2. 建议优先兼容 Neo4j Community Edition。
   因此当前 Schema 采用“唯一约束 + 范围索引”的保守设计，不依赖企业版特性。
3. CSV 文件应统一采用 UTF-8 编码。
   这样可以避免中文说明、中文规则名称和告警描述导入时出现乱码。
4. 后续若使用 `LOAD CSV` 导入 Neo4j，需要将示例文件放入 Neo4j 的 `import` 目录，或在配置中开启对应目录访问权限。
5. 后端阶段连接 Neo4j 时，需要注意驱动版本与数据库版本匹配，推荐后续统一采用官方 Python 驱动 `neo4j`。
6. 前后端联调阶段需要处理跨域问题，但本阶段尚不涉及接口实现。

## 9. 第一阶段完成判定
当以下内容全部满足时，可以认为“需求与建模阶段”已完成：

1. `README.md` 已完整说明项目目标、阶段范围、目录结构和验证方法。
2. `docs/data_dictionary.md` 已定义原始日志标准字段、节点字段和关系字段。
3. `docs/graph_model.md` 已明确 Neo4j 节点、关系、建模原则和典型攻击链。
4. `neo4j/init_schema.cypher` 可以在 Neo4j 中成功执行，并生成约束和索引。
5. `data/processed/` 下的示例 CSV 能够和建模文档一一对应，不存在字段名冲突。

## 10. 后续开发路线
接下来的推荐顺序如下：

1. 生成 `data/raw/` 原始日志样例。
2. 编写日志清洗与实体抽取脚本。
3. 编写 Neo4j 导入脚本并完成基础查询验证。
4. 再进入恶意行为识别、后端接口和前端页面实现阶段。

## 11. 当前阶段快速验证命令
如果本机已安装 Neo4j，可按以下思路快速验证：

```bash
# 方式一：使用 cypher-shell 执行
cypher-shell -f neo4j/init_schema.cypher
```

```cypher
// 方式二：将 neo4j/init_schema.cypher 内容复制到 Neo4j Browser 后执行
SHOW CONSTRAINTS;
SHOW INDEXES;
```

同时检查 `data/processed/` 中的 CSV 文件是否存在，并确认其表头与 `docs/data_dictionary.md` 中的定义一致。
