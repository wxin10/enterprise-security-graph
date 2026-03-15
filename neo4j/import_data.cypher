////////////////////////////////////////////////////////////////////////
// 文件路径：neo4j/import_data.cypher
// 作用说明：使用 LOAD CSV 手工导入 data/processed/ 下的节点和关系数据
//
// 使用前提：
// 1. 先执行 neo4j/init_schema.cypher。
// 2. 将 data/processed/ 下的最终节点/关系 CSV 复制到 Neo4j 的 import 目录。
// 3. 当前脚本默认按 file:///文件名 的方式读取，因此文件需要位于 import 根目录。
////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////
// 一、导入节点
////////////////////////////////////////////////////////////////////////

LOAD CSV WITH HEADERS FROM 'file:///users.csv' AS row
MERGE (n:User {user_id: row.user_id})
SET n.username = row.username,
    n.display_name = CASE row.display_name WHEN '' THEN null ELSE row.display_name END,
    n.department = CASE row.department WHEN '' THEN null ELSE row.department END,
    n.role = CASE row.role WHEN '' THEN null ELSE row.role END,
    n.privilege_level = CASE row.privilege_level WHEN '' THEN null ELSE toInteger(row.privilege_level) END,
    n.status = CASE row.status WHEN '' THEN null ELSE row.status END,
    n.is_whitelisted = CASE row.is_whitelisted WHEN '' THEN null ELSE toBoolean(row.is_whitelisted) END,
    n.risk_score = CASE row.risk_score WHEN '' THEN null ELSE toFloat(row.risk_score) END,
    n.created_at = CASE row.created_at WHEN '' THEN null ELSE row.created_at END;

LOAD CSV WITH HEADERS FROM 'file:///hosts.csv' AS row
MERGE (n:Host {host_id: row.host_id})
SET n.hostname = row.hostname,
    n.asset_type = CASE row.asset_type WHEN '' THEN null ELSE row.asset_type END,
    n.os_name = CASE row.os_name WHEN '' THEN null ELSE row.os_name END,
    n.critical_level = CASE row.critical_level WHEN '' THEN null ELSE toInteger(row.critical_level) END,
    n.owner_department = CASE row.owner_department WHEN '' THEN null ELSE row.owner_department END,
    n.status = CASE row.status WHEN '' THEN null ELSE row.status END,
    n.risk_score = CASE row.risk_score WHEN '' THEN null ELSE toFloat(row.risk_score) END,
    n.created_at = CASE row.created_at WHEN '' THEN null ELSE row.created_at END;

LOAD CSV WITH HEADERS FROM 'file:///ips.csv' AS row
MERGE (n:IP {ip_id: row.ip_id})
SET n.ip_address = row.ip_address,
    n.ip_type = CASE row.ip_type WHEN '' THEN null ELSE row.ip_type END,
    n.geo_location = CASE row.geo_location WHEN '' THEN null ELSE row.geo_location END,
    n.reputation_level = CASE row.reputation_level WHEN '' THEN null ELSE row.reputation_level END,
    n.is_blocked = CASE row.is_blocked WHEN '' THEN null ELSE toBoolean(row.is_blocked) END,
    n.risk_score = CASE row.risk_score WHEN '' THEN null ELSE toFloat(row.risk_score) END,
    n.created_at = CASE row.created_at WHEN '' THEN null ELSE row.created_at END;

LOAD CSV WITH HEADERS FROM 'file:///sessions.csv' AS row
MERGE (n:Session {session_id: row.session_id})
SET n.protocol = CASE row.protocol WHEN '' THEN null ELSE row.protocol END,
    n.login_result = CASE row.login_result WHEN '' THEN null ELSE row.login_result END,
    n.start_time = CASE row.start_time WHEN '' THEN null ELSE row.start_time END,
    n.end_time = CASE row.end_time WHEN '' THEN null ELSE row.end_time END,
    n.duration_seconds = CASE row.duration_seconds WHEN '' THEN null ELSE toInteger(row.duration_seconds) END,
    n.auth_method = CASE row.auth_method WHEN '' THEN null ELSE row.auth_method END,
    n.src_port = CASE row.src_port WHEN '' THEN null ELSE toInteger(row.src_port) END,
    n.dst_port = CASE row.dst_port WHEN '' THEN null ELSE toInteger(row.dst_port) END,
    n.risk_score = CASE row.risk_score WHEN '' THEN null ELSE toFloat(row.risk_score) END;

LOAD CSV WITH HEADERS FROM 'file:///events.csv' AS row
MERGE (n:Event {event_id: row.event_id})
SET n.event_type = row.event_type,
    n.event_level = CASE row.event_level WHEN '' THEN null ELSE row.event_level END,
    n.event_time = CASE row.event_time WHEN '' THEN null ELSE row.event_time END,
    n.action = CASE row.action WHEN '' THEN null ELSE row.action END,
    n.result = CASE row.result WHEN '' THEN null ELSE row.result END,
    n.log_source = CASE row.log_source WHEN '' THEN null ELSE row.log_source END,
    n.raw_log_id = CASE row.raw_log_id WHEN '' THEN null ELSE row.raw_log_id END,
    n.confidence = CASE row.confidence WHEN '' THEN null ELSE toFloat(row.confidence) END,
    n.risk_score = CASE row.risk_score WHEN '' THEN null ELSE toFloat(row.risk_score) END,
    n.detail = CASE row.detail WHEN '' THEN null ELSE row.detail END;

