////////////////////////////////////////////////////////////////////////
// 文件路径：neo4j/init_schema.cypher
// 作用说明：初始化第一阶段图谱建模所需的 Neo4j 约束与索引
// 兼容建议：推荐使用 Neo4j 5.x，当前脚本采用 Community 版可用语法
////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////
// 一、唯一约束
// 说明：
// 1. 每类核心节点均使用业务主键字段作为唯一约束。
// 2. 这样可以避免重复导入，也方便后续使用 MERGE 写入。
////////////////////////////////////////////////////////////////////////

CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (n:User)
REQUIRE n.user_id IS UNIQUE;

CREATE CONSTRAINT host_id_unique IF NOT EXISTS
FOR (n:Host)
REQUIRE n.host_id IS UNIQUE;

CREATE CONSTRAINT ip_id_unique IF NOT EXISTS
FOR (n:IP)
REQUIRE n.ip_id IS UNIQUE;

CREATE CONSTRAINT session_id_unique IF NOT EXISTS
FOR (n:Session)
REQUIRE n.session_id IS UNIQUE;

CREATE CONSTRAINT event_id_unique IF NOT EXISTS
FOR (n:Event)
REQUIRE n.event_id IS UNIQUE;

CREATE CONSTRAINT rule_id_unique IF NOT EXISTS
FOR (n:Rule)
REQUIRE n.rule_id IS UNIQUE;

CREATE CONSTRAINT alert_id_unique IF NOT EXISTS
FOR (n:Alert)
REQUIRE n.alert_id IS UNIQUE;

CREATE CONSTRAINT block_action_id_unique IF NOT EXISTS
FOR (n:BlockAction)
REQUIRE n.action_id IS UNIQUE;

////////////////////////////////////////////////////////////////////////
// 二、范围索引
// 说明：
// 1. 范围索引用于提升常用过滤字段和排序字段的查询性能。
// 2. 当前以第一阶段的数据导入和基础查询验证为目标，不做过度设计。
////////////////////////////////////////////////////////////////////////

// User 节点常用查询字段索引
CREATE RANGE INDEX user_username_idx IF NOT EXISTS
FOR (n:User)
ON (n.username);

CREATE RANGE INDEX user_department_idx IF NOT EXISTS
FOR (n:User)
ON (n.department);

// Host 节点常用查询字段索引
CREATE RANGE INDEX host_hostname_idx IF NOT EXISTS
FOR (n:Host)
ON (n.hostname);

CREATE RANGE INDEX host_asset_type_idx IF NOT EXISTS
FOR (n:Host)
ON (n.asset_type);

CREATE RANGE INDEX host_critical_level_idx IF NOT EXISTS
FOR (n:Host)
ON (n.critical_level);

// IP 节点常用查询字段索引
CREATE RANGE INDEX ip_address_idx IF NOT EXISTS
FOR (n:IP)
ON (n.ip_address);

CREATE RANGE INDEX ip_blocked_idx IF NOT EXISTS
FOR (n:IP)
ON (n.is_blocked);

// Session 节点常用查询字段索引
CREATE RANGE INDEX session_start_time_idx IF NOT EXISTS
FOR (n:Session)
ON (n.start_time);

CREATE RANGE INDEX session_login_result_idx IF NOT EXISTS
FOR (n:Session)
ON (n.login_result);

// Event 节点常用查询字段索引
CREATE RANGE INDEX event_type_idx IF NOT EXISTS
FOR (n:Event)
ON (n.event_type);

CREATE RANGE INDEX event_time_idx IF NOT EXISTS
FOR (n:Event)
ON (n.event_time);

CREATE RANGE INDEX event_level_idx IF NOT EXISTS
FOR (n:Event)
ON (n.event_level);

// Alert 节点常用查询字段索引
CREATE RANGE INDEX alert_status_idx IF NOT EXISTS
FOR (n:Alert)
ON (n.status);

CREATE RANGE INDEX alert_severity_idx IF NOT EXISTS
FOR (n:Alert)
ON (n.severity);

CREATE RANGE INDEX alert_score_idx IF NOT EXISTS
FOR (n:Alert)
ON (n.score);

// Rule 节点常用查询字段索引
CREATE RANGE INDEX rule_category_idx IF NOT EXISTS
FOR (n:Rule)
ON (n.rule_category);

CREATE RANGE INDEX rule_level_idx IF NOT EXISTS
FOR (n:Rule)
ON (n.rule_level);

// BlockAction 节点常用查询字段索引
CREATE RANGE INDEX block_status_idx IF NOT EXISTS
FOR (n:BlockAction)
ON (n.status);

CREATE RANGE INDEX block_executed_at_idx IF NOT EXISTS
FOR (n:BlockAction)
ON (n.executed_at);

////////////////////////////////////////////////////////////////////////
// 三、执行后验证语句
// 说明：
// 1. 以下语句默认作为注释保留，执行 schema 后可手动运行。
// 2. 用于确认约束和索引已经生效。
////////////////////////////////////////////////////////////////////////

// SHOW CONSTRAINTS;
// SHOW INDEXES;

////////////////////////////////////////////////////////////////////////
// 四、后续导入提醒
// 说明：
// 1. 当前 schema 与 data/processed/ 下的示例 CSV 对齐。
// 2. 第二阶段编写导入脚本时，建议统一使用 MERGE 导入节点和关系。
// 3. 如果使用 LOAD CSV，需要注意文件位于 Neo4j import 目录或已开放访问。
////////////////////////////////////////////////////////////////////////
