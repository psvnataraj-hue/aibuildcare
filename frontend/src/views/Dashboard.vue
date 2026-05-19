<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Inbox, Activity, CheckCircle2, AlertTriangle, Plus } from 'lucide-vue-next'
import { api, openWS, type Complaint } from '../api'
import Card from '../components/ui/Card.vue'
import ComplaintCard from '../components/ComplaintCard.vue'
import Spinner from '../components/ui/Spinner.vue'

const router = useRouter()
const all = ref<Complaint[]>([])
const loading = ref(true)
let ws: WebSocket | null = null

const OPEN = ['received', 'acknowledged', 'assigned']
function isOverdue(c: Complaint) {
  if (['resolved', 'closed'].includes(c.status)) return false
  if (c.estimated_completion_date)
    return new Date(c.estimated_completion_date).getTime() < Date.now()
  return Date.now() - new Date(c.created_at).getTime() > 3 * 86400000
}

const stats = computed(() => ({
  open: all.value.filter((c) => OPEN.includes(c.status)).length,
  in_progress: all.value.filter((c) => c.status === 'in_progress').length,
  done: all.value.filter((c) =>
    ['resolved', 'closed'].includes(c.status)
  ).length,
  overdue: all.value.filter(isOverdue).length,
}))
const recent = computed(() => all.value.slice(0, 8))

const cards = computed(() => [
  { key: 'open', label: 'Open · खुली', n: stats.value.open,
    icon: Inbox, cls: 'text-amber-600', q: 'received' },
  { key: 'ip', label: 'In Progress · चालू', n: stats.value.in_progress,
    icon: Activity, cls: 'text-sky-600', q: 'in_progress' },
  { key: 'done', label: 'Completed · पूरा', n: stats.value.done,
    icon: CheckCircle2, cls: 'text-emerald-600', q: 'resolved' },
  { key: 'over', label: 'Overdue · विलंबित', n: stats.value.overdue,
    icon: AlertTriangle, cls: 'text-destructive', q: '' },
])

async function load() {
  all.value = await api.listComplaints('', '', 'created_at')
  loading.value = false
}
onMounted(() => {
  load()
  ws = openWS(() => load())
})
onUnmounted(() => ws?.close())
</script>

<template>
  <Spinner v-if="loading">Loading…</Spinner>
  <div v-else class="space-y-6">
    <h1 class="text-xl font-bold">
      Overview · <span class="text-muted-foreground">अवलोकन</span>
    </h1>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <button
        v-for="card in cards"
        :key="card.key"
        class="text-left"
        @click="router.push(card.q ? `/complaints?status=${card.q}` : '/complaints')"
      >
        <Card hover>
          <div class="flex items-start justify-between">
            <div>
              <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {{ card.label }}
              </p>
              <p class="text-4xl font-extrabold mt-2" :class="card.cls">
                {{ card.n }}
              </p>
            </div>
            <component :is="card.icon" class="h-7 w-7" :class="card.cls" />
          </div>
        </Card>
      </button>
    </div>

    <div class="flex items-center justify-between">
      <h2 class="font-semibold">Recent complaints · हाल की शिकायतें</h2>
      <button
        class="inline-flex items-center gap-1 h-10 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
        @click="router.push('/complaints')"
      >
        <Plus class="h-4 w-4" /> New · नई
      </button>
    </div>

    <div v-if="recent.length" class="grid sm:grid-cols-2 gap-3">
      <ComplaintCard v-for="c in recent" :key="c.id" :c="c" />
    </div>
    <p v-else class="text-muted-foreground">No complaints yet · कोई शिकायत नहीं</p>
  </div>
</template>
