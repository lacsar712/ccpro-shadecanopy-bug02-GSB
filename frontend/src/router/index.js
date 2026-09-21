import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import GreenhousesView from '../views/GreenhousesView.vue'
import ZonesView from '../views/ZonesView.vue'
import ClimateLogsView from '../views/ClimateLogsView.vue'
import IrrigationView from '../views/IrrigationView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/greenhouses', name: 'greenhouses', component: GreenhousesView },
    { path: '/zones', name: 'zones', component: ZonesView },
    { path: '/climate-logs', name: 'climate-logs', component: ClimateLogsView },
    { path: '/irrigation', name: 'irrigation', component: IrrigationView },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
  if (auth.isAuthenticated && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { name: 'login' }
    }
  }
})

export default router
