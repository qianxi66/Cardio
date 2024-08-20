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
      beforeEnter: (to, from,next) => {
        if (localStorage.token) {
          next(); }
        else {
          next('/login'); }
      },
      children: [
        {
          path: '',
          name: 'patient',
          component: () => import('../views/PatientDetailView.vue'),
          beforeEnter: (to, from,next) => {
            if (localStorage.token) {
              next(); }
            else {
              next('/login'); }
          },
          children: [
            {
              path: '',
              name: 'patient.report.empty',
              component: () => import('../views/ReportDetailView.vue'),
              beforeEnter: (to, from,next) => {
                if (localStorage.token) {
                  next(); }
                else {
                  next('/login'); }
              },
            }
        ]
        },
        {
          path: '/patient/:patient_id',
          component: () => import('../views/PatientDetailView.vue'),
          beforeEnter: (to, from,next) => {
            if (localStorage.token) {
              next(); }
            else {
              next('/login'); }
          },
          children: [
            {
              path: '/patient/:patient_id',
              name: 'patient.detail',
              component: () => import('../views/ReportDetailView.vue'),
              beforeEnter: (to, from,next) => {
                if (localStorage.token) {
                  next(); }
                else {
                  next('/login'); }
              },
            },
            {
              path: 'report/:report_id',
              name: 'patient.report.detail',
              component: () => import('../views/ReportDetailView.vue'),
              beforeEnter: (to, from,next) => {
                if (localStorage.token) {
                  next(); }
                else {
                  next('/login'); }
              },
            },
          ]
        }
      ]
    }
  ]
})
export default router
