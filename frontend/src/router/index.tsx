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
          path: "/patient/:patient_id",
          name: "patient.detail",
          component: () => import("../views/PatientDetailView.vue"),
          children: [
            {
              path: "/patient/:patient_id/record/:record_id",
              name: "patient.record.detail",
              component: () => import("../views/RecordDetailView.vue"),
            },
          ],
        },
      ],
    },
  ],
});

export default router;
