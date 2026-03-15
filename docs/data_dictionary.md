# 数据字典设计

## 1. 文档目的
本文件用于定义企业网络恶意行为识别与封禁系统的基础数据规范，作为后续日志清洗、实体抽取、Neo4j 导入、后端接口和前端展示的统一数据标准。

本数据字典分为三层：
1. 原始日志标准字段层：描述不同日志来源在标准化前后的公共字段。
2. 图谱节点字段层：描述写入 Neo4j 的节点属性。
3. 图谱关系字段层：描述写入 Neo4j 的边关系及其关联键。

通过该设计，可以保证后续脚本、数据库和接口使用同一套字段语义，降低字段漂移和重复清洗的成本。

## 2. 设计原则
1. 字段命名统一采用英文小写加下划线，方便脚本处理和数据库导入。
2. 字段说明统一使用中文，便于论文撰写、团队沟通和答辩展示。
3. 所有主键字段采用前缀编码，便于快速识别实体类型。
4. 时间字段统一采用 ISO 8601 格式，建议保留时区信息。
5. 枚举字段统一使用大写英文值，减少多源日志合并时的歧义。

## 3. 主键编码规则

| 实体类型 | 主键字段 | 编码示例 | 说明 |
| --- | --- | --- | --- |
| 用户 | `user_id` | `U001` | 用户唯一编号 |
| 主机 | `host_id` | `H001` | 资产唯一编号 |
| IP | `ip_id` | `IP001` | IP 实体唯一编号 |
| 会话 | `session_id` | `S001` | 一次访问或登录会话编号 |
| 事件 | `event_id` | `E001` | 日志抽取后的安全事件编号 |
| 规则 | `rule_id` | `R001` | 检测规则编号 |
| 告警 | `alert_id` | `A001` | 告警编号 |
| 封禁动作 | `action_id` | `BA001` | 封禁或处置动作编号 |

## 4. 原始日志标准字段
原始日志来源可能包括 AD 认证日志、VPN 日志、主机日志、EDR 日志和防火墙日志。为便于统一处理，建议先映射到以下公共字段。

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `raw_log_id` | string | 是 | `RAW202603150001` | 原始日志唯一编号 |
| `log_source` | string | 是 | `VPN` | 日志来源系统 |
| `log_type` | string | 是 | `AUTH` | 日志类别 |
| `event_time` | string | 是 | `2026-03-15T09:10:10+08:00` | 事件发生时间 |
| `src_ip` | string | 否 | `183.62.211.45` | 源 IP 地址 |
| `dst_ip` | string | 否 | `10.10.1.10` | 目标 IP 地址 |
| `src_port` | integer | 否 | `49152` | 源端口 |
| `dst_port` | integer | 否 | `3389` | 目标端口 |
| `username` | string | 否 | `lisi` | 关联用户名 |
| `hostname` | string | 否 | `WIN10-001` | 关联主机名 |
| `protocol` | string | 否 | `RDP` | 使用的访问协议 |
| `action` | string | 否 | `LOGIN` | 操作动作 |
| `result` | string | 否 | `FAILED` | 操作结果 |
| `message` | string | 否 | `连续失败登录` | 原始日志摘要 |
| `bytes_in` | integer | 否 | `1024` | 入站流量 |
| `bytes_out` | integer | 否 | `2048` | 出站流量 |

## 5. 数据标准化规则
1. 时间统一转换为 `yyyy-MM-ddTHH:mm:ss+08:00` 格式。
2. 用户名、主机名、IP 地址在清洗阶段应去除首尾空格并统一大小写策略。
3. 枚举字段建议采用以下格式：
   - 登录结果：`SUCCESS` / `FAILURE`
   - 事件等级：`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`
   - 资产状态：`ONLINE` / `OFFLINE` / `ISOLATED`
   - 告警状态：`NEW` / `CONFIRMED` / `BLOCKED` / `RESOLVED`
