// 文件路径：frontend/src/main.js
// 作用说明：
// 1. 创建 Vue 应用实例。
// 2. 注册 Vue Router、Element Plus 和全局图标。
// 3. 加载全局样式，统一企业安全平台深蓝风格。

import { createApp } from "vue";
import ElementPlus from "element-plus";
import * as ElementPlusIconsVue from "@element-plus/icons-vue";

import App from "./App.vue";
import router from "./router";
import "element-plus/dist/index.css";
import "./styles/global.css";

const app = createApp(App);

// 逐个注册 Element Plus 图标。
// 这样在模板中可以直接使用图标组件，便于菜单、卡片和操作按钮扩展。
Object.entries(ElementPlusIconsVue).forEach(([iconName, component]) => {
  app.component(iconName, component);
});

app.use(router);
app.use(ElementPlus);
app.mount("#app");
