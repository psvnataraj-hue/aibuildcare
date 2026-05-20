<script setup lang="ts">
import { ref, watch } from 'vue'
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
import { clearToken, hasToken } from './api'
import { isDark, toggleTheme } from './lib/theme'
import { lang, t, toggleLang } from './lib/i18n'
import Toaster from './components/ui/Toaster.vue'

const route = useRoute()
const router = useRouter()
const menuOpen = ref(false)
const profileOpen = ref(false)

const nav = [
  { to: '/', key: 'dashboard', icon: LayoutDashboard },
  { to: '/complaints', key: 'complaints', icon: ClipboardList },
  { to: '/performance', key: 'contractors', icon: Wrench },
  { to: '/staff', key: 'staff', icon: UsersIcon },
  { to: '/hierarchy', key: 'hierarchy', icon: TrendingUp },
  { to: '/analytics', key: 'analytics', icon: BarChart3 },
  { to: '/settings', key: 'settings', icon: SettingsIcon },
]

function logout() {
  clearToken()
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
