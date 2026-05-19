<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Users, Star, CheckCircle2, Gauge } from 'lucide-vue-next'
import { api, type AnalyticsSummary } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'

const router = useRouter()
const s = ref<AnalyticsSummary | null>(null)
const loading = ref(true)
onMounted(async () => {
  try {
    s.value = await api.analyticsSummary()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <Spinner v-if="loading">Loading…</Spinner>
  <div v-else-if="s" class="space-y-5">
    <h1 class="text-xl font-bold">
      Analytics · <span class="text-muted-foreground">विश्लेषण</span>
    </h1>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-muted-foreground">Contractors · ठेकेदार</p>
            <p class="text-2xl font-bold mt-1">{{ s.total_contractors }}</p>
          </div>
          <Users class="h-5 w-5 text-sky-500" />
        </div>
      </Card>
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-muted-foreground">Avg rating · रेटिंग</p>
            <p class="text-2xl font-bold mt-1">
              {{ s.avg_rating_across_all ?? '—' }}
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
              {{ s.workload_distribution.available }}
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
              {{ s.workload_distribution.at_capacity }}
            </p>
          </div>
          <Gauge class="h-5 w-5 text-amber-500" />
        </div>
      </Card>
    </div>

    <Card>
      <h2 class="font-semibold mb-3">Top performers · सर्वश्रेष्ठ</h2>
      <div class="divide-y">
        <div
          v-for="(t, i) in s.top_performers"
          :key="i"
          class="flex items-center justify-between py-2.5"
        >
          <span class="font-medium">{{ i + 1 }}. {{ t.name }}</span>
          <span class="flex items-center gap-3 text-sm">
            <span class="inline-flex items-center gap-1 text-amber-500">
              <Star class="h-4 w-4 fill-amber-400 text-amber-400" />{{
                t.rating ?? '—'
              }}
            </span>
            <span class="text-muted-foreground"
              >{{ t.completed }} done</span
            >
          </span>
        </div>
        <p
          v-if="!s.top_performers.length"
          class="text-sm text-muted-foreground py-2"
        >
          No data yet
        </p>
      </div>
    </Card>

    <Card v-if="Object.keys(s.category_performance).length">
      <h2 class="font-semibold mb-3">By category · श्रेणी अनुसार</h2>
      <div class="space-y-2 text-sm">
        <div
          v-for="(v, k) in s.category_performance"
          :key="k"
          class="flex justify-between"
        >
          <span>{{ k }}</span>
          <span class="text-muted-foreground">
            Resp {{ v.avg_response_time ?? '—' }}h · Resolve
            {{ v.avg_resolution_time ?? '—' }}h
          </span>
        </div>
      </div>
    </Card>

    <button
      class="h-12 px-5 rounded-lg border font-medium hover:bg-secondary"
      @click="router.push('/contractors')"
    >
      View all contractors · सभी ठेकेदार
    </button>
  </div>
</template>
