<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Users, Star, CheckCircle2, Gauge } from 'lucide-vue-next'
import { api, type ContractorPerf, type AnalyticsSummary } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'

const router = useRouter()
const rows = ref<ContractorPerf[]>([])
const sum = ref<AnalyticsSummary | null>(null)
const loading = ref(true)

onMounted(async () => {
  const [perf, s] = await Promise.all([
    api.contractorPerformance(),
    api.analyticsSummary().catch(() => null),
  ])
  perf.sort((a, b) => (b.average_rating ?? 0) - (a.average_rating ?? 0))
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

    <!-- contractor cards (no table) -->
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <Card v-for="c in rows" :key="c.contractor_id">
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
      <p v-if="!rows.length" class="text-muted-foreground">
        No contractor activity yet
      </p>
    </div>
  </div>
</template>
