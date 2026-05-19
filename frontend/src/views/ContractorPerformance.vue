<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Users,
  ClipboardCheck,
  CheckCircle2,
  Star,
} from 'lucide-vue-next'
import { api, type ContractorPerf } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'
import DataTable from '../components/ui/DataTable.vue'

const rows = ref<ContractorPerf[]>([])
const loading = ref(true)

onMounted(async () => {
  const data = await api.contractorPerformance()
  // default: highest rating first
  data.sort((a, b) => (b.average_rating ?? 0) - (a.average_rating ?? 0))
  rows.value = data
  loading.value = false
})

const totals = computed(() => ({
  contractors: rows.value.length,
  assigned: rows.value.reduce((a, r) => a + r.assigned_count, 0),
  resolved: rows.value.reduce((a, r) => a + r.resolved_count, 0),
}))

const COLUMNS = [
  { key: 'name', label: 'Contractor' },
  { key: 'specialty', label: 'Specialty' },
  { key: 'average_rating', label: 'Rating' },
  { key: 'assigned_count', label: 'Assigned' },
  { key: 'resolved_count', label: 'Resolved' },
  { key: 'avg_response_time_hours', label: 'Avg response (h)' },
  { key: 'avg_resolution_time_hours', label: 'Avg resolution (h)' },
  { key: 'completion_rate', label: 'Completion %' },
  { key: 'last_activity', label: 'Last activity' },
]
const fmt = (v: number | null) => (v == null ? '—' : v)
</script>

<template>
  <Spinner v-if="loading" />
  <div v-else class="space-y-6">
    <div class="grid grid-cols-3 gap-4">
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted-foreground">Contractors</p>
            <p class="text-3xl font-bold mt-1">{{ totals.contractors }}</p>
          </div>
          <Users class="h-6 w-6 text-sky-500" />
        </div>
      </Card>
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted-foreground">Total assigned</p>
            <p class="text-3xl font-bold mt-1">{{ totals.assigned }}</p>
          </div>
          <ClipboardCheck class="h-6 w-6 text-violet-500" />
        </div>
      </Card>
      <Card>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted-foreground">Total resolved</p>
            <p class="text-3xl font-bold mt-1">{{ totals.resolved }}</p>
          </div>
          <CheckCircle2 class="h-6 w-6 text-emerald-500" />
        </div>
      </Card>
    </div>

    <Card :padded="false">
      <DataTable :columns="COLUMNS" :rows="rows">
        <template #average_rating="{ value }">
          <span
            class="inline-flex items-center gap-1 text-amber-500 font-medium"
          >
            <Star class="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
            {{ value ?? '—' }}
          </span>
        </template>
        <template #avg_response_time_hours="{ value }">{{
          fmt(value)
        }}</template>
        <template #avg_resolution_time_hours="{ value }">{{
          fmt(value)
        }}</template>
        <template #completion_rate="{ value }">{{ value }}%</template>
        <template #last_activity="{ value }">{{
          value ? new Date(value).toLocaleString() : '—'
        }}</template>
        <template #empty>No contractor activity yet</template>
      </DataTable>
    </Card>
  </div>
</template>
