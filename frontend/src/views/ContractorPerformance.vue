<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Users, Star, CheckCircle2, Gauge, XCircle } from 'lucide-vue-next'
import { api, type ContractorPerf, type AnalyticsSummary } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'

const route = useRoute()
const router = useRouter()
const rows = ref<ContractorPerf[]>([])
const sum = ref<AnalyticsSummary | null>(null)
const loading = ref(true)

const sort = ref((route.query.sort as string) || 'rating')
const fStatus = ref((route.query.status as string) || '')
const fCat = ref((route.query.category as string) || '')
const fRating = ref((route.query.rating as string) || '')

const CATS = [
  'AC/Cooling', 'Plumbing', 'Electrical', 'Lift', 'Civil', 'Security',
]
const CAP = 10
const openJobs = (c: ContractorPerf) =>
  Math.max(0, c.assigned_count - c.resolved_count)
const statusOf = (c: ContractorPerf) =>
  openJobs(c) >= CAP ? 'overloaded'
  : openJobs(c) >= Math.ceil(CAP * 0.7) ? 'at_capacity'
  : 'available'

const view = computed(() => {
  let v = [...rows.value]
  if (fStatus.value) v = v.filter((c) => statusOf(c) === fStatus.value)
  if (fCat.value)
    v = v.filter((c) =>
      (c.specialty || '').toLowerCase().includes(fCat.value.toLowerCase())
    )
  if (fRating.value)
    v = v.filter((c) => (c.average_rating ?? 0) >= Number(fRating.value))
  const by: Record<string, (a: ContractorPerf, b: ContractorPerf) => number> =
    {
      rating: (a, b) => (b.average_rating ?? 0) - (a.average_rating ?? 0),
      workload: (a, b) => openJobs(b) - openJobs(a),
      response: (a, b) =>
        (a.avg_response_time_hours ?? 1e9) -
        (b.avg_response_time_hours ?? 1e9),
      completion: (a, b) => b.completion_rate - a.completion_rate,
    }
  return v.sort(by[sort.value] || by.rating)
})

const activeFilters = computed(() =>
  [
    fStatus.value && `Status: ${fStatus.value}`,
    fCat.value && `Category: ${fCat.value}`,
    fRating.value && `Rating ≥ ${fRating.value}`,
  ].filter(Boolean) as string[]
)
function clearFilters() {
  fStatus.value = ''
  fCat.value = ''
  fRating.value = ''
  sort.value = 'rating'
}
watch([sort, fStatus, fCat, fRating], () => {
  router.replace({
    query: {
      sort: sort.value,
      ...(fStatus.value ? { status: fStatus.value } : {}),
      ...(fCat.value ? { category: fCat.value } : {}),
      ...(fRating.value ? { rating: fRating.value } : {}),
    },
  })
})

onMounted(async () => {
  const [perf, s] = await Promise.all([
    api.contractorPerformance(),
    api.analyticsSummary().catch(() => null),
  ])
  rows.value = perf
  sum.value = s
  loading.value = false
})
</script>

