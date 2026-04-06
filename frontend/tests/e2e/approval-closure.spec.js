import { expect, test } from "@playwright/test";

const analystUser = {
  user_id: "OPS-001",
  username: "analyst",
  display_name: "值班分析员",
  department: "安全运营中心",
  role: "user"
};

const adminUser = {
  user_id: "ADMIN-001",
  username: "admin",
  display_name: "平台管理员",
  department: "平台治理中心",
  role: "admin"
};

function buildSuccess(data, message = "操作成功") {
  return {
    code: 0,
    message,
    data,
    timestamp: "2026-04-06T09:00:00+08:00"
  };
}

function formatTimestamp(step) {
  const hour = String(9 + Math.floor(step / 60)).padStart(2, "0");
  const minute = String(step % 60).padStart(2, "0");
  return `2026-04-06 ${hour}:${minute}:00`;
}

function buildSummary(items) {
  return {
    total: items.length,
    pending: items.filter((item) => item.status === "待审批").length,
    approved: items.filter((item) => item.status === "已通过").length,
    rejected: items.filter((item) => item.status === "已驳回").length
  };
}

function createMockBackend() {
  let requestIndex = 1;
  let auditIndex = 1;
  let timestampIndex = 0;
  const sessions = new Map();
  const disposals = [];
  const bans = [];
  const auditLogs = [];

  function nextTimestamp() {
    const value = formatTimestamp(timestampIndex);
    timestampIndex += 1;
    return value;
  }

  function createAudit({ module, action, operator, target, result, risk_level, detail }) {
    auditLogs.unshift({
      audit_id: `AUD-E2E-${String(auditIndex).padStart(3, "0")}`,
      module,
      action,
      operator_id: operator.user_id,
      operator: operator.display_name,
      operator_role: operator.role === "admin" ? "管理员" : "普通用户",
      target,
      target_id: "",
      result,
      risk_level,
      operated_at: nextTimestamp(),
      detail
    });
    auditIndex += 1;
  }

  function createSession(user) {
    const sessionToken = `session-${user.username}-${sessions.size + 1}`;
    sessions.set(sessionToken, user);
    return sessionToken;
  }

  function getAuthorizedUser(request) {
    const header = request.headers().authorization || "";
    const token = header.replace(/^Bearer\s+/i, "").trim();
    return sessions.get(token) || null;
  }

  function buildApprovalOverview() {
    const reviewedItems = [...disposals]
      .filter((item) => ["已通过", "已驳回"].includes(item.status))
      .sort((left, right) => String(right.reviewed_at || right.updated_at).localeCompare(String(left.reviewed_at || left.updated_at)));
    const pendingItems = [...disposals]
      .filter((item) => item.status === "待审批")
      .sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));

    return {
      enabled: true,
      pending_disposal_count: pendingItems.length,
      approved_today_count: reviewedItems.filter((item) => item.status === "已通过").length,
      rejected_today_count: reviewedItems.filter((item) => item.status === "已驳回").length,
      recent_action_time: reviewedItems[0]?.reviewed_at || "",
      recent_disposals: pendingItems.slice(0, 5),
      recent_reviews: reviewedItems.slice(0, 5)
    };
  }

  function buildOverviewResponse() {
    return {
      summary: {
        node_total: 128,
        relation_total: 246,
        alert_total: 18,
        blocked_ip_total: bans.filter((item) => item.current_ban_status === "BLOCKED").length,
        high_risk_event_total: 6
      },
      latest_alerts: [
        {
          alert_id: "ALT-BASE-001",
          alert_name: "异常登录集中告警",
          severity: "HIGH",
          status: "待研判",
          score: 92,
          event_type: "LOGIN",
          rule_name: "异常登录行为识别"
        }
      ],
      top_risk_users: [
        { user_id: "OPS-001", username: "analyst", department: "安全运营中心", risk_score: 88 }
      ],
      top_risk_ips: [
        { ip_id: "IP-001", ip_address: "10.10.10.10", ip_type: "办公终端", risk_score: 86, is_blocked: false }
      ],
      top_risk_hosts: [
        { host_id: "HOST-001", hostname: "SRV-APP-01", asset_type: "业务主机", risk_score: 82 }
      ],
      approval_overview: buildApprovalOverview()
    };
  }

  function buildBanItem(record, reviewerName, reviewedAt, reviewComment) {
    const actionId = `LINKED-BAN-${record.source_ip.replaceAll(".", "_")}`;
    return {
      action_id: actionId,
      action_type: "BLOCK_IP",
      block_source: "manual",
      latest_action_type: "MANUAL_BLOCK_IP",
      target_type: "IP",
      status: "BLOCKED",
      current_ban_status: "BLOCKED",
      current_block_status: "BLOCKED",
      executed_at: reviewedAt,
      executor: reviewerName,
      ticket_no: "",
      rollback_supported: true,
      remark: reviewComment,
      alert_id: record.alert_id,
      alert_name: record.alert_name,
      severity: record.severity,
      ip_id: `IP-${record.source_ip.replaceAll(".", "_")}`,
      ip_address: record.source_ip,
      ip_block_status: "BLOCKED",
      is_blocked: true,
      blocked_at: reviewedAt,
      blocked_by: reviewerName,
      block_reason: reviewComment,
      behavior_id: "",
      behavior_type: record.alert_name,
      risk_score: record.severity === "CRITICAL" ? 90 : 80,
      confidence: 0.95,
      event_count: 1,
      source_type: "disposal_approval",
      released_at: "",
      released_by: "",
      release_reason: "",
      latest_action_at: reviewedAt,
      latest_action_by: reviewerName,
      latest_action_reason: reviewComment,
      latest_operator: reviewerName,
      latest_reason: reviewComment,
      history_action_count: 1,
      history_actions: [
        {
          sequence: 1,
          action_type: "MANUAL_BLOCK_IP",
          from_status: "NONE",
          to_status: "BLOCKED",
          operated_at: reviewedAt,
          operated_by: reviewerName,
          reason: reviewComment,
          origin: "MANUAL"
        }
      ],
      history_actions_brief: [
        {
          sequence: 1,
          action_type: "MANUAL_BLOCK_IP",
          from_status: "NONE",
          to_status: "BLOCKED",
          operated_at: reviewedAt,
          operated_by: reviewerName,
          reason: reviewComment,
          origin: "MANUAL"
        }
      ],
      history_summary: "人工重新封禁",
      block_count: 1,
      release_count: 0,
      is_released: false,
      can_unban: true,
      can_reblock: false,
      can_verify: true,
      enforcement_mode: "MOCK",
      enforcement_backend: "MOCK",
      enforcement_status: "SIMULATED",
      enforcement_rule_name: `MOCK-${actionId}`,
      enforcement_message: "策略校验已完成",
      enforcement_executed: true,
      enforcement_success: true,
      verification_status: "VERIFIED",
      verified_at: reviewedAt,
      verification_message: "封禁状态已同步",
      verification_supported: true,
      verification_attempted: true,
      block_effective: true,
      truly_blocked: true,
      enforcement_scope_ports: "",
      enforcement_scope_description: "应用层封禁已执行",
      approval_source_label: "处置申请审批",
      approval_request_id: record.request_id,
      approval_reviewer_name: reviewerName,
      approval_reviewed_at: reviewedAt,
      approval_review_comment: reviewComment,
      approval_execution_status: "已封禁"
    };
  }

  async function fulfillJson(route, status, payload) {
    await route.fulfill({
      status,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET,POST,PATCH,OPTIONS",
        "access-control-allow-headers": "Content-Type, Authorization"
      },
      body: JSON.stringify(payload)
    });
  }

  async function handleRoute(route) {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,PATCH,OPTIONS",
          "access-control-allow-headers": "Content-Type, Authorization"
        }
      });
      return;
    }

    if (path === "/api/auth/login" && method === "POST") {
      const payload = request.postDataJSON();
      const user = payload.username === "admin" ? adminUser : payload.username === "analyst" ? analystUser : null;

      if (!user || payload.password !== "123456") {
        await fulfillJson(route, 401, {
          code: 401,
          message: "账号或密码错误",
          data: null,
          timestamp: "2026-04-06T09:00:00+08:00"
        });
        return;
      }

      const sessionToken = createSession(user);
      await fulfillJson(route, 200, buildSuccess({ session_token: sessionToken, user }, "登录成功"));
      return;
    }

    if (path === "/api/auth/me" && method === "GET") {
      const user = getAuthorizedUser(request);
      if (!user) {
        await fulfillJson(route, 401, {
          code: 401,
          message: "登录状态已失效，请重新登录",
          data: null,
          timestamp: "2026-04-06T09:00:00+08:00"
        });
        return;
      }

      await fulfillJson(route, 200, buildSuccess({ session_token: request.headers().authorization?.replace(/^Bearer\s+/i, ""), user }, "会话恢复成功"));
      return;
    }

    const currentUser = getAuthorizedUser(request);
    if (!currentUser) {
      await fulfillJson(route, 401, {
        code: 401,
        message: "登录状态已失效，请重新登录",
        data: null,
        timestamp: "2026-04-06T09:00:00+08:00"
      });
      return;
    }

    if (path === "/api/graph/overview" && method === "GET") {
      await fulfillJson(route, 200, buildSuccess(buildOverviewResponse(), "总览数据获取成功"));
      return;
    }

    if (path === "/api/disposals" && method === "GET") {
      await fulfillJson(route, 200, buildSuccess({ items: [...disposals], summary: buildSummary(disposals) }, "处置申请获取成功"));
      return;
    }

    if (path === "/api/disposals/my" && method === "GET") {
      const items = disposals.filter((item) => item.applicant_id === currentUser.user_id);
      await fulfillJson(route, 200, buildSuccess({ items, summary: buildSummary(items) }, "我的处置记录获取成功"));
      return;
    }

    if (path === "/api/disposals" && method === "POST") {
      const payload = request.postDataJSON();
      const now = nextTimestamp();
      const requestId = `REQ-20260406-${String(requestIndex).padStart(3, "0")}`;
      requestIndex += 1;
      const record = {
        request_id: requestId,
        alert_id: payload.alert_id,
        alert_name: payload.alert_name,
        source_ip: payload.source_ip,
        severity: payload.severity,
        status: "待审批",
        applicant_id: currentUser.user_id,
        applicant_name: currentUser.display_name,
        applicant_role: currentUser.role,
        disposal_type: payload.disposal_type,
        urgency_level: payload.urgency_level,
        disposition_opinion: payload.disposition_opinion,
        review_comment: "",
        reviewer_id: "",
        reviewer_name: "",
        reviewed_at: "",
        execution_status: "",
        execution_target: payload.source_ip,
        execution_message: "",
        linked_ban_action_id: "",
        created_at: now,
        updated_at: now
      };
      disposals.unshift(record);
      createAudit({
        module: "处置申请",
        action: "提交处置申请",
        operator: currentUser,
        target: `${record.alert_name} / ${record.alert_id}`,
        result: "待审批",
        risk_level: record.severity === "CRITICAL" || record.severity === "HIGH" ? "高" : "中",
        detail: `提交${record.disposal_type}，处置意见：${record.disposition_opinion}`
      });
      await fulfillJson(route, 200, buildSuccess(record, "处置申请提交成功"));
      return;
    }

    if (path.startsWith("/api/disposals/") && method === "PATCH") {
      const requestId = path.split("/").at(-1);
      const payload = request.postDataJSON();
      const record = disposals.find((item) => item.request_id === requestId);

      if (!record) {
        await fulfillJson(route, 404, {
          code: 404,
          message: "申请记录不存在",
          data: null,
          timestamp: "2026-04-06T09:00:00+08:00"
        });
        return;
      }

      const reviewedAt = nextTimestamp();
      const reviewComment = String(payload.review_comment || "").trim();
      record.status = payload.status;
      record.review_comment = reviewComment;
      record.reviewer_id = currentUser.user_id;
      record.reviewer_name = currentUser.display_name;
      record.reviewed_at = reviewedAt;
      record.updated_at = reviewedAt;
      record.execution_status = "";
      record.execution_message = "";
      record.linked_ban_action_id = "";

      createAudit({
        module: "处置申请",
        action: "审批处置申请",
        operator: currentUser,
        target: `${record.alert_name} / ${record.request_id}`,
        result: record.status,
        risk_level: record.severity === "CRITICAL" || record.severity === "HIGH" ? "高" : "中",
        detail: `审批备注：${reviewComment}`
      });

      if (record.status === "已通过" && record.disposal_type === "封禁申请") {
        const linkedBan = buildBanItem(record, currentUser.display_name, reviewedAt, reviewComment);
        record.execution_status = "已封禁";
        record.execution_message = `处置申请 ${record.request_id} 审批通过后已联动封禁来源 IP ${record.source_ip}。`;
        record.linked_ban_action_id = linkedBan.action_id;

        const existingIndex = bans.findIndex((item) => item.action_id === linkedBan.action_id);
        if (existingIndex >= 0) {
          bans.splice(existingIndex, 1, linkedBan);
        } else {
          bans.unshift(linkedBan);
        }

        createAudit({
          module: "处置申请",
          action: "联动封禁处置",
          operator: currentUser,
          target: `${record.alert_name} / ${record.request_id}`,
          result: "已封禁",
          risk_level: record.severity === "CRITICAL" || record.severity === "HIGH" ? "高" : "中",
          detail: `处置申请 ${record.request_id} 审批通过后已联动封禁来源 IP ${record.source_ip}，审批人：${currentUser.display_name}，审批备注：${reviewComment}，联动结果：已封禁。`
        });
      }

      await fulfillJson(route, 200, buildSuccess(record, "处置申请审批成功"));
      return;
    }

    if (path === "/api/bans" && method === "GET") {
      const status = url.searchParams.get("status") || "";
      const keywordIp = url.searchParams.get("target_ip") || "";
      const filteredItems = bans.filter((item) => {
        if (status && item.current_ban_status !== status) {
          return false;
        }
        if (keywordIp && !String(item.ip_address || "").includes(keywordIp)) {
          return false;
        }
        return true;
      });
      await fulfillJson(
        route,
        200,
        buildSuccess(
          {
            items: filteredItems,
            pagination: {
              page: Number(url.searchParams.get("page") || "1"),
              size: Number(url.searchParams.get("size") || "10"),
              total: filteredItems.length
            },
            filters: {
              status: status || null,
              target_ip: keywordIp || null
            },
            enforcement_profile: {
              mode: "MOCK",
              backend: "MOCK",
              host_platform: "APPLICATION",
              supports_real_execution: false,
              rule_prefix: "ESG",
              local_ports: [],
              scope_description: "策略校验"
            }
          },
          "封禁处置列表获取成功"
        )
      );
      return;
    }

    if (path.startsWith("/api/bans/") && method === "GET") {
      const banId = path.split("/").at(-1);
      const banItem = bans.find((item) => item.action_id === banId);
      if (!banItem) {
        await fulfillJson(route, 404, {
          code: 404,
          message: "封禁记录不存在",
          data: null,
          timestamp: "2026-04-06T09:00:00+08:00"
        });
        return;
      }
      await fulfillJson(route, 200, buildSuccess(banItem, "封禁记录详情获取成功"));
      return;
    }

    if (path === "/api/audit/logs" && method === "GET") {
      await fulfillJson(route, 200, buildSuccess({ items: [...auditLogs] }, "审计日志获取成功"));
      return;
    }

    if (path.startsWith("/api/audit/logs/") && method === "GET") {
      const auditId = path.split("/").at(-1);
      const auditItem = auditLogs.find((item) => item.audit_id === auditId);
      if (!auditItem) {
        await fulfillJson(route, 404, {
          code: 404,
          message: "审计记录不存在",
          data: null,
          timestamp: "2026-04-06T09:00:00+08:00"
        });
        return;
      }
      await fulfillJson(route, 200, buildSuccess(auditItem, "审计详情获取成功"));
      return;
    }

    await fulfillJson(route, 404, {
      code: 404,
      message: `未实现的测试接口：${method} ${path}`,
      data: null,
      timestamp: "2026-04-06T09:00:00+08:00"
    });
  }

  return {
    async attach(page) {
      await page.context().route("http://127.0.0.1:5000/api/**", handleRoute);
    },
    latestRequestId() {
      return disposals[0]?.request_id || "";
    }
  };
}

