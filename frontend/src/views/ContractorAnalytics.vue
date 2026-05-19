<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Star } from 'lucide-vue-next'
import { api, type ContractorAnalytics } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'

const route = useRoute()
const router = useRouter()
const a = ref<ContractorAnalytics | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    a.value = await api.contractorAnalytics(Number(route.params.id))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <Spinner v-if="loading">Loading…</Spinner>
  <div v-else-if="a" class="space-y-5">
    <button
      class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      @click="router.push('/contractors')"
    >
      <ArrowLeft class="h-4 w-4" /> Back · वापस
    </button>

    <div class="flex items-center gap-3 flex-wrap">
      <h1 class="text-2xl font-bold">{{ a.name }}</h1>
      <span
        class="inline-flex items-center gap-1 text-amber-500 font-semibold"
      >
        <Star class="h-5 w-5 fill-amber-400 text-amber-400" />
        {{ a.rating ?? '—' }}
      </span>
      <span
        class="text-xs px-2 py-0.5 rounded-full"
        :class="
          a.availability.status === 'online'
            ? 'bg-emerald-500/15 text-emerald-600'
            : 'bg-muted text-muted-foreground'
        "
        >{{ a.availability.status }}</span
      >
    </div>

    <!-- workload KPI cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Card>
        <p class="text-xs text-muted-foreground">Pending · लंबित</p>
        <p class="text-3xl font-bold mt-1 text-amber-600">
          {{ a.workload.pending_count }}
        </p>
      </Card>
      <Card>
        <p class="text-xs text-muted-foreground">In progress · चालू</p>
        <p class="text-3xl font-bold mt-1 text-sky-600">
          {{ a.workload.in_progress_count }}
        </p>
      </Card>
      <Card>
        <p class="text-xs text-muted-foreground">Completed · पूरा</p>
        <p class="text-3xl font-bold mt-1 text-emerald-600">
          {{ a.workload.completed_count }}
        </p>
      </Card>
      <Card>
        <p class="text-xs text-muted-foreground">Total · कुल</p>
        <p class="text-3xl font-bold mt-1">
          {{ a.workload.total_assigned }}
        </p>
      </Card>
    </div>

    <div class="grid sm:grid-cols-2 gap-3">
      <Card>
        <h2 class="font-semibold mb-2">Response time (hours)</h2>
        <p class="text-sm text-muted-foreground">
          Avg <strong class="text-foreground">{{ a.response_time.avg_hours ?? '—' }}</strong>
          · Min {{ a.response_time.min_hours ?? '—' }}
          · Max {{ a.response_time.max_hours ?? '—' }}
        </p>
      </Card>
      <Card>
        <h2 class="font-semibold mb-2">Resolution time (hours)</h2>
        <p class="text-sm text-muted-foreground">
          Avg <strong class="text-foreground">{{ a.resolution_time.avg_hours ?? '—' }}</strong>
          · Min {{ a.resolution_time.min_hours ?? '—' }}
          · Max {{ a.resolution_time.max_hours ?? '—' }}
        </p>
      </Card>
    </div>

    <Card>
      <h2 class="font-semibold mb-3">Category specialization</h2>
      <div
        v-if="Object.keys(a.category_specialization).length"
        class="space-y-2"
      >
        <div
          v-for="(v, k) in a.category_specialization"
          :key="k"
        >
          <div class="flex justify-between text-sm mb-1">
            <span>{{ k }}</span>
            <span class="text-muted-foreground"
              >{{ v.completed }} done · {{ v.pct_of_total }}%</span
            >
          </div>
          <div class="h-2 rounded-full bg-secondary overflow-hidden">
            <div
              class="h-full rounded-full bg-primary"
              :style="{ width: v.pct_of_total + '%' }"
            />
          </div>
        </div>
      </div>
      <p v-else class="text-sm text-muted-foreground">No jobs yet</p>
    </Card>
  </div>
  <p v-else class="text-muted-foreground">Contractor not found</p>
</template>
