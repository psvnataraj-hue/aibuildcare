<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Plus, Loader2, Image as ImageIcon } from 'lucide-vue-next'
import { api, openWS, type Complaint } from '../api'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Spinner from '../components/ui/Spinner.vue'
import DataTable from '../components/ui/DataTable.vue'

const COLUMNS = [
  { key: 'ticket_number', label: 'Ticket' },
  { key: 'unit_number', label: 'Unit' },
  { key: 'category', label: 'Category' },
  { key: 'priority', label: 'Priority' },
  { key: 'status', label: 'Status' },
  { key: 'channel', label: 'Channel' },
]

const router = useRouter()
const items = ref<Complaint[]>([])
const q = ref('')
const status = ref('')
const sort = ref('created_at')
const newText = ref('')
const creating = ref(false)
const loading = ref(true)
let ws: WebSocket | null = null

async function load() {
  items.value = await api.listComplaints(q.value, status.value, sort.value)
  loading.value = false
}
async function create() {
  if (!newText.value.trim()) return
  creating.value = true
  try {
    await api.createComplaint(newText.value)
    newText.value = ''
    await load()
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  load()
  ws = openWS(() => load())
})
onUnmounted(() => ws?.close())
</script>

<template>
  <div class="space-y-4">
    <Card>
      <div class="flex gap-2 flex-wrap">
        <input
          v-model="newText"
          placeholder="Log a complaint, e.g. '5B mein AC kharab hai urgent'"
          class="flex-1 min-w-[240px] bg-background border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring"
          @keyup.enter="create"
        />
        <button
          :disabled="creating"
          class="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md font-medium hover:bg-primary/90 disabled:opacity-60"
          @click="create"
        >
          <Loader2 v-if="creating" class="h-4 w-4 animate-spin" />
          <Plus v-else class="h-4 w-4" />
          {{ creating ? 'Parsing…' : 'Log + parse' }}
        </button>
      </div>
    </Card>

    <div class="flex gap-2 flex-wrap items-center">
      <div class="relative flex-1 min-w-[200px]">
        <Search
          class="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <input
          v-model="q"
          placeholder="Search ticket / unit / text…"
          class="w-full bg-card border rounded-md pl-9 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring"
          @keyup.enter="load"
        />
      </div>
      <select
        v-model="status"
        class="bg-card border rounded-md px-3 py-2"
        @change="load"
      >
        <option value="">All statuses</option>
        <option>received</option>
        <option>acknowledged</option>
        <option>assigned</option>
        <option>in_progress</option>
        <option>resolved</option>
        <option>closed</option>
      </select>
      <select
        v-model="sort"
        class="bg-card border rounded-md px-3 py-2"
        @change="load"
      >
        <option value="created_at">Newest</option>
        <option value="priority">Priority</option>
        <option value="status">Status</option>
      </select>
    </div>

    <Card :padded="false">
      <Spinner v-if="loading" />
      <DataTable
        v-else
        :columns="COLUMNS"
        :rows="items"
        @row-click="(r: Complaint) => router.push(`/complaints/${r.id}`)"
      >
        <template #ticket_number="{ value }">
          <span class="font-mono text-xs">{{ value }}</span>
        </template>
        <template #unit_number="{ value }">{{ value || '—' }}</template>
        <template #category="{ row }">
          <span class="inline-flex items-center gap-1">
            {{ row.category }}
            <ImageIcon
              v-if="row.media_urls"
              class="h-3.5 w-3.5 text-muted-foreground"
            />
          </span>
        </template>
        <template #priority="{ value }">
          <Badge :variant="value">{{ value }}</Badge>
        </template>
        <template #status="{ value }">
          <Badge :variant="value">{{ value.replace('_', ' ') }}</Badge>
        </template>
        <template #channel="{ value }">
          <span class="capitalize text-muted-foreground">{{ value }}</span>
        </template>
        <template #empty>No complaints</template>
      </DataTable>
    </Card>
  </div>
</template>
