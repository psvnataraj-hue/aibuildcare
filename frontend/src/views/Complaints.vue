<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Search, Plus, Loader2 } from 'lucide-vue-next'
import { api, openWS, type Complaint } from '../api'
import Card from '../components/ui/Card.vue'
import ComplaintCard from '../components/ComplaintCard.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'

const route = useRoute()
const items = ref<Complaint[]>([])
const q = ref('')
const status = ref((route.query.status as string) || '')
const category = ref('')
const priority = ref('')
const dateRange = ref('all')
const newText = ref('')
const creating = ref(false)
const loading = ref(true)
let ws: WebSocket | null = null

const CATS = [
  'AC/Cooling', 'Plumbing', 'Electrical', 'Elevator',
  'Housekeeping', 'Security', 'Other',
]

async function load() {
  items.value = await api.listComplaints(q.value, status.value, 'created_at')
  loading.value = false
}
async function create() {
  if (!newText.value.trim()) return
  creating.value = true
  try {
    const c = await api.createComplaint(newText.value)
    newText.value = ''
    await load()
    toast(`Logged ${c.ticket_number} ✓`)
  } catch (e: any) {
    toast(e.message || 'Failed to log', 'error')
  } finally {
    creating.value = false
  }
}

const filtered = computed(() =>
  items.value.filter((c) => {
    if (category.value && c.category !== category.value) return false
    if (priority.value && c.priority !== priority.value) return false
    if (dateRange.value !== 'all') {
      const days = dateRange.value === '7' ? 7 : 30
      if (
        Date.now() - new Date(c.created_at).getTime() >
        days * 86400000
      )
        return false
    }
    return true
  })
)

const page = ref(Number(route.query.page) || 1)
const perPage = ref(Number(route.query.per_page) || 10)
const totalPages = computed(() =>
  Math.max(1, Math.ceil(filtered.value.length / perPage.value))
)
const paged = computed(() => {
  if (page.value > totalPages.value) page.value = 1
  const s = (page.value - 1) * perPage.value
  return filtered.value.slice(s, s + perPage.value)
})
const rangeText = computed(() => {
  const n = filtered.value.length
  if (!n) return '0'
  const s = (page.value - 1) * perPage.value + 1
  return `${s}-${Math.min(s + perPage.value - 1, n)} of ${n}`
})

onMounted(() => {
  load()
  ws = openWS(() => load())
})
onUnmounted(() => ws?.close())
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-xl font-bold">
      All Complaints · <span class="text-muted-foreground">सभी शिकायतें</span>
    </h1>

    <Card>
      <div class="flex gap-2 flex-wrap">
        <input
          v-model="newText"
          placeholder="New complaint · नई शिकायत (e.g. '5B mein AC kharab hai urgent')"
          class="flex-1 min-w-[220px] h-12 bg-background border rounded-lg px-3 focus:outline-none focus:ring-2 focus:ring-ring"
          @keyup.enter="create"
        />
        <button
          :disabled="creating"
          class="inline-flex items-center gap-2 h-12 px-5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-60"
          @click="create"
        >
          <Loader2 v-if="creating" class="h-4 w-4 animate-spin" />
          <Plus v-else class="h-4 w-4" />
          {{ creating ? 'Parsing…' : 'Add · जोड़ें' }}
        </button>
      </div>
    </Card>

    <div class="flex gap-2 flex-wrap items-center">
      <div class="relative flex-1 min-w-[180px]">
        <Search
          class="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <input
          v-model="q"
          placeholder="Search · खोजें"
          class="w-full h-11 bg-card border rounded-lg pl-9 pr-3 focus:outline-none focus:ring-2 focus:ring-ring"
          @keyup.enter="load"
        />
      </div>
      <select
        v-model="status"
        class="h-11 bg-card border rounded-lg px-3"
        @change="load"
      >
        <option value="">All status · सभी</option>
        <option>received</option>
        <option>acknowledged</option>
        <option>assigned</option>
        <option>in_progress</option>
        <option>resolved</option>
        <option>closed</option>
      </select>
      <select v-model="category" class="h-11 bg-card border rounded-lg px-3">
        <option value="">All categories</option>
        <option v-for="cat in CATS" :key="cat">{{ cat }}</option>
      </select>
      <select v-model="priority" class="h-11 bg-card border rounded-lg px-3">
        <option value="">All priority</option>
        <option>urgent</option>
        <option>high</option>
        <option>normal</option>
      </select>
      <select v-model="dateRange" class="h-11 bg-card border rounded-lg px-3">
        <option value="all">All time</option>
        <option value="7">Last 7 days</option>
        <option value="30">Last 30 days</option>
      </select>
    </div>

    <Spinner v-if="loading" />
    <template v-else-if="filtered.length">
      <div class="grid sm:grid-cols-2 gap-3">
        <ComplaintCard v-for="c in paged" :key="c.id" :c="c" />
      </div>
      <div
        class="flex items-center justify-between flex-wrap gap-3 pt-2 text-sm"
      >
        <span class="text-muted-foreground">Showing {{ rangeText }}</span>
        <div class="flex items-center gap-2">
          <select
            v-model.number="perPage"
            class="h-10 bg-card border rounded-lg px-2"
          >
            <option :value="10">10</option>
            <option :value="25">25</option>
            <option :value="50">50</option>
          </select>
          <button
            class="h-10 px-3 rounded-lg border disabled:opacity-40 hover:bg-secondary"
            :disabled="page <= 1"
            @click="page--"
          >
            Prev
          </button>
          <span class="px-2">{{ page }} / {{ totalPages }}</span>
          <button
            class="h-10 px-3 rounded-lg border disabled:opacity-40 hover:bg-secondary"
            :disabled="page >= totalPages"
            @click="page++"
          >
            Next
          </button>
        </div>
      </div>
    </template>
    <Card v-else>
      <p class="text-center text-muted-foreground py-6">
        No complaints match · कोई शिकायत नहीं
      </p>
    </Card>
  </div>
</template>
