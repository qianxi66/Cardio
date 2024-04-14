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
          component: () => import("../views/EmptyPatientView.vue"),
        },
        {
          path: "/patient/:patient_id",
          name: "patient.detail",
          component: () => import("../views/PatientDetailView.vue"),
          children: [
            {
              path: "/patient/:patient_id/report/:report_id",
              name: "patient.report.detail",
              component: () => import("../views/ReportDetailView.vue"),
            },
          ],
        },
      ],
    },
  ],
});

export default router;
