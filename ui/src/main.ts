import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";
import App from "./App.vue";
import ControlPanel from "./views/ControlPanel.vue";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: "/",
      name: "control",
      component: ControlPanel,
    },
  ],
});

createApp(App).use(router).mount("#app");