4. 布尔字段统一使用 `true` / `false`。
5. 风险分值建议统一使用 `0-100` 的数值区间，便于后续评分模型扩展。

## 6. 处理后 CSV 文件总览

| 文件名 | 类型 | 对应标签/关系 | 主键或关联键 | 用途说明 |
| --- | --- | --- | --- | --- |
| `users.csv` | 节点 | `User` | `user_id` | 存储用户基础信息 |
| `hosts.csv` | 节点 | `Host` | `host_id` | 存储主机或资产信息 |
| `ips.csv` | 节点 | `IP` | `ip_id` | 存储 IP 实体信息 |
| `sessions.csv` | 节点 | `Session` | `session_id` | 存储登录或访问会话 |
| `events.csv` | 节点 | `Event` | `event_id` | 存储抽取出的安全事件 |
| `rules.csv` | 节点 | `Rule` | `rule_id` | 存储检测规则 |
| `alerts.csv` | 节点 | `Alert` | `alert_id` | 存储告警结果 |
| `block_actions.csv` | 节点 | `BlockAction` | `action_id` | 存储封禁或处置动作 |
| `rel_user_initiates_session.csv` | 关系 | `INITIATES` | `user_id + session_id` | 用户发起会话 |
| `rel_session_uses_source_ip.csv` | 关系 | `USES_SOURCE_IP` | `session_id + ip_id` | 会话源地址 |
| `rel_session_accesses_host.csv` | 关系 | `ACCESSES` | `session_id + host_id` | 会话访问目标主机 |
| `rel_session_generates_event.csv` | 关系 | `GENERATES` | `session_id + event_id` | 会话产生安全事件 |
| `rel_event_triggers_alert.csv` | 关系 | `TRIGGERS` | `event_id + alert_id` | 事件触发告警 |
| `rel_alert_hit_rule.csv` | 关系 | `HIT_RULE` | `alert_id + rule_id` | 告警命中规则 |
| `rel_block_disposes_alert.csv` | 关系 | `DISPOSES` | `action_id + alert_id` | 处置动作对应告警 |
| `rel_block_targets_ip.csv` | 关系 | `TARGETS_IP` | `action_id + ip_id` | 封禁动作指向目标 IP |

## 7. 节点字段定义

### 7.1 `users.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `user_id` | string | 是 | `U001` | 用户唯一编号 |
| `username` | string | 是 | `zhangsan` | 登录用户名 |
| `display_name` | string | 否 | `张三` | 用户显示名称 |
| `department` | string | 否 | `运维部` | 所属部门 |
| `role` | string | 否 | `运维工程师` | 岗位角色 |
| `privilege_level` | integer | 否 | `4` | 权限等级，数值越大权限越高 |
| `status` | string | 否 | `ACTIVE` | 用户状态 |
| `is_whitelisted` | boolean | 否 | `false` | 是否白名单账号 |
| `risk_score` | float | 否 | `88` | 当前风险分值 |
| `created_at` | string | 否 | `2026-03-01T09:00:00+08:00` | 建档时间 |

### 7.2 `hosts.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `host_id` | string | 是 | `H001` | 主机唯一编号 |
| `hostname` | string | 是 | `WIN10-001` | 主机名称 |
| `asset_type` | string | 否 | `WORKSTATION` | 资产类型 |
| `os_name` | string | 否 | `Windows 10` | 操作系统名称 |
| `critical_level` | integer | 否 | `2` | 资产重要等级 |
| `owner_department` | string | 否 | `办公网络` | 归属部门或业务域 |
| `status` | string | 否 | `ONLINE` | 资产在线状态 |
| `risk_score` | float | 否 | `25` | 资产风险分值 |
| `created_at` | string | 否 | `2026-03-01T09:00:00+08:00` | 建档时间 |

