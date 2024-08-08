import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/login'
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
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
              component: () => import('../views/ReportDetailView.vue')
            }
        ]
        },
        {
          path: '/patient/:patient_id',
          component: () => import('../views/PatientDetailView.vue'),
          children: [
            {
              path: '/patient/:patient_id',
              name: 'patient.detail',
              component: () => import('../views/ReportDetailView.vue')
            },
            {
              path: 'report/:report_id',
              name: 'patient.report.detail',
              component: () => import('../views/ReportDetailView.vue')
            },
          ]
        }
      ]
    }
  ]
})
export default router
