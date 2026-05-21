<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  ClipboardList,
  Wrench,
  BarChart3,
  Settings as SettingsIcon,
  Users as UsersIcon,
  TrendingUp,
  LogOut,
  Moon,
  Sun,
  Building2,
  Menu,
  X,
  User,
  HelpCircle,
} from 'lucide-vue-next'
import { api, clearToken, hasToken, PERMISSIONS } from './api'
import { isDark, toggleTheme } from './lib/theme'
import { lang, t, toggleLang } from './lib/i18n'
import {
  currentUser,
  clearCurrentUser,
} from './lib/currentUser'
import Toaster from './components/ui/Toaster.vue'

const route = useRoute()
const router = useRouter()
const menuOpen = ref(false)
const profileOpen = ref(false)

// E3h: every nav item declares the minimum permission it requires.
// `null` = always visible to any authenticated user (Dashboard,
// Settings are user-scoped; Complaints requires at least the basic
// view-own/view-all gates the page itself enforces server-side).
const ALL_NAV = [
  { to: '/', key: 'dashboard', icon: LayoutDashboard, perm: null },
  { to: '/complaints', key: 'complaints', icon: ClipboardList, perm: null },
  { to: '/performance', key: 'contractors', icon: Wrench,
    perm: PERMISSIONS.VIEW_ALL },
  { to: '/staff', key: 'staff', icon: UsersIcon,
    perm: PERMISSIONS.MODIFY_STAFF },
  { to: '/hierarchy', key: 'hierarchy', icon: TrendingUp,
    perm: PERMISSIONS.MODIFY_CONFIG },
  { to: '/analytics', key: 'analytics', icon: BarChart3,
    perm: PERMISSIONS.VIEW_ALL },
  { to: '/settings', key: 'settings', icon: SettingsIcon, perm: null },
] as const

const nav = computed(() => {
  const u = currentUser.value
  if (!u) return ALL_NAV.filter((n) => n.perm === null)
  return ALL_NAV.filter(
    (n) => n.perm === null || u.permissions.includes(n.perm),
  )
})

async function logout() {
  // E3h: server-side revoke (B2 from security PR #1) BEFORE clearing
  // local token, so the auth_sessions row is deleted while we still
  // have the bearer to authenticate the DELETE.
  try { await api.logout() } catch { /* graceful: log out locally anyway */ }
  clearToken()
  clearCurrentUser()
  router.push('/login')
}
const shell = () => hasToken() && route.path !== '/login'
watch(
  () => route.path,
  () => {
    menuOpen.value = false
    profileOpen.value = false
  }
)
</script>

<template>
  <div v-if="shell()" class="min-h-full flex">
    <!-- backdrop (mobile drawer) -->
    <div
      v-if="menuOpen"
      class="fixed inset-0 z-30 bg-black/50 md:hidden"
      @click="menuOpen = false"
    />
    <aside
      class="w-60 shrink-0 border-r bg-card flex flex-col z-40 fixed inset-y-0 left-0 transition-transform md:static md:translate-x-0"
      :class="menuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"
    >
      <div class="h-16 flex items-center gap-2 px-5 border-b">
        <Building2 class="h-6 w-6 text-primary" />
        <span class="font-bold text-lg">AIBuildCare</span>
        <button
          class="ml-auto md:hidden h-9 w-9 inline-flex items-center justify-center rounded-md hover:bg-secondary"
          @click="menuOpen = false"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
      <nav class="flex-1 p-3 space-y-1">
        <RouterLink
          v-for="n in nav"
          :key="n.to"
          :to="n.to"
          class="flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors"
          :class="
            route.path === n.to
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
          "
        >
          <component :is="n.icon" class="h-5 w-5" />
          {{ t(n.key) }}
        </RouterLink>
      </nav>
      <div class="p-3 border-t">
        <button
          class="flex w-full items-center gap-3 px-3 py-3 rounded-lg text-sm text-muted-foreground hover:bg-secondary hover:text-foreground"
          @click="logout"
        >
          <LogOut class="h-5 w-5" /> {{ t('logout') }}
        </button>
      </div>
    </aside>

    <div class="flex-1 flex flex-col min-w-0">
      <header
        class="h-16 border-b bg-card/80 backdrop-blur flex items-center justify-between px-3 md:px-6 sticky top-0 z-20"
      >
        <div class="flex items-center gap-2">
          <button
            class="md:hidden h-10 w-10 inline-flex items-center justify-center rounded-lg hover:bg-secondary"
            aria-label="Menu"
            @click="menuOpen = true"
          >
            <Menu class="h-5 w-5" />
          </button>
          <span class="font-semibold capitalize">
            {{ route.path === '/' ? t('overview') : t(route.path.slice(1).split('/')[0]) }}
          </span>
        </div>
        <div class="flex items-center gap-1">
          <button
            class="h-10 px-3 inline-flex items-center justify-center rounded-lg hover:bg-secondary text-sm font-semibold"
            :title="lang === 'en' ? 'Switch to हिंदी' : 'Switch to English'"
            @click="toggleLang"
          >
            {{ lang === 'en' ? 'EN' : 'हिं' }}
          </button>
          <button
            class="h-10 w-10 inline-flex items-center justify-center rounded-lg hover:bg-secondary"
            :title="isDark ? 'Light mode' : 'Dark mode'"
            @click="toggleTheme"
          >
            <Sun v-if="isDark" class="h-5 w-5" />
            <Moon v-else class="h-5 w-5" />
          </button>
          <div class="relative">
            <button
              class="h-10 w-10 inline-flex items-center justify-center rounded-full bg-primary text-primary-foreground font-bold text-sm"
              aria-label="Profile"
              @click="profileOpen = !profileOpen"
            >
              NA
            </button>
            <div
              v-if="profileOpen"
              class="absolute right-0 mt-2 w-52 rounded-lg border bg-card shadow-lg py-1 z-30"
            >
              <div class="px-4 py-2 border-b">
                <p class="font-semibold text-sm">Nataraj (Admin)</p>
                <p class="text-xs text-muted-foreground">
                  admin@aibuildcare.app
                </p>
              </div>
              <button
                class="w-full flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-secondary"
                @click="router.push('/settings')"
              >
                <User class="h-4 w-4" /> {{ t('profile') }}
              </button>
              <button
                class="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-muted-foreground"
                disabled
              >
                <HelpCircle class="h-4 w-4" /> {{ t('help') }}
              </button>
              <div class="border-t my-1" />
              <button
                class="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-destructive hover:bg-secondary"
                @click="logout"
              >
                <LogOut class="h-4 w-4" /> {{ t('logout') }}
              </button>
            </div>
          </div>
        </div>
      </header>
      <main class="flex-1 p-4 md:p-6 max-w-6xl w-full mx-auto">
        <RouterView />
      </main>
    </div>
  </div>

  <RouterView v-else />

  <Toaster />
</template>
