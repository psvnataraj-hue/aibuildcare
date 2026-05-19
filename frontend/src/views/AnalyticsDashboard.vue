<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
} from 'chart.js'
import { Bar } from 'vue-chartjs'
import { Download } from 'lucide-vue-next'
import {
  api,
  type AnalyticsSummary,
  type Complaint,
  type ContractorPerf,
} from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'

ChartJS.register(
  Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale
)

const router = useRouter()
const loading = ref(true)
const s = ref<AnalyticsSummary | null>(null)
const complaints = ref<Complaint[]>([])
const perf = ref<ContractorPerf[]>([])
const tab = ref<'overview' | 'trends' | 'categories' | 'contractors'>(
  'overview'
)
const from = ref('')
const to = ref('')

onMounted(async () => {
  const [sm, cs, pf] = await Promise.all([
    api.analyticsSummary().catch(() => null),
    api.listComplaints('', '', 'created_at').catch(() => []),
    api.contractorPerformance().catch(() => []),
  ])
  s.value = sm
  complaints.value = cs
  perf.value = pf
  loading.value = false
})

const inRange = (c: Complaint) => {
  const t = new Date(c.created_at).getTime()
  if (from.value && t < new Date(from.value).getTime()) return false
  if (to.value && t > new Date(to.value).getTime() + 86400000) return false
  return true
}
const filtered = computed(() => complaints.value.filter(inRange))

function weekKey(d: string) {
  const dt = new Date(d)
  const onejan = new Date(dt.getFullYear(), 0, 1)
  const wk = Math.ceil(
    ((dt.getTime() - onejan.getTime()) / 86400000 + onejan.getDay() + 1) / 7
  )
  return `${dt.getFullYear()}-W${wk}`
}
const STATUSES = ['received', 'acknowledged', 'assigned', 'in_progress', 'resolved', 'closed']
const COLORS: Record<string, string> = {
  received: '#0ea5e9', acknowledged: '#6366f1', assigned: '#8b5cf6',
  in_progress: '#f59e0b', resolved: '#10b981', closed: '#64748b',
}
const chartData = computed(() => {
  const weeks: string[] = []
  const map: Record<string, Record<string, number>> = {}
  for (const c of filtered.value) {
    const w = weekKey(c.created_at)
    if (!weeks.includes(w)) weeks.push(w)
    map[w] = map[w] || {}
    map[w][c.status] = (map[w][c.status] || 0) + 1
  }
  weeks.sort()
  return {
    labels: weeks,
    datasets: STATUSES.map((st) => ({
      label: st.replace('_', ' '),
      backgroundColor: COLORS[st],
      data: weeks.map((w) => map[w]?.[st] || 0),
    })),
  }
})
const chartOpts = {
  responsive: true,
  maintainAspectRatio: false,
  scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
}

function dl(name: string, rows: (string | number)[][]) {
  const csv = rows
    .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  a.download = name
  a.click()
  toast('CSV exported ✓')
}
function exportCsv() {
  const d = new Date().toISOString().slice(0, 10)
  if (tab.value === 'contractors') {
    dl(`aibuildcare-contractors-${d}.csv`, [
      ['Name', 'Specialty', 'Rating', 'Assigned', 'Resolved', 'Resp(h)', 'Completion%'],
      ...perf.value.map((p) => [
        p.name, p.specialty, p.average_rating ?? '', p.assigned_count,
        p.resolved_count, p.avg_response_time_hours ?? '',
        p.completion_rate,
      ]),
    ])
  } else if (tab.value === 'categories' && s.value) {
    dl(`aibuildcare-categories-${d}.csv`, [
      ['Category', 'Avg response (h)', 'Avg resolution (h)'],
      ...Object.entries(s.value.category_performance).map(([k, v]) => [
        k, v.avg_response_time ?? '', v.avg_resolution_time ?? '',
      ]),
    ])
  } else {
    dl(`aibuildcare-complaints-${d}.csv`, [
      ['Ticket', 'Unit', 'Category', 'Priority', 'Status', 'Created'],
      ...filtered.value.map((c) => [
        c.ticket_number, c.unit_number ?? '', c.category ?? '',
        c.priority, c.status, c.created_at,
      ]),
    ])
  }
}

const TABS = [
  ['overview', 'Overview'],
  ['trends', 'Trends'],
  ['categories', 'Categories'],
  ['contractors', 'Contractors'],
] as const
</script>

