<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Send,
  CheckCircle2,
  Circle,
  Languages,
} from 'lucide-vue-next'
import {
  api,
  type Complaint,
  type Contractor,
  type Message,
} from '../api'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Spinner from '../components/ui/Spinner.vue'
import ImageLightbox from '../components/ui/ImageLightbox.vue'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const c = ref<Complaint | null>(null)
const contractors = ref<Contractor[]>([])
const msg = ref('')
const pick = ref<number | null>(null)
const error = ref('')
const lightbox = ref<string | null>(null)
const loading = ref(true)

const FLOW = [
  'received',
  'acknowledged',
  'assigned',
  'in_progress',
  'resolved',
  'closed',
]

const photos = computed(() =>
  (c.value?.media_urls || '')
    .split(',')
    .map((u) => u.trim())
    .filter(Boolean)
)
const stepIdx = computed(() =>
  c.value ? FLOW.indexOf(c.value.status) : -1
)

async function load() {
  c.value = await api.getComplaint(id)
  loading.value = false
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
  if (!pick.value) return
  error.value = ''
  try {
    await api.assign(id, pick.value)
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}
async function setStatus(s: string) {
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
  <Spinner v-if="loading" />
  <div v-else-if="c" class="space-y-6">
    <button
      class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      @click="router.push('/complaints')"
    >
      <ArrowLeft class="h-4 w-4" /> Back to complaints
    </button>

    <div>
      <div class="flex items-center gap-3 flex-wrap">
        <h1 class="text-2xl font-bold">{{ c.ticket_number }}</h1>
        <Badge :variant="c.priority">{{ c.priority }}</Badge>
        <Badge :variant="c.status">{{ c.status.replace('_', ' ') }}</Badge>
        <span
          v-if="c.detected_language"
          class="inline-flex items-center gap-1 text-xs text-muted-foreground"
        >
          <Languages class="h-3.5 w-3.5" /> {{ c.detected_language }}
        </span>
      </div>
      <p class="text-muted-foreground mt-1">
        {{ c.category }} · {{ c.unit_number || 'unknown unit' }}
      </p>
      <p class="text-sm mt-2">{{ c.raw_text }}</p>
    </div>

    <!-- status timeline -->
    <Card>
      <div class="flex items-center justify-between">
        <template v-for="(s, i) in FLOW" :key="s">
          <div class="flex flex-col items-center text-center flex-1">
            <component
              :is="i <= stepIdx ? CheckCircle2 : Circle"
              class="h-5 w-5"
              :class="
                i <= stepIdx ? 'text-primary' : 'text-muted-foreground/40'
              "
            />
            <span
              class="text-[11px] mt-1 capitalize"
              :class="
                i <= stepIdx
                  ? 'text-foreground font-medium'
                  : 'text-muted-foreground'
              "
              >{{ s.replace('_', ' ') }}</span
            >
          </div>
          <div
            v-if="i < FLOW.length - 1"
            class="h-0.5 flex-1 -mt-4"
            :class="i < stepIdx ? 'bg-primary' : 'bg-border'"
          />
        </template>
      </div>
    </Card>

    <div
      v-if="photos.length"
      class="flex flex-wrap gap-3"
    >
      <button
        v-for="(u, i) in photos"
        :key="i"
        class="h-28 w-28 rounded-lg overflow-hidden border hover:ring-2 hover:ring-ring"
        @click="lightbox = u"
      >
        <img :src="u" class="h-full w-full object-cover" alt="photo" />
      </button>
    </div>

    <div class="grid md:grid-cols-3 gap-6">
      <Card class="md:col-span-2">
        <h2 class="font-semibold mb-3">Message thread</h2>
        <div class="space-y-3 max-h-80 overflow-y-auto pr-1">
          <div v-for="m in (c.messages as Message[])" :key="m.id">
            <div class="flex items-center gap-2">
              <span
                class="text-xs font-semibold capitalize"
                :class="
                  m.sender === 'system'
                    ? 'text-primary'
                    : 'text-foreground'
                "
                >{{ m.sender }}</span
              >
              <span class="text-[11px] text-muted-foreground">{{
                new Date(m.created_at).toLocaleString()
              }}</span>
            </div>
            <div class="bg-secondary rounded-md p-2.5 mt-1 text-sm">
              {{ m.body }}
            </div>
          </div>
        </div>
        <div class="flex gap-2 mt-4">
          <input
            v-model="msg"
            placeholder="Reply…"
            class="flex-1 bg-background border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring"
            @keyup.enter="send"
          />
          <button
            class="inline-flex items-center gap-1 bg-primary text-primary-foreground px-4 rounded-md hover:bg-primary/90"
            @click="send"
          >
            <Send class="h-4 w-4" />
          </button>
        </div>
      </Card>

      <Card class="space-y-5">
        <div>
          <p class="text-sm text-muted-foreground mb-2">Quick actions</p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="s in FLOW"
              :key="s"
              class="text-xs border rounded-md px-2 py-1 hover:bg-secondary capitalize"
              :class="
                c.status === s ? 'bg-primary text-primary-foreground' : ''
              "
              @click="setStatus(s)"
            >
              {{ s.replace('_', ' ') }}
            </button>
          </div>
        </div>
        <div>
          <p class="text-sm text-muted-foreground mb-1">Assign contractor</p>
          <select
            v-model="pick"
            class="w-full bg-background border rounded-md px-2 py-2 mb-2"
          >
            <option :value="null">Select…</option>
            <option v-for="ct in contractors" :key="ct.id" :value="ct.id">
              {{ ct.name }} ({{ ct.specialty }})
            </option>
          </select>
          <button
            class="w-full bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90"
            @click="assign"
          >
            Assign
          </button>
        </div>
        <p
          v-if="error"
          class="text-destructive text-sm bg-destructive/10 rounded-md px-3 py-2"
        >
          {{ error }}
        </p>
      </Card>
    </div>
  </div>

  <ImageLightbox :src="lightbox" @close="lightbox = null" />
</template>
