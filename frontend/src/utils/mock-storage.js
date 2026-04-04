// 文件路径：frontend/src/utils/mock-storage.js
// 作用说明：
// 1. 在前端本地维护“处置申请 / 我的处理记录”的模拟数据。
// 2. 为普通用户提交申请、查看个人记录以及后续审计展示提供统一数据源。
// 3. 当前阶段不新增后端接口，优先保证角色流程可演示、可验证。

const STORAGE_REQUEST_KEY = "mock_disposal_requests";

const DEFAULT_REQUESTS = [
  {
    request_id: "REQ-20260404-001",
    alert_id: "ALT-20031",
    alert_name: "异常登录失败激增",
    severity: "HIGH",
    status: "待审批",
    applicant_id: "OPS-001",
    applicant_name: "值班分析员",
    applicant_role: "user",
    disposal_type: "封禁申请",
    urgency_level: "高",
    disposition_opinion: "建议先封禁源 IP 2 小时，并继续观察同源账号行为。",
    created_at: "2026-04-04 08:30:00",
    updated_at: "2026-04-04 08:30:00"
  }
];

function ensureDefaultRequests() {
  if (!sessionStorage.getItem(STORAGE_REQUEST_KEY)) {
    sessionStorage.setItem(STORAGE_REQUEST_KEY, JSON.stringify(DEFAULT_REQUESTS));
  }
}

function formatNow() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  const hour = String(now.getHours()).padStart(2, "0");
  const minute = String(now.getMinutes()).padStart(2, "0");
  const second = String(now.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

export function listDisposalRequests() {
  ensureDefaultRequests();

  try {
    const records = JSON.parse(sessionStorage.getItem(STORAGE_REQUEST_KEY) || "[]");
    return [...records].sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));
  } catch (error) {
    sessionStorage.setItem(STORAGE_REQUEST_KEY, JSON.stringify(DEFAULT_REQUESTS));
    return [...DEFAULT_REQUESTS];
  }
}

export function saveDisposalRequest(payload) {
  const nextItem = {
    request_id: `REQ-${Date.now()}`,
    status: "待审批",
    created_at: formatNow(),
    updated_at: formatNow(),
    ...payload
  };

  const nextRecords = [nextItem, ...listDisposalRequests()];
  sessionStorage.setItem(STORAGE_REQUEST_KEY, JSON.stringify(nextRecords));
  return nextItem;
}

export function listMyDisposalRequests(user) {
  if (!user?.user_id) {
    return [];
  }

  return listDisposalRequests().filter((item) => item.applicant_id === user.user_id);
}

export function buildAuditLogRecords() {
  return listDisposalRequests().map((item) => ({
    audit_id: `AUD-${item.request_id}`,
    module: "处置申请",
    action: item.status === "待审批" ? "提交申请" : "申请流转",
    operator: item.applicant_name,
    operator_role: item.applicant_role === "admin" ? "管理员" : "普通用户",
    target: `${item.alert_name} / ${item.alert_id}`,
    result: item.status,
    operated_at: item.updated_at || item.created_at
  }));
}
