import { expect, test } from "@playwright/test";

function buildUniqueSuffix() {
  return `${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function extractRequestId(cardText) {
  const matched = String(cardText || "").match(/申请编号：([A-Z0-9-]+)/);
  if (!matched) {
    throw new Error(`未能从页面文本中解析申请编号：${cardText}`);
  }
  return matched[1];
}

async function clearSession(page) {
  await page.evaluate(() => {
    sessionStorage.clear();
  });
}

async function login(page, username) {
  await page.goto("/login");
  await page.locator(".login-form input").nth(0).fill(username);
  await page.locator(".login-form input").nth(1).fill("123456");
  await page.locator(".login-button").click();
  await page.waitForURL("**/console/dashboard");
}

async function submitBanDisposal(page, payload) {
  await page.goto("/console/disposals");

  const formItems = page.locator(".request-form .el-form-item");
  await formItems.filter({ hasText: "告警编号" }).locator("input").fill(payload.alertId);
  await formItems.filter({ hasText: "告警名称" }).locator("input").fill(payload.alertName);
  await formItems.filter({ hasText: "处置目标 IP" }).locator("input").fill(payload.sourceIp);
  await formItems.filter({ hasText: "处置意见" }).locator("textarea").fill(payload.opinion);

  await page.locator(".form-actions .el-button--primary").click();
  await expect(page.locator(".record-card-list")).toContainText(payload.alertName);

  const recordCard = page.locator(".record-card").filter({ hasText: payload.alertName }).first();
  await expect(recordCard).toContainText("待审批");
  return extractRequestId(await recordCard.innerText());
}

async function reviewFromDashboard(page, requestId, comment, approve = true) {
  await page.goto("/console/dashboard");
  const row = page.locator(".approval-panel .el-table__row").filter({ hasText: requestId }).first();
  await expect(row).toBeVisible();

  const buttons = row.locator("button");
  await buttons.nth(approve ? 0 : 1).click();

  const dialog = page.locator(".el-message-box");
  await expect(dialog).toBeVisible();
  await dialog.locator("textarea").fill(comment);
  await dialog.locator(".el-message-box__btns .el-button--primary").click();
  await expect(dialog).toBeHidden();
}

test("普通用户提交封禁申请后，管理员可在首页审批并在封禁页看到审批来源说明", async ({ page }) => {
  const suffix = buildUniqueSuffix();
  const alertName = `真实E2E封禁申请-${suffix}`;

  await login(page, "analyst");
  const requestId = await submitBanDisposal(page, {
    alertId: `ALT-E2E-APPROVE-${suffix}`,
    alertName,
    sourceIp: "10.10.10.88",
    opinion: "建议立即封禁测试来源 IP，并继续观察关联访问行为。"
  });

  await clearSession(page);
  await login(page, "admin");
  await reviewFromDashboard(page, requestId, "联调通过，执行封禁。", true);

  await expect(page.locator(".review-panel")).toContainText(requestId);
  await expect(page.locator(".review-panel")).toContainText("联调通过，执行封禁。");
  await expect(page.locator(".review-panel")).toContainText("已封禁");

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
  await expect(analystRow).toContainText("联调通过，执行封禁。");
});

test("管理员驳回后，我的处理记录与审计日志同步显示驳回结果和原因", async ({ page }) => {
  const suffix = buildUniqueSuffix();
  const alertName = `真实E2E驳回申请-${suffix}`;

  await login(page, "analyst");
  const requestId = await submitBanDisposal(page, {
    alertId: `ALT-E2E-REJECT-${suffix}`,
    alertName,
    sourceIp: "10.10.10.99",
    opinion: "请结合更多证据复核后再决定是否执行封禁。"
  });

  await clearSession(page);
  await login(page, "admin");
  await reviewFromDashboard(page, requestId, "证据不足，驳回当前申请。", false);

  await page.goto("/console/audit");
  const auditRow = page.locator(".el-table__row").filter({ hasText: requestId }).first();
  await expect(auditRow).toContainText("已驳回");
  await auditRow.getByRole("button", { name: "查看详情" }).click();
  await expect(page.locator(".detail-drawer")).toContainText("证据不足，驳回当前申请。");

  await clearSession(page);
  await login(page, "analyst");
  await page.goto("/console/my-records");
  const analystRow = page.locator(".el-table__row").filter({ hasText: requestId }).first();
  await expect(analystRow).toContainText("已驳回");
  await expect(analystRow).toContainText("证据不足，驳回当前申请。");
});
