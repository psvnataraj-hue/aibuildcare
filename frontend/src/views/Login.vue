<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Building2, Loader2 } from 'lucide-vue-next'
import { api, setToken } from '../api'
import { loadCurrentUser } from '../lib/currentUser'

const email = ref('admin@aibuildcare.app')
// Cleared 2026-05-21: previously prefilled with the leaked default
// "ChangeMe!2026" which no longer works in prod after PR #3.
const password = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const { access_token } = await api.login(email.value, password.value)
    setToken(access_token)
    // E3h: load identity + permissions before navigating so the nav
    // can render correctly on first paint (no flash of every-link).
    await loadCurrentUser()
    router.push('/')
  } catch (e: any) {
    error.value = e.message || 'login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <form
      class="bg-card text-card-foreground border rounded-lg shadow-lg w-full max-w-sm p-8"
      @submit.prevent="submit"
    >
      <div class="flex items-center gap-2 mb-1">
        <Building2 class="h-7 w-7 text-primary" />
        <h1 class="text-2xl font-bold">AIBuildCare</h1>
      </div>
      <p class="text-sm text-muted-foreground mb-6">Staff sign in</p>

      <label class="block text-sm font-medium mb-1">Email</label>
      <input
        v-model="email"
        type="email"
        class="w-full bg-background border rounded-md px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-ring"
        required
      />

      <label class="block text-sm font-medium mb-1">Password</label>
      <input
        v-model="password"
        type="password"
        class="w-full bg-background border rounded-md px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-ring"
        required
      />

      <p
        v-if="error"
        class="text-destructive text-sm mb-3 bg-destructive/10 rounded-md px-3 py-2"
      >
        {{ error }}
      </p>

      <button
        :disabled="loading"
        class="w-full bg-primary text-primary-foreground py-2 rounded-md font-medium hover:bg-primary/90 disabled:opacity-60 inline-flex items-center justify-center gap-2"
      >
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        {{ loading ? 'Signing in…' : 'Sign in' }}
      </button>
    </form>
  </div>
</template>
