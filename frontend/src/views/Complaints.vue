<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api, openWS, type Complaint } from '../api'

const items = ref<Complaint[]>([])
const q = ref('')
const status = ref('')
const sort = ref('created_at')
const newText = ref('')
const creating = ref(false)
let ws: WebSocket | null = null

async function load() {
  items.value = await api.listComplaints(q.value, status.value, sort.value)
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

const prioClass = (p: string) =>
  p === 'urgent'
    ? 'bg-red-100 text-red-700'
    : p === 'high'
      ? 'bg-amber-100 text-amber-700'
      : 'bg-slate-100 text-slate-600'

onMounted(() => {
  load()
  ws = openWS(() => load())
})
onUnmounted(() => ws?.close())
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-4">Complaints</h1>

    <div class="bg-white rounded-xl shadow p-4 mb-4 flex gap-2 flex-wrap">
      <input
        v-model="newText"
        placeholder="Log a complaint, e.g. '5B mein AC kharab hai urgent'"
        class="flex-1 min-w-[240px] border rounded px-3 py-2"
        @keyup.enter="create"
      />
      <button
        :disabled="creating"
        class="bg-brand text-white px-4 py-2 rounded disabled:opacity-60"
        @click="create"
      >
        {{ creating ? 'Parsing...' : 'Log + parse' }}
      </button>
    </div>

    <div class="flex gap-2 mb-4 flex-wrap">
      <input
        v-model="q"
        placeholder="Search..."
        class="border rounded px-3 py-2"
        @keyup.enter="load"
      />
      <select v-model="status" class="border rounded px-3 py-2" @change="load">
        <option value="">All statuses</option>
        <option>received</option>
        <option>acknowledged</option>
        <option>assigned</option>
        <option>in_progress</option>
        <option>resolved</option>
        <option>closed</option>
      </select>
      <select v-model="sort" class="border rounded px-3 py-2" @change="load">
        <option value="created_at">Newest</option>
        <option value="priority">Priority</option>
        <option value="status">Status</option>
      </select>
    </div>

    <div class="bg-white rounded-xl shadow overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-left">
          <tr>
            <th class="p-3">Ticket</th>
            <th class="p-3">Unit</th>
            <th class="p-3">Category</th>
            <th class="p-3">Priority</th>
            <th class="p-3">Status</th>
            <th class="p-3">Channel</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in items"
            :key="c.id"
            class="border-t hover:bg-slate-50 cursor-pointer"
            @click="$router.push(`/complaints/${c.id}`)"
          >
            <td class="p-3 font-mono">{{ c.ticket_number }}</td>
            <td class="p-3">{{ c.unit_number || '-' }}</td>
            <td class="p-3">{{ c.category }}</td>
            <td class="p-3">
              <span
                class="px-2 py-0.5 rounded-full text-xs"
                :class="prioClass(c.priority)"
                >{{ c.priority }}</span
              >
            </td>
            <td class="p-3">{{ c.status }}</td>
            <td class="p-3">{{ c.channel }}</td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="p-6 text-center text-slate-400">
              No complaints
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