async function login(page, username) {
  await page.goto("/login");
  await page.locator(".login-form input").nth(0).fill(username);
  await page.locator(".login-form input").nth(1).fill("123456");
  await page.locator(".login-button").click();
  await page.waitForURL("**/console/dashboard");
}

async function clearSession(page) {
  await page.evaluate(() => {
    sessionStorage.clear();
  });
}

async function submitBanDisposal(page, payload) {
  await page.goto("/console/disposals");
  const formItems = page.locator(".request-form .el-form-item");

  await formItems.filter({ hasText: "告警编号" }).locator("input").fill(payload.alertId);
  await formItems.filter({ hasText: "告警名称" }).locator("input").fill(payload.alertName);
  await formItems.filter({ hasText: "处置目标 IP" }).locator("input").fill(payload.sourceIp);
  await formItems.filter({ hasText: "处置意见" }).locator("textarea").fill(payload.opinion);
  await page.locator(".form-actions .el-button--primary").click();
}

async function approveFromDashboard(page, requestId, comment, approve = true) {
  const row = page.locator(".approval-panel .el-table__row").filter({ hasText: requestId }).first();
  await expect(row).toBeVisible();
  const buttons = row.locator("button");
  await buttons.nth(approve ? 0 : 1).click();
  await expect(page.locator(".el-message-box")).toBeVisible();
  await page.locator(".el-message-box textarea").fill(comment);
  await page.locator(".el-message-box__btns .el-button--primary").click();
}