<template>
  <Spinner v-if="loading">Loading…</Spinner>
  <div v-else class="space-y-5">
    <h1 class="text-xl font-bold">
      Contractors · <span class="text-muted-foreground">ठेकेदार</span>
    </h1>

    <!-- summary cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-muted-foreground">Total · कुल</p>
            <p class="text-2xl font-bold mt-1">
              {{ sum?.total_contractors ?? rows.length }}
            </p>
          </div>
          <Users class="h-5 w-5 text-sky-500" />
        </div>
      </Card>
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-muted-foreground">Avg rating · रेटिंग</p>
            <p class="text-2xl font-bold mt-1">
              {{ sum?.avg_rating_across_all ?? '—' }}
            </p>
          </div>
          <Star class="h-5 w-5 fill-amber-400 text-amber-400" />
        </div>
      </Card>
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-muted-foreground">Available · उपलब्ध</p>
            <p class="text-2xl font-bold mt-1 text-emerald-600">
              {{ sum?.workload_distribution.available ?? '—' }}
            </p>
          </div>
          <CheckCircle2 class="h-5 w-5 text-emerald-500" />
        </div>
      </Card>
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-muted-foreground">At capacity · व्यस्त</p>
            <p class="text-2xl font-bold mt-1 text-amber-600">
              {{ sum?.workload_distribution.at_capacity ?? '—' }}
            </p>
          </div>
          <Gauge class="h-5 w-5 text-amber-500" />
        </div>
      </Card>
    </div>

    <!-- sort + filters -->
    <div class="flex flex-wrap gap-2 items-center">
      <select v-model="sort" class="h-11 bg-card border rounded-lg px-3 text-sm">
        <option value="rating">Sort: Rating ↓</option>
        <option value="workload">Sort: Most pending</option>
        <option value="response">Sort: Fastest response</option>
        <option value="completion">Sort: Completion %</option>
      </select>
      <select v-model="fStatus" class="h-11 bg-card border rounded-lg px-3 text-sm">
        <option value="">All status</option>
        <option value="available">Available</option>
        <option value="at_capacity">At capacity</option>
        <option value="overloaded">Overloaded</option>
      </select>
      <select v-model="fCat" class="h-11 bg-card border rounded-lg px-3 text-sm">
        <option value="">All categories</option>
        <option v-for="c in CATS" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="fRating" class="h-11 bg-card border rounded-lg px-3 text-sm">
        <option value="">All ratings</option>
        <option value="5">5.0 ⭐</option>
        <option value="4.5">4.5 ⭐+</option>
        <option value="4">4.0 ⭐+</option>
        <option value="3.5">3.5 ⭐+</option>
      </select>
      <button
        v-if="activeFilters.length"
        class="h-11 px-3 inline-flex items-center gap-1 rounded-lg border text-sm hover:bg-secondary"
        @click="clearFilters"
      >
        <XCircle class="h-4 w-4" /> Clear
      </button>
    </div>
    <div v-if="activeFilters.length" class="flex flex-wrap gap-2">
      <span
        v-for="f in activeFilters"
        :key="f"
        class="text-xs px-2 py-1 rounded-full bg-primary/15 text-primary font-medium"
        >{{ f }}</span
      >
    </div>

    <!-- contractor cards (no table) -->
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <Card v-for="c in view" :key="c.contractor_id">
        <div class="flex items-start justify-between">
          <div class="min-w-0">
            <p class="font-semibold truncate">{{ c.name }}</p>
            <p class="text-xs text-muted-foreground truncate">
              {{ c.specialty }}
            </p>
          </div>
          <span
            class="inline-flex items-center gap-1 text-amber-500 font-semibold shrink-0"
          >
            <Star class="h-4 w-4 fill-amber-400 text-amber-400" />
            {{ c.average_rating ?? '—' }}
          </span>
        </div>
        <div class="grid grid-cols-3 gap-2 mt-3 text-center">
          <div>
            <p class="text-lg font-bold">{{ c.assigned_count }}</p>
            <p class="text-[11px] text-muted-foreground">Assigned</p>
          </div>
          <div>
            <p class="text-lg font-bold text-emerald-600">
              {{ c.resolved_count }}
            </p>
            <p class="text-[11px] text-muted-foreground">Done · पूरा</p>
          </div>
          <div>
            <p class="text-lg font-bold">
              {{ c.avg_response_time_hours ?? '—' }}
            </p>
            <p class="text-[11px] text-muted-foreground">Resp (h)</p>
          </div>
        </div>
        <button
          class="mt-4 w-full h-12 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90"
          @click="router.push(`/contractors/${c.contractor_id}`)"
        >
          View Details · विवरण
        </button>
      </Card>
      <p v-if="!view.length" class="text-muted-foreground">
        No contractors match
      </p>
    </div>
  </div>
</template>
