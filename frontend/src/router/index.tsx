import { createRouter, createWebHistory } from "vue-router";
const require_login = (to, from) => {
  if (!localStorage.token) {
    return "/login";
  }
};
const not_login = (to, from) => {
  if (localStorage.token) {
    return "/patient";
  }
};
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      component: () => <div>Loading...</div>,
      beforeEnter: (to, from) => {
        if (localStorage.token) {
          return "/patient";
        } else {
          return "/login";
        }
      },
    },
    {
      path: "/login",
      name: "login",
      component: () => import("../views/LoginView.vue"),
      beforeEnter: not_login,
    },
    {
      path: "/patient",
      component: () => import("../views/PatientsView.vue"),
      beforeEnter: require_login,
      children: [
        {
          path: "",
          name: "patient",
          component: () => import("../views/PatientDetailView.vue"),
          beforeEnter: require_login,
          children: [
            {
              path: "",
              name: "patient.report.empty",
              component: () => import("../views/ReportDetailView.vue"),
              beforeEnter: require_login,
            },
          ],
        },
        {
          path: "/patient/:patient_id",
          component: () => import("../views/PatientDetailView.vue"),
          beforeEnter: require_login,
          children: [
            {
              path: "/patient/:patient_id",
              name: "patient.detail",
              component: () => import("../views/ReportDetailView.vue"),
              beforeEnter: require_login,
            },
            {
              path: "report/:report_id",
              name: "patient.report.detail",
              component: () => import("../views/ReportDetailView.vue"),
              beforeEnter: require_login,
            },
          ],
        },
      ],
    },
    {
      path: "/creat_patient",
      name: "creat_patient",
      component: () => import("../views/CreatPatient.vue"),
      beforeEnter: require_login,
    },
    {
      path: "/patient/:patient_id/update",
      name: "patient.update",
      component: () => import("../views/UpdatePatient.vue"),
      beforeEnter: require_login,
    },
  ],
});
export default router;
