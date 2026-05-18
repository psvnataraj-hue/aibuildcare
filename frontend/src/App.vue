<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { clearToken, hasToken } from './api'

const route = useRoute()
const router = useRouter()

function logout() {
  clearToken()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-full">
    <header
      v-if="hasToken() && route.path !== '/login'"
      class="bg-brand text-white shadow"
    >
      <div
        class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6 flex-wrap"
      >
        <span class="font-bold text-lg">AIBuildCare</span>
        <nav class="flex gap-4 text-sm">
          <RouterLink to="/" class="hover:underline">Dashboard</RouterLink>
          <RouterLink to="/complaints" class="hover:underline"
            >Complaints</RouterLink
          >
          <RouterLink to="/contractors" class="hover:underline"
            >Contractors</RouterLink
          >
        </nav>
        <button class="ml-auto text-sm hover:underline" @click="logout">
          Logout
        </button>
      </div>
    </header>
    <main class="max-w-6xl mx-auto p-4">
      <RouterView />
    </main>
  </div>
</template>
