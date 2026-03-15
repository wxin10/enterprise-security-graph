// 文件路径：frontend/src/api/bans.js
// 作用说明：
// 1. 封装封禁管理相关接口请求。
// 2. 统一处理 /api/bans 的分页与筛选参数。
// 3. 便于后续继续扩展封禁详情、回滚等接口。

import http from "@/api/http";

export function fetchBans(params) {
  return http.get("/api/bans", {
    params
  });
}
