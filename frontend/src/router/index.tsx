import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/patient",
      name: "patient",
      component: () => import("../views/PatientsView.vue"),
      children: [
        {
          path: "/patient/",
          name: "patient.empty",
          component: () => <div> empty </div>,
        },
        {
          path: "/patient/:id",
          name: "patient.detail",
          component: () => <div> id </div>,
        },
      ],
    },
  ],
});

export default router;
