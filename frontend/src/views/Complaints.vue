<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Plus, Loader2, Image as ImageIcon } from 'lucide-vue-next'
import { api, openWS, type Complaint } from '../api'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Spinner from '../components/ui/Spinner.vue'

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
      <table v-else class="w-full text-sm">
        <thead class="text-left text-muted-foreground border-b">
          <tr>
            <th class="p-3 font-medium">Ticket</th>
            <th class="p-3 font-medium">Unit</th>
            <th class="p-3 font-medium">Category</th>
            <th class="p-3 font-medium">Priority</th>
            <th class="p-3 font-medium">Status</th>
            <th class="p-3 font-medium">Channel</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in items"
            :key="c.id"
            class="border-b last:border-0 hover:bg-secondary/50 cursor-pointer"
            @click="router.push(`/complaints/${c.id}`)"
          >
            <td class="p-3 font-mono text-xs">{{ c.ticket_number }}</td>
            <td class="p-3">{{ c.unit_number || '—' }}</td>
            <td class="p-3 flex items-center gap-1">
              {{ c.category }}
              <ImageIcon
                v-if="c.media_urls"
                class="h-3.5 w-3.5 text-muted-foreground"
              />
            </td>
            <td class="p-3"><Badge :variant="c.priority">{{ c.priority }}</Badge></td>
            <td class="p-3">
              <Badge :variant="c.status">{{
                c.status.replace('_', ' ')
              }}</Badge>
            </td>
            <td class="p-3 capitalize text-muted-foreground">
              {{ c.channel }}
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="p-8 text-center text-muted-foreground">
              No complaints
            </td>
          </tr>
        </tbody>
      </table>
    </Card>
  </div>
</template>
