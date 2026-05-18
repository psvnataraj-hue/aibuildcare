<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api, openWS } from '../api'

const stats = ref({ total: 0, open: 0, urgent_open: 0, by_status: {} as Record<string, number> })
const loading = ref(true)
let ws: WebSocket | null = null

async function load() {
  stats.value = await api.analytics()
  loading.value = false
}

onMounted(() => {
  load()
  ws = openWS(() => load())
})
onUnmounted(() => ws?.close())
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">Overview</h1>
    <div v-if="loading" class="text-slate-500">Loading...</div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="bg-white rounded-xl shadow p-6">
        <div class="text-sm text-slate-500">Total complaints</div>
        <div class="text-4xl font-bold mt-2">{{ stats.total }}</div>
      </div>
      <div class="bg-white rounded-xl shadow p-6">
        <div class="text-sm text-slate-500">Open</div>
        <div class="text-4xl font-bold mt-2 text-amber-600">
          {{ stats.open }}
        </div>
      </div>
      <div class="bg-white rounded-xl shadow p-6">
        <div class="text-sm text-slate-500">Urgent &amp; open</div>
        <div class="text-4xl font-bold mt-2 text-red-600">
          {{ stats.urgent_open }}
        </div>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow p-6 mt-6">
      <h2 class="font-semibold mb-3">By status</h2>
      <div class="flex flex-wrap gap-3">
        <span
          v-for="(n, s) in stats.by_status"
          :key="s"
          class="px-3 py-1 rounded-full bg-slate-100 text-sm"
        >
          {{ s }}: <strong>{{ n }}</strong>
        </span>
        <span
          v-if="!Object.keys(stats.by_status).length"
          class="text-slate-400 text-sm"
          >No complaints yet</span
        >
      </div>
    </div>
  </div>
</template>
