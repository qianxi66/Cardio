import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/patient',
      name: 'patient',
      component: () => import('../views/PatientsView.vue')
    },
  ]
})

export default router
