<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Inbox,
  AlertTriangle,
  CheckCircle2,
  Activity,
} from 'lucide-vue-next'
import { api, openWS, type Complaint } from '../api'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Spinner from '../components/ui/Spinner.vue'

const router = useRouter()
const stats = ref({
  total: 0,
  open: 0,
  urgent_open: 0,
  by_status: {} as Record<string, number>,
})
const recent = ref<Complaint[]>([])
const loading = ref(true)
let ws: WebSocket | null = null

async function load() {
  const [s, list] = await Promise.all([
    api.analytics(),
    api.listComplaints('', '', 'created_at'),
  ])
  stats.value = s
  recent.value = list.slice(0, 6)
  loading.value = false
}

const cards = computed(() => [
  { label: 'Total complaints', value: stats.value.total, icon: Inbox,
    tint: 'text-sky-500' },
  { label: 'Open', value: stats.value.open, icon: Activity,
    tint: 'text-amber-500' },
  { label: 'Urgent & open', value: stats.value.urgent_open,
    icon: AlertTriangle, tint: 'text-destructive' },
  { label: 'Resolved', value: stats.value.by_status?.resolved || 0,
    icon: CheckCircle2, tint: 'text-emerald-500' },
])

const chart = computed(() => {
  const e = Object.entries(stats.value.by_status || {})
  const max = Math.max(1, ...e.map(([, n]) => n))
  return e.map(([k, n]) => ({ k, n, pct: Math.round((n / max) * 100) }))
})

onMounted(() => {
  load()
  ws = openWS(() => load())
})
onUnmounted(() => ws?.close())
</script>

<template>
  <Spinner v-if="loading">Loading dashboard…</Spinner>
  <div v-else class="space-y-6">
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <Card v-for="c in cards" :key="c.label">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-sm text-muted-foreground">{{ c.label }}</p>
            <p class="text-3xl font-bold mt-1">{{ c.value }}</p>
          </div>
          <component :is="c.icon" class="h-6 w-6" :class="c.tint" />
        </div>
      </Card>
    </div>

    <div class="grid lg:grid-cols-5 gap-6">
      <Card class="lg:col-span-2">
        <h2 class="font-semibold mb-4">Complaints by status</h2>
        <div v-if="chart.length" class="space-y-3">
          <div v-for="row in chart" :key="row.k">
            <div class="flex justify-between text-sm mb-1">
              <span class="capitalize text-muted-foreground">{{
                row.k.replace('_', ' ')
              }}</span>
              <span class="font-medium">{{ row.n }}</span>
            </div>
            <div class="h-2 rounded-full bg-secondary overflow-hidden">
              <div
                class="h-full rounded-full bg-primary transition-all"
                :style="{ width: row.pct + '%' }"
              />
            </div>
          </div>
        </div>
        <p v-else class="text-sm text-muted-foreground">No data yet</p>
      </Card>

      <Card class="lg:col-span-3">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold">Recent complaints</h2>
          <button
            class="text-sm text-primary hover:underline"
            @click="router.push('/complaints')"
          >
            View all
          </button>
        </div>
        <div v-if="recent.length" class="divide-y">
          <button
            v-for="r in recent"
            :key="r.id"
            class="w-full flex items-center gap-3 py-3 text-left hover:bg-secondary/50 rounded-md px-2 -mx-2"
            @click="router.push(`/complaints/${r.id}`)"
          >
            <span class="font-mono text-xs text-muted-foreground w-28 shrink-0"
              >{{ r.ticket_number }}</span
            >
            <span class="flex-1 truncate text-sm">{{
              r.unit_number || '—'
            }} · {{ r.category }}</span>
            <Badge :variant="r.priority">{{ r.priority }}</Badge>
            <Badge :variant="r.status">{{ r.status.replace('_', ' ') }}</Badge>
          </button>
        </div>
        <p v-else class="text-sm text-muted-foreground">No complaints yet</p>
      </Card>
    </div>
  </div>
</template>
