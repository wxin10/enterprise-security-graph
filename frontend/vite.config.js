import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

// 文件路径：frontend/vite.config.js
// 作用说明：
// 1. 启用 Vue 单文件组件支持。
// 2. 配置 @ 路径别名，减少前端代码中的相对路径层级。
// 3. 保持最小可运行配置，便于后续继续扩展前端工程。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url))
    }
  },
  server: {
    host: "0.0.0.0",
    port: 5173
  }
});