### 7.3 `ips.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `ip_id` | string | 是 | `IP001` | IP 唯一编号 |
| `ip_address` | string | 是 | `10.10.1.23` | IP 地址文本 |
| `ip_type` | string | 否 | `INTERNAL` | IP 类型，内网或外网 |
| `geo_location` | string | 否 | `华东办公区` | 地理位置或网络区域 |
| `reputation_level` | string | 否 | `LOW` | 威胁信誉等级 |
| `is_blocked` | boolean | 否 | `false` | 是否已封禁 |
| `risk_score` | float | 否 | `15` | IP 风险分值 |
| `created_at` | string | 否 | `2026-03-01T09:00:00+08:00` | 建档时间 |

### 7.4 `sessions.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | `S001` | 会话唯一编号 |
| `protocol` | string | 否 | `SSH` | 访问协议 |
| `login_result` | string | 否 | `SUCCESS` | 登录结果 |
| `start_time` | string | 否 | `2026-03-15T10:05:00+08:00` | 会话开始时间 |
| `end_time` | string | 否 | `2026-03-15T10:06:30+08:00` | 会话结束时间 |
| `duration_seconds` | integer | 否 | `90` | 会话持续时间 |
| `auth_method` | string | 否 | `PASSWORD` | 认证方式 |
| `src_port` | integer | 否 | `55124` | 源端口 |
| `dst_port` | integer | 否 | `22` | 目标端口 |
| `risk_score` | float | 否 | `78` | 会话风险分值 |

### 7.5 `events.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `event_id` | string | 是 | `E001` | 事件唯一编号 |
| `event_type` | string | 是 | `LOGIN_FAIL` | 事件类型 |
| `event_level` | string | 否 | `HIGH` | 事件等级 |
| `event_time` | string | 否 | `2026-03-15T09:10:10+08:00` | 事件发生时间 |
| `action` | string | 否 | `LOGIN` | 事件动作 |
| `result` | string | 否 | `FAILED` | 事件结果 |
| `log_source` | string | 否 | `VPN` | 来源系统 |
| `raw_log_id` | string | 否 | `RAW202603150001` | 映射到的原始日志编号 |
| `confidence` | float | 否 | `0.91` | 检测置信度 |
| `risk_score` | float | 否 | `82` | 事件风险分值 |
| `detail` | string | 否 | `外部地址对办公终端发起连续失败登录` | 事件细节说明 |

### 7.6 `rules.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `rule_id` | string | 是 | `R001` | 规则唯一编号 |
| `rule_name` | string | 是 | `连续失败登录阈值规则` | 规则名称 |
| `rule_category` | string | 否 | `THRESHOLD` | 规则类别 |
| `rule_level` | string | 否 | `HIGH` | 规则风险等级 |
| `threshold_desc` | string | 否 | `5分钟失败登录次数>=5` | 规则阈值描述 |
| `description` | string | 否 | `检测外部来源对单主机的暴力破解行为` | 规则详细说明 |
| `enabled` | boolean | 否 | `true` | 规则是否启用 |

### 7.7 `alerts.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `alert_id` | string | 是 | `A001` | 告警唯一编号 |
| `alert_name` | string | 是 | `暴力破解告警` | 告警名称 |
| `severity` | string | 否 | `HIGH` | 告警严重等级 |
| `score` | float | 否 | `82` | 告警得分 |
| `status` | string | 否 | `BLOCKED` | 告警状态 |
| `first_seen` | string | 否 | `2026-03-15T09:10:11+08:00` | 首次发现时间 |
| `last_seen` | string | 否 | `2026-03-15T09:12:00+08:00` | 最近更新时间 |
| `description` | string | 否 | `检测到外部地址连续失败登录` | 告警说明 |
| `suggestion` | string | 否 | `建议立即封禁源 IP 并复核账号状态` | 处置建议 |

