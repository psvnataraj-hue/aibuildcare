<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  api,
  type Complaint,
  type Contractor,
  type Message,
} from '../api'

const route = useRoute()
const id = Number(route.params.id)
const c = ref<Complaint | null>(null)
const contractors = ref<Contractor[]>([])
const msg = ref('')
const pickContractor = ref<number | null>(null)
const error = ref('')

const photos = computed(() =>
  (c.value?.media_urls || '')
    .split(',')
    .map((u) => u.trim())
    .filter(Boolean)
)

const STATUSES = [
  'received',
  'acknowledged',
  'assigned',
  'in_progress',
  'resolved',
  'closed',
]

async function load() {
  c.value = await api.getComplaint(id)
}

onMounted(async () => {
  await load()
  contractors.value = await api.contractors()
})

async function send() {
  if (!msg.value.trim()) return
  await api.addMessage(id, msg.value)
  msg.value = ''
  await load()
}

async function assign() {
  if (!pickContractor.value) return
  try {
    await api.assign(id, pickContractor.value)
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}

async function changeStatus(s: string) {
  error.value = ''
  try {
    await api.setStatus(id, s)
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}
</script>

<template>
  <div v-if="c">
    <RouterLink to="/complaints" class="text-brand text-sm"
      >&larr; Back</RouterLink
    >
    <h1 class="text-2xl font-bold mt-2 mb-1">
      {{ c.ticket_number }}
      <span class="text-base font-normal text-slate-500"
        >· {{ c.category }} · {{ c.unit_number || 'unknown unit' }}</span
      >
    </h1>
    <p class="text-sm text-slate-500 mb-2">{{ c.raw_text }}</p>
    <span
      v-if="c.detected_language"
      class="inline-block text-xs bg-slate-200 rounded-full px-2 py-0.5 mb-4"
      >🌐 {{ c.detected_language }}</span
    >

    <div v-if="photos.length" class="flex flex-wrap gap-3 mb-4">
      <a
        v-for="(url, i) in photos"
        :key="i"
        :href="url"
        target="_blank"
        rel="noopener"
      >
        <img
          :src="url"
          class="h-32 w-32 object-cover rounded-lg border shadow-sm hover:opacity-90"
          alt="complaint photo"
        />
      </a>
    </div>

    <div class="grid md:grid-cols-3 gap-4">
      <div class="md:col-span-2 bg-white rounded-xl shadow p-4">
        <h2 class="font-semibold mb-3">Message thread</h2>
        <div class="space-y-3 max-h-80 overflow-y-auto">
          <div
            v-for="m in c.messages as Message[]"
            :key="m.id"
            class="text-sm"
          >
            <span
              class="font-semibold"
              :class="m.sender === 'system' ? 'text-brand' : 'text-slate-700'"
              >{{ m.sender }}</span
            >
            <span class="text-slate-400 text-xs ml-2">{{
              new Date(m.created_at).toLocaleString()
            }}</span>
            <div class="bg-slate-50 rounded p-2 mt-1">{{ m.body }}</div>
          </div>
        </div>
        <div class="flex gap-2 mt-4">
          <input
            v-model="msg"
            placeholder="Reply..."
            class="flex-1 border rounded px-3 py-2"
            @keyup.enter="send"
          />
          <button
            class="bg-brand text-white px-4 py-2 rounded"
            @click="send"
          >
            Send
          </button>
        </div>
      </div>

      <div class="bg-white rounded-xl shadow p-4 space-y-4">
        <div>
          <div class="text-sm text-slate-500">Status</div>
          <div class="font-semibold mb-2">{{ c.status }}</div>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="s in STATUSES"
              :key="s"
              class="text-xs border rounded px-2 py-1 hover:bg-slate-50"
              @click="changeStatus(s)"
            >
              {{ s }}
            </button>
          </div>
        </div>
        <div>
          <div class="text-sm text-slate-500 mb-1">Assign contractor</div>
          <select
            v-model="pickContractor"
            class="w-full border rounded px-2 py-2 mb-2"
          >
            <option :value="null">Select...</option>
            <option v-for="ct in contractors" :key="ct.id" :value="ct.id">
              {{ ct.name }} ({{ ct.specialty }})
            </option>
          </select>
          <button
            class="w-full bg-brand text-white py-2 rounded"
            @click="assign"
          >
            Assign
          </button>
        </div>
        <p v-if="error" class="text-red-600 text-sm">{{ error }}</p>
      </div>
    </div>
  </div>
  <div v-else class="text-slate-500">Loading...</div>
</template>