<template>
  <Spinner v-if="loading">Loading…</Spinner>
  <div v-else class="space-y-5">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <h1 class="text-xl font-bold">
        Analytics · <span class="text-muted-foreground">विश्लेषण</span>
      </h1>
      <button
        class="inline-flex items-center gap-2 h-10 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:brightness-110"
        @click="exportCsv"
      >
        <Download class="h-4 w-4" /> Export CSV
      </button>
    </div>

    <div class="flex items-center gap-2 flex-wrap text-sm">
      <span class="text-muted-foreground">Date range:</span>
      <input type="date" v-model="from" class="h-10 bg-card border rounded-lg px-2" />
      <span>→</span>
      <input type="date" v-model="to" class="h-10 bg-card border rounded-lg px-2" />
      <button
        v-if="from || to"
        class="h-10 px-3 rounded-lg border hover:bg-secondary"
        @click="from = ''; to = ''"
      >
        Clear
      </button>
    </div>

    <div class="flex gap-1 border-b">
      <button
        v-for="[k, lbl] in TABS"
        :key="k"
        class="px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors"
        :class="
          tab === k
            ? 'border-primary text-primary'
            : 'border-transparent text-muted-foreground hover:text-foreground'
        "
        @click="tab = k"
      >
        {{ lbl }}
      </button>
    </div>

    <!-- OVERVIEW -->
    <div v-if="tab === 'overview' && s" class="space-y-4">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card><p class="text-xs text-muted-foreground">Contractors</p>
          <p class="text-3xl font-bold mt-1">{{ s.total_contractors }}</p></Card>
        <Card><p class="text-xs text-muted-foreground">Avg rating</p>
          <p class="text-3xl font-bold mt-1">{{ s.avg_rating_across_all ?? '—' }}</p></Card>
        <Card><p class="text-xs text-muted-foreground">Available</p>
          <p class="text-3xl font-bold mt-1 text-emerald-600">{{ s.workload_distribution.available }}</p></Card>
        <Card><p class="text-xs text-muted-foreground">At capacity</p>
          <p class="text-3xl font-bold mt-1 text-amber-600">{{ s.workload_distribution.at_capacity }}</p></Card>
      </div>
      <Card>
        <h2 class="font-semibold mb-3">Top performers</h2>
        <div class="divide-y">
          <div v-for="(t, i) in s.top_performers" :key="i"
               class="flex justify-between py-2.5 text-sm">
            <span>{{ i + 1 }}. {{ t.name }}</span>
            <span class="text-muted-foreground">⭐ {{ t.rating ?? '—' }} · {{ t.completed }} done</span>
          </div>
        </div>
      </Card>
    </div>

    <!-- TRENDS -->
    <Card v-else-if="tab === 'trends'">
      <h2 class="font-semibold mb-3">Complaints over time (by status)</h2>
      <div v-if="chartData.labels.length" class="h-72">
        <Bar :data="chartData" :options="chartOpts" />
      </div>
      <p v-else class="text-sm text-muted-foreground py-8 text-center">
        Not enough data yet — need more complaints in this date range.
      </p>
    </Card>

    <!-- CATEGORIES -->
    <Card v-else-if="tab === 'categories' && s">
      <h2 class="font-semibold mb-3">Category performance</h2>
      <div class="space-y-2 text-sm">
        <div
          v-for="(v, k) in s.category_performance"
          :key="k"
          class="flex justify-between border-b last:border-0 py-2"
        >
          <span class="font-medium">{{ k }}</span>
          <span class="text-muted-foreground">
            Resp {{ v.avg_response_time ?? '—' }}h · Resolve
            {{ v.avg_resolution_time ?? '—' }}h
          </span>
        </div>
        <p v-if="!Object.keys(s.category_performance).length"
           class="text-muted-foreground py-4">No data yet</p>
      </div>
    </Card>

    <!-- CONTRACTORS -->
    <div v-else-if="tab === 'contractors'" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <Card
        v-for="c in [...perf].sort((a,b)=>(b.average_rating??0)-(a.average_rating??0))"
        :key="c.contractor_id"
        hover
        @click="router.push(`/contractors/${c.contractor_id}`)"
      >
        <div class="flex justify-between">
          <span class="font-semibold truncate">{{ c.name }}</span>
          <span class="text-amber-500 font-semibold">⭐ {{ c.average_rating ?? '—' }}</span>
        </div>
        <p class="text-xs text-muted-foreground mt-1">
          {{ c.assigned_count }} assigned · {{ c.resolved_count }} done ·
          {{ c.completion_rate }}%
        </p>
      </Card>
    </div>
  </div>
</template>
