<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'

const email = ref('admin@aibuildcare.app')
const password = ref('ChangeMe!2026')
const error = ref('')
const loading = ref(false)
const router = useRouter()

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const { access_token } = await api.login(email.value, password.value)
    setToken(access_token)
    router.push('/')
  } catch (e: any) {
    error.value = e.message || 'login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <form
      class="bg-white p-8 rounded-xl shadow-md w-full max-w-sm"
      @submit.prevent="submit"
    >
      <h1 class="text-2xl font-bold text-brand mb-1">AIBuildCare</h1>
      <p class="text-sm text-slate-500 mb-6">Staff sign in</p>

      <label class="block text-sm font-medium mb-1">Email</label>
      <input
        v-model="email"
        type="email"
        class="w-full border rounded px-3 py-2 mb-4"
        required
      />

      <label class="block text-sm font-medium mb-1">Password</label>
      <input
        v-model="password"
        type="password"
        class="w-full border rounded px-3 py-2 mb-4"
        required
      />

      <p v-if="error" class="text-red-600 text-sm mb-3">{{ error }}</p>

      <button
        :disabled="loading"
        class="w-full bg-brand hover:bg-brand-dark text-white py-2 rounded font-medium disabled:opacity-60"
      >
        {{ loading ? 'Signing in...' : 'Sign in' }}
      </button>
    </form>
  </div>
</template>