LOAD CSV WITH HEADERS FROM 'file:///rules.csv' AS row
MERGE (n:Rule {rule_id: row.rule_id})
SET n.rule_name = row.rule_name,
    n.rule_category = CASE row.rule_category WHEN '' THEN null ELSE row.rule_category END,
    n.rule_level = CASE row.rule_level WHEN '' THEN null ELSE row.rule_level END,
    n.threshold_desc = CASE row.threshold_desc WHEN '' THEN null ELSE row.threshold_desc END,
    n.description = CASE row.description WHEN '' THEN null ELSE row.description END,
    n.enabled = CASE row.enabled WHEN '' THEN null ELSE toBoolean(row.enabled) END;

LOAD CSV WITH HEADERS FROM 'file:///alerts.csv' AS row
MERGE (n:Alert {alert_id: row.alert_id})
SET n.alert_name = row.alert_name,
    n.severity = CASE row.severity WHEN '' THEN null ELSE row.severity END,
    n.score = CASE row.score WHEN '' THEN null ELSE toFloat(row.score) END,
    n.status = CASE row.status WHEN '' THEN null ELSE row.status END,
    n.first_seen = CASE row.first_seen WHEN '' THEN null ELSE row.first_seen END,
    n.last_seen = CASE row.last_seen WHEN '' THEN null ELSE row.last_seen END,
    n.description = CASE row.description WHEN '' THEN null ELSE row.description END,
    n.suggestion = CASE row.suggestion WHEN '' THEN null ELSE row.suggestion END;

LOAD CSV WITH HEADERS FROM 'file:///block_actions.csv' AS row
MERGE (n:BlockAction {action_id: row.action_id})
SET n.action_type = CASE row.action_type WHEN '' THEN null ELSE row.action_type END,
    n.target_type = CASE row.target_type WHEN '' THEN null ELSE row.target_type END,
    n.status = CASE row.status WHEN '' THEN null ELSE row.status END,
    n.executed_at = CASE row.executed_at WHEN '' THEN null ELSE row.executed_at END,
    n.executor = CASE row.executor WHEN '' THEN null ELSE row.executor END,
    n.ticket_no = CASE row.ticket_no WHEN '' THEN null ELSE row.ticket_no END,
    n.rollback_supported = CASE row.rollback_supported WHEN '' THEN null ELSE toBoolean(row.rollback_supported) END,
    n.remark = CASE row.remark WHEN '' THEN null ELSE row.remark END;

////////////////////////////////////////////////////////////////////////
// 二、导入关系
////////////////////////////////////////////////////////////////////////

LOAD CSV WITH HEADERS FROM 'file:///rel_user_initiates_session.csv' AS row
MATCH (a:User {user_id: row.user_id})
MATCH (b:Session {session_id: row.session_id})
MERGE (a)-[r:INITIATES]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

LOAD CSV WITH HEADERS FROM 'file:///rel_session_uses_source_ip.csv' AS row
MATCH (a:Session {session_id: row.session_id})
MATCH (b:IP {ip_id: row.ip_id})
MERGE (a)-[r:USES_SOURCE_IP]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

LOAD CSV WITH HEADERS FROM 'file:///rel_session_accesses_host.csv' AS row
MATCH (a:Session {session_id: row.session_id})
MATCH (b:Host {host_id: row.host_id})
MERGE (a)-[r:ACCESSES]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

LOAD CSV WITH HEADERS FROM 'file:///rel_session_generates_event.csv' AS row
MATCH (a:Session {session_id: row.session_id})
MATCH (b:Event {event_id: row.event_id})
MERGE (a)-[r:GENERATES]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

LOAD CSV WITH HEADERS FROM 'file:///rel_event_triggers_alert.csv' AS row
MATCH (a:Event {event_id: row.event_id})
MATCH (b:Alert {alert_id: row.alert_id})
MERGE (a)-[r:TRIGGERS]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

LOAD CSV WITH HEADERS FROM 'file:///rel_alert_hit_rule.csv' AS row
MATCH (a:Alert {alert_id: row.alert_id})
MATCH (b:Rule {rule_id: row.rule_id})
MERGE (a)-[r:HIT_RULE]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

LOAD CSV WITH HEADERS FROM 'file:///rel_block_disposes_alert.csv' AS row
MATCH (a:BlockAction {action_id: row.action_id})
MATCH (b:Alert {alert_id: row.alert_id})
MERGE (a)-[r:DISPOSES]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

LOAD CSV WITH HEADERS FROM 'file:///rel_block_targets_ip.csv' AS row
MATCH (a:BlockAction {action_id: row.action_id})
MATCH (b:IP {ip_id: row.ip_id})
MERGE (a)-[r:TARGETS_IP]->(b)
SET r.relation_time = CASE row.relation_time WHEN '' THEN null ELSE row.relation_time END;

////////////////////////////////////////////////////////////////////////
// 三、导入后验证查询
////////////////////////////////////////////////////////////////////////

// 查看节点数量
MATCH (n)
RETURN labels(n) AS labels, count(*) AS total
ORDER BY total DESC;

// 查看关系数量
MATCH ()-[r]->()
RETURN type(r) AS relation_type, count(*) AS total
ORDER BY total DESC;

// 查看典型攻击链
MATCH (u:User)-[:INITIATES]->(s:Session)-[:GENERATES]->(e:Event)-[:TRIGGERS]->(a:Alert)
OPTIONAL MATCH (b:BlockAction)-[:DISPOSES]->(a)
RETURN u.username, s.session_id, e.event_type, a.alert_name, b.action_type
ORDER BY s.session_id;
