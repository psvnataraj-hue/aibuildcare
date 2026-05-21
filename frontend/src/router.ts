import { createRouter, createWebHistory } from 'vue-router'
import { hasToken } from './api'
import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import Complaints from './views/Complaints.vue'
import ComplaintDetail from './views/ComplaintDetail.vue'
import Contractors from './views/Contractors.vue'
import ContractorPerformance from './views/ContractorPerformance.vue'
import ContractorAnalytics from './views/ContractorAnalytics.vue'
import AnalyticsDashboard from './views/AnalyticsDashboard.vue'
import Settings from './views/Settings.vue'
import Staff from './views/Staff.vue'
import Hierarchy from './views/Hierarchy.vue'
import Vendors from './views/Vendors.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard, meta: { auth: true } },
    { path: '/complaints', component: Complaints, meta: { auth: true } },
    {
      path: '/complaints/:id',
      component: ComplaintDetail,
      meta: { auth: true },
    },
    { path: '/contractors', component: Contractors, meta: { auth: true } },
    {
      path: '/performance',
      component: ContractorPerformance,
      meta: { auth: true },
    },
    {
      path: '/contractors/:id',
      component: ContractorAnalytics,
      meta: { auth: true },
    },
    { path: '/analytics', component: AnalyticsDashboard, meta: { auth: true } },
    { path: '/staff', component: Staff, meta: { auth: true } },
    { path: '/hierarchy', component: Hierarchy, meta: { auth: true } },
    { path: '/vendors', component: Vendors, meta: { auth: true } },
    { path: '/settings', component: Settings, meta: { auth: true } },
  ],
})

router.beforeEach((to) => {
  if (to.meta.auth && !hasToken()) return '/login'
  if (to.path === '/login' && hasToken()) return '/'
})

export default router
