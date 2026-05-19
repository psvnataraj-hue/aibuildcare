<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  ClipboardList,
  Wrench,
  BarChart3,
  Settings as SettingsIcon,
  LogOut,
  Moon,
  Sun,
  Building2,
} from 'lucide-vue-next'
import { clearToken, hasToken } from './api'
import { isDark, toggleTheme } from './lib/theme'

const route = useRoute()
const router = useRouter()

const nav = [
  { to: '/', label: 'Dashboard · डैशबोर्ड', icon: LayoutDashboard },
  { to: '/complaints', label: 'Complaints · शिकायतें', icon: ClipboardList },
  { to: '/performance', label: 'Contractors · ठेकेदार', icon: Wrench },
  { to: '/analytics', label: 'Analytics · विश्लेषण', icon: BarChart3 },
  { to: '/settings', label: 'Settings · सेटिंग्स', icon: SettingsIcon },
]

function logout() {
  clearToken()
  router.push('/login')
}
const shell = () => hasToken() && route.path !== '/login'
</script>

<template>
  <div v-if="shell()" class="min-h-full flex">
    <aside
      class="w-60 shrink-0 border-r bg-card hidden md:flex flex-col"
    >
      <div class="h-16 flex items-center gap-2 px-5 border-b">
        <Building2 class="h-6 w-6 text-primary" />
        <span class="font-bold text-lg">AIBuildCare</span>
      </div>
      <nav class="flex-1 p-3 space-y-1">
        <RouterLink
          v-for="n in nav"
          :key="n.to"
          :to="n.to"
          class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors"
          :class="
            route.path === n.to
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
          "
        >
          <component :is="n.icon" class="h-4 w-4" />
          {{ n.label }}
        </RouterLink>
      </nav>
      <div class="p-3 border-t">
        <button
          class="flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-secondary hover:text-foreground"
          @click="logout"
        >
          <LogOut class="h-4 w-4" /> Logout
        </button>
      </div>
    </aside>

    <div class="flex-1 flex flex-col min-w-0">
      <header
        class="h-16 border-b bg-card/80 backdrop-blur flex items-center justify-between px-4 md:px-6 sticky top-0 z-10"
      >
        <span class="font-semibold capitalize">
          {{ route.path === '/' ? 'Overview' : route.path.slice(1).split('/')[0] }}
        </span>
        <div class="flex items-center gap-1">
          <button
            class="h-9 w-9 inline-flex items-center justify-center rounded-md hover:bg-secondary"
            :title="isDark ? 'Light mode' : 'Dark mode'"
            @click="toggleTheme"
          >
            <Sun v-if="isDark" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </button>
          <RouterLink
            to="/complaints"
            class="md:hidden h-9 w-9 inline-flex items-center justify-center rounded-md hover:bg-secondary"
          >
            <ClipboardList class="h-4 w-4" />
          </RouterLink>
        </div>
      </header>
      <main class="flex-1 p-4 md:p-6 max-w-6xl w-full mx-auto">
        <RouterView />
      </main>
    </div>
  </div>

  <RouterView v-else />
</template>
