import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/workspaces',
      children: [
        {
          path: 'workspaces',
          name: 'workspaces',
          component: () => import('@/views/workspaces/WorkspaceListView.vue'),
        },
        {
          path: 'workspaces/:wsId',
          name: 'workspace-detail',
          component: () => import('@/views/workspaces/WorkspaceDetailView.vue'),
        },
        {
          path: 'skills',
          name: 'skills',
          component: () => import('@/views/marketplace/SkillsView.vue'),
        },
        {
          path: 'mcps',
          name: 'mcps',
          component: () => import('@/views/marketplace/McpsView.vue'),
        },
        {
          path: 'feishu-apps',
          name: 'feishu-apps',
          component: () => import('@/views/feishu-apps/FeishuAppsView.vue'),
        },
        {
          path: 'memory',
          name: 'memory',
          component: () => import('@/views/memory/MemoryView.vue'),
        },
        {
          path: 'sessions',
          name: 'sessions',
          component: () => import('@/views/sessions/SessionHistoryView.vue'),
        },
        {
          path: 'traces',
          name: 'traces',
          component: () => import('@/views/traces/TracesView.vue'),
        },
        {
          path: 'insights',
          name: 'insights',
          component: () => import('@/views/insights/InsightsView.vue'),
        },
        {
          path: 'monitoring',
          name: 'monitoring',
          component: () => import('@/views/monitoring/MonitoringView.vue'),
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/users/UsersView.vue'),
          meta: { requireAdmin: true },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/workspaces',
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true

  const store = useUserStore()

  if (!store.initialized) {
    await store.fetchMe()
  }

  if (!store.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requireAdmin && store.user?.role !== 'admin') {
    return { name: 'workspaces' }
  }

  return true
})

export default router