### 7.8 `block_actions.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `action_id` | string | 是 | `BA001` | 处置动作唯一编号 |
| `action_type` | string | 否 | `BLOCK_IP` | 动作类型 |
| `target_type` | string | 否 | `IP` | 目标对象类型 |
| `status` | string | 否 | `SUCCESS` | 动作执行状态 |
| `executed_at` | string | 否 | `2026-03-15T09:12:00+08:00` | 执行时间 |
| `executor` | string | 否 | `auto_engine` | 执行人或执行模块 |
| `ticket_no` | string | 否 | `T20260315001` | 工单或处置编号 |
| `rollback_supported` | boolean | 否 | `true` | 是否支持回滚 |
| `remark` | string | 否 | `自动封禁外部恶意地址` | 备注说明 |

## 8. 关系字段定义

### 8.1 `rel_user_initiates_session.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `user_id` | string | 是 | `U001` | 起始用户编号 |
| `session_id` | string | 是 | `S001` | 目标会话编号 |
| `relation_time` | string | 否 | `2026-03-15T10:05:00+08:00` | 关系建立时间 |

### 8.2 `rel_session_uses_source_ip.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | `S001` | 会话编号 |
| `ip_id` | string | 是 | `IP002` | 源 IP 编号 |
| `relation_time` | string | 否 | `2026-03-15T10:05:00+08:00` | 关系建立时间 |

### 8.3 `rel_session_accesses_host.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | `S001` | 会话编号 |
| `host_id` | string | 是 | `H002` | 访问目标主机编号 |
| `relation_time` | string | 否 | `2026-03-15T10:05:02+08:00` | 访问关系建立时间 |

### 8.4 `rel_session_generates_event.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | `S001` | 会话编号 |
| `event_id` | string | 是 | `E003` | 关联事件编号 |
| `relation_time` | string | 否 | `2026-03-15T10:06:20+08:00` | 事件写入时间 |

### 8.5 `rel_event_triggers_alert.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `event_id` | string | 是 | `E001` | 事件编号 |
| `alert_id` | string | 是 | `A001` | 告警编号 |
| `relation_time` | string | 否 | `2026-03-15T09:10:11+08:00` | 触发时间 |

### 8.6 `rel_alert_hit_rule.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `alert_id` | string | 是 | `A001` | 告警编号 |
| `rule_id` | string | 是 | `R001` | 命中规则编号 |
| `relation_time` | string | 否 | `2026-03-15T09:10:11+08:00` | 命中时间 |

### 8.7 `rel_block_disposes_alert.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `action_id` | string | 是 | `BA001` | 处置动作编号 |
| `alert_id` | string | 是 | `A001` | 对应告警编号 |
| `relation_time` | string | 否 | `2026-03-15T09:12:00+08:00` | 处置时间 |

### 8.8 `rel_block_targets_ip.csv`

| 字段名 | 类型 | 必填 | 示例 | 中文说明 |
| --- | --- | --- | --- | --- |
| `action_id` | string | 是 | `BA001` | 处置动作编号 |
| `ip_id` | string | 是 | `IP003` | 目标 IP 编号 |
| `relation_time` | string | 否 | `2026-03-15T09:12:00+08:00` | 封禁生效时间 |

## 9. 数据字典与图谱映射关系
为了保证论文中的“概念模型”和工程中的“落地模型”一致，可将映射关系概括为：

1. 用户、主机、IP 对应图谱中的基础实体。
2. 会话对应连接行为上下文，是多源日志归并的关键中间对象。
3. 事件用于承载原始日志经过规则或逻辑抽取后的安全语义。
4. 告警用于承载检测输出结果。
5. 封禁动作用于承载联动处置与回滚追踪。

## 10. 论文写作可用描述
可以在论文中将本节描述为：

“系统采用统一数据字典实现多源安全日志的标准化表达。通过定义用户、主机、IP、会话、事件、规则、告警和封禁动作等核心对象，并为各对象设置唯一主键、风险分值、状态字段和时间字段，保证了安全数据在清洗、入库、检测、展示和审计各阶段的一致性与可追溯性。”
