import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: (to) => {
        return { path: '/patient', query: { showall: to.query.showall || 'false' } };
      },
    },
    {
      path: '/patient',
      component: () => import('../views/PatientsView.vue'),
      children: [
        {
          path: '',
          name: 'patient',
          component: () => import('../views/PatientDetailView.vue'),
          children: [
            {
              path: '',
              name: 'patient.report.empty',
              component: () => import('../views/ReportDetailView.vue'),
            },
          ],
        },
        {
          path: '/patient/:patient_id',
          component: () => import('../views/PatientDetailView.vue'),
          children: [
            {
              path: '',
              name: 'patient.detail',
              component: () => import('../views/ReportDetailView.vue'),
              props: (route) => ({ showall: route.query.showall || 'false' }),
            },
            {
              path: 'report/:report_id',
              name: 'patient.report.detail',
              component: () => import('../views/ReportDetailView.vue'),
              props: (route) => ({ showall: route.query.showall || 'false' }), // Ensure showall is passed as prop
            },
          ],
        },
      ],
    },
  ],
});

export default router;