test("普通用户提交封禁申请后，管理员可在首页审批并在封禁页看到审批来源", async ({ page }) => {
  const backend = createMockBackend();
  await backend.attach(page);

  await login(page, "analyst");
  await submitBanDisposal(page, {
    alertId: "ALT-E2E-001",
    alertName: "异地登录封禁申请",
    sourceIp: "10.10.10.88",
    opinion: "建议立即封禁测试来源 IP。"
  });

  const requestId = backend.latestRequestId();
  await expect(page.locator(".record-card-list")).toContainText(requestId);

  await clearSession(page);
  await login(page, "admin");
  await expect(page.locator(".approval-panel")).toContainText(requestId);
  await approveFromDashboard(page, requestId, "联调通过，执行封禁。", true);
  await expect(page.locator(".review-panel")).toContainText(requestId);

  await page.goto("/console/bans");
  await expect(page.locator(".table-panel")).toContainText("处置申请审批");
  await expect(page.locator(".table-panel")).toContainText(requestId);
  await expect(page.locator(".table-panel")).toContainText("平台管理员");
  await expect(page.locator(".table-panel")).toContainText("联调通过，执行封禁。");
  await expect(page.locator(".table-panel")).toContainText("已封禁");

  await clearSession(page);
  await login(page, "analyst");
  await page.goto("/console/my-records");
  const analystRow = page.locator(".el-table__row").filter({ hasText: requestId }).first();
  await expect(analystRow).toContainText("已通过");
  await expect(analystRow).toContainText("已封禁");
});

test("管理员驳回后，我的处理记录和审计日志同步显示驳回原因", async ({ page }) => {
  const backend = createMockBackend();
  await backend.attach(page);

  await login(page, "analyst");
  await submitBanDisposal(page, {
    alertId: "ALT-E2E-002",
    alertName: "封禁申请二次复核",
    sourceIp: "10.10.10.99",
    opinion: "请复核后决定是否执行封禁。"
  });

  const requestId = backend.latestRequestId();
  await clearSession(page);
  await login(page, "admin");
  await approveFromDashboard(page, requestId, "证据不足，已驳回当前申请。", false);

  await page.goto("/console/audit");
  const auditRow = page.locator(".el-table__row").filter({ hasText: requestId }).first();
  await expect(auditRow).toContainText("已驳回");
  await auditRow.getByRole("button", { name: "查看详情" }).click();
  await expect(page.locator(".detail-drawer")).toContainText("证据不足，已驳回当前申请。");

  await clearSession(page);
  await login(page, "analyst");
  await page.goto("/console/my-records");
  const analystRow = page.locator(".el-table__row").filter({ hasText: requestId }).first();
  await expect(analystRow).toContainText("已驳回");
  await expect(analystRow).toContainText("证据不足，已驳回当前申请。");
});
