<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  TrendingUp,
  UserPlus,
  Pencil,
  Trash2,
  X,
  Phone,
  Mail,
  AlertTriangle,
} from 'lucide-vue-next'
import {
  api,
  PERMISSIONS,
  type HierarchyEntry,
  type HierarchyCreatePayload,
  type HierarchyPatchPayload,
} from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'
import { can } from '../lib/currentUser'

// E3h: viewers can see the hierarchy; only roles with MODIFY_CONFIG
// (sr_manager / secretary / chairman / admin by default) can edit.
const canModify = computed(() => can(PERMISSIONS.MODIFY_CONFIG))

// 4 levels — each maps to a specific role_name expected by the cron
// escalation logic. Adding entries with other role_names is allowed
// by the backend but won't be consumed by the auto-escalation job.
const LEVELS = [
  {
    level: 1,
    role: 'manager',
    label: 'L1 · Manager',
    color: 'amber',
    desc: 'First on-site contact. Notified on initial SLA breach.',
  },
  {
    level: 2,
    role: 'sr_manager',
    label: 'L2 · Senior Manager',
    color: 'orange',
    desc: 'Escalation after L1 SLA breach.',
  },
  {
    level: 3,
    role: 'secretary',
    label: 'L3 · Secretary',
    color: 'red',
    desc: 'Society secretary. Escalation after L2 breach.',
  },
  {
    level: 4,
    role: 'chairman',
    label: 'L4 · Chairman',
    color: 'red-deep',
    desc: 'Final escalation tier. Notified on prolonged breach.',
  },
] as const

const loading = ref(true)
const entries = ref<HierarchyEntry[]>([])

const grouped = computed(() => {
  const out: Record<number, HierarchyEntry[]> = { 1: [], 2: [], 3: [], 4: [] }
  for (const e of entries.value) {
    if (!out[e.escalation_level]) out[e.escalation_level] = []
    out[e.escalation_level].push(e)
  }
  return out
})

// add modal
const addingLevel = ref<number | null>(null)
const add = ref<HierarchyCreatePayload>(emptyAdd())
function emptyAdd(level = 1): HierarchyCreatePayload {
  const lvl = LEVELS.find((l) => l.level === level) || LEVELS[0]
  return {
    role_name: lvl.role,
    person_name: '',
    phone: '',
    whatsapp_enabled: true,
    email: '',
    escalation_level: level,
    response_time_target_minutes: 60,
  }
}
function openAdd(level: number) {
  add.value = emptyAdd(level)
  addingLevel.value = level
}

// edit modal
const editingId = ref<number | null>(null)
const edit = ref<HierarchyPatchPayload>({})
function openEdit(e: HierarchyEntry) {
  editingId.value = e.id
  edit.value = {
    role_name: e.role_name,
    person_name: e.person_name,
    phone: e.phone || '',
    whatsapp_enabled: e.whatsapp_enabled,
    email: e.email || '',
    escalation_level: e.escalation_level,
    response_time_target_minutes: e.response_time_target_minutes,
    active: e.active,
  }
}

async function load() {
  loading.value = true
  try {
    entries.value = await api.listHierarchy()
  } catch (e: any) {
    toast(e.message || 'Failed to load hierarchy', 'error')
  } finally {
    loading.value = false
  }
}

async function submitAdd() {
  if (!add.value.person_name?.trim()) {
    toast('Person name is required', 'error')
    return
  }
  const payload: HierarchyCreatePayload = { ...add.value }
  if (payload.phone === '') payload.phone = null
  if (payload.email === '') payload.email = null
  try {
    await api.addHierarchy(payload)
    toast(`Added ${add.value.person_name} ✓`)
    addingLevel.value = null
    await load()
  } catch (e: any) {
    toast(e.message || 'Add failed', 'error')
  }
}

async function submitEdit() {
  if (!editingId.value) return
  const payload: HierarchyPatchPayload = { ...edit.value }
  if (payload.phone === '') payload.phone = null
  if (payload.email === '') payload.email = null
  try {
    await api.updateHierarchy(editingId.value, payload)
    toast('Updated ✓')
    editingId.value = null
    await load()
  } catch (e: any) {
    toast(e.message || 'Update failed', 'error')
  }
}

async function remove(e: HierarchyEntry) {
  if (!confirm(`Remove ${e.person_name} from L${e.escalation_level}? This is a hard delete and cannot be undone.`)) return
  try {
    await api.deleteHierarchy(e.id)
    toast(`Removed ${e.person_name} ✓`)
    await load()
  } catch (err: any) {
    toast(err.message || 'Delete failed', 'error')
  }
}

const totalSeeded = computed(() => entries.value.length)
const allFourLevelsSeeded = computed(() =>
  LEVELS.every((l) => (grouped.value[l.level] || []).length > 0)
)

onMounted(load)
</script>

<template>
  <Spinner v-if="loading" />
  <div v-else class="space-y-6">
    <!-- header -->
    <div>
      <h1 class="text-2xl font-bold flex items-center gap-2">
        <TrendingUp class="h-6 w-6 text-primary" />
        Escalation Hierarchy · वृद्धि पदानुक्रम
      </h1>
      <p class="text-sm text-muted-foreground mt-1">
        Per-society escalation chain. The cron-driven escalation job
        notifies the person at each level when a complaint breaches
        its SLA threshold (default L1=2h, L2=4h, L3=8h).
      </p>
    </div>

    <!-- empty-chain warning -->
    <div
      v-if="totalSeeded === 0"
      class="rounded-lg bg-amber-100 dark:bg-amber-900/40 px-4 py-3 flex items-start gap-2 text-amber-900 dark:text-amber-200"
    >
      <AlertTriangle class="h-5 w-5 shrink-0 mt-0.5" />
      <div class="text-sm">
        <p class="font-semibold">No escalation hierarchy seeded.</p>
        <p class="mt-1">
          The cron job will run but escalation messages have nowhere
          to go. Add at least an L1 manager to get value from the
          auto-escalation pipeline.
        </p>
      </div>
    </div>

    <div
      v-else-if="!allFourLevelsSeeded"
      class="rounded-lg bg-amber-100/60 dark:bg-amber-900/30 px-4 py-2 flex items-start gap-2 text-amber-900 dark:text-amber-200 text-sm"
    >
      <AlertTriangle class="h-4 w-4 shrink-0 mt-0.5" />
      <span>
        Partial chain — escalations beyond the highest seeded level
        will be silently skipped by the cron job.
      </span>
    </div>

    <!-- 4 level columns -->
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card v-for="lvl in LEVELS" :key="lvl.level" class="flex flex-col">
        <div class="flex items-start justify-between gap-2">
          <div>
            <p
              class="font-bold text-sm"
              :class="{
                'text-amber-700 dark:text-amber-300': lvl.color === 'amber',
                'text-orange-700 dark:text-orange-300': lvl.color === 'orange',
                'text-red-700 dark:text-red-300': lvl.color === 'red',
                'text-red-800 dark:text-red-200': lvl.color === 'red-deep',
              }"
            >
              {{ lvl.label }}
            </p>
            <p class="text-[11px] text-muted-foreground mt-0.5 leading-tight">
              {{ lvl.desc }}
            </p>
          </div>
          <button
            v-if="canModify"
            class="shrink-0 h-7 w-7 inline-flex items-center justify-center rounded-md bg-primary/10 text-primary hover:bg-primary/20"
            title="Add person at this level"
            @click="openAdd(lvl.level)"
          >
            <UserPlus class="h-3.5 w-3.5" />
          </button>
        </div>

        <div class="mt-3 space-y-2 flex-1">
          <div
            v-for="e in grouped[lvl.level] || []"
            :key="e.id"
            class="rounded-md border bg-secondary/40 px-3 py-2"
            :class="!e.active ? 'opacity-60' : ''"
          >
            <p class="font-semibold text-sm truncate">
              {{ e.person_name }}
            </p>
            <p
              v-if="e.phone"
              class="text-xs text-muted-foreground mt-0.5 flex items-center gap-1"
            >
              <Phone class="h-3 w-3" />
              {{ e.phone }}
              <span v-if="e.whatsapp_enabled" class="text-emerald-600 ml-1">
                WA
              </span>
            </p>
            <p
              v-if="e.email"
              class="text-xs text-muted-foreground mt-0.5 flex items-center gap-1"
            >
              <Mail class="h-3 w-3" />
              <span class="truncate">{{ e.email }}</span>
            </p>
            <div v-if="canModify" class="mt-2 flex gap-1">
              <button
                class="flex-1 inline-flex items-center justify-center gap-1 border rounded px-1 py-0.5 text-[11px] hover:bg-secondary"
                @click="openEdit(e)"
              >
                <Pencil class="h-3 w-3" /> Edit
              </button>
              <button
                class="inline-flex items-center justify-center gap-1 border rounded px-1 py-0.5 text-[11px] hover:bg-destructive/10 text-destructive"
                @click="remove(e)"
              >
                <Trash2 class="h-3 w-3" />
              </button>
            </div>
          </div>
          <p
            v-if="(grouped[lvl.level] || []).length === 0"
            class="text-xs italic text-muted-foreground text-center py-3"
          >
            no one assigned
          </p>
        </div>
      </Card>
    </div>

    <!-- ADD modal -->
    <div
      v-if="addingLevel !== null"
      class="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      @click.self="addingLevel = null"
    >
      <Card class="w-full max-w-md">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold flex items-center gap-2">
            <UserPlus class="h-5 w-5 text-primary" />
            Add to L{{ addingLevel }}
          </h2>
          <button
            class="h-8 w-8 rounded-md hover:bg-secondary inline-flex items-center justify-center"
            @click="addingLevel = null"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
        <div class="space-y-3">
          <label class="block">
            <span class="text-xs text-muted-foreground">Person name *</span>
            <input
              v-model="add.person_name"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              placeholder="e.g. Mira Manager"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Phone (with country code)</span>
            <input
              v-model="add.phone"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              placeholder="+91XXXXXXXXXX"
            />
          </label>
          <label class="inline-flex items-center gap-2 text-sm">
            <input
              v-model="add.whatsapp_enabled"
              type="checkbox"
              class="rounded"
            />
            WhatsApp enabled
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Email</span>
            <input
              v-model="add.email"
              type="email"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">
              Response-time target (minutes)
            </span>
            <input
              v-model.number="add.response_time_target_minutes"
              type="number"
              min="1"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <div class="flex gap-2 pt-2">
            <button
              class="flex-1 bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90"
              @click="submitAdd"
            >
              Add
            </button>
            <button
              class="border rounded-md px-4 hover:bg-secondary"
              @click="addingLevel = null"
            >
              Cancel
            </button>
          </div>
        </div>
      </Card>
    </div>

    <!-- EDIT modal -->
    <div
      v-if="editingId"
      class="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      @click.self="editingId = null"
    >
      <Card class="w-full max-w-md">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold flex items-center gap-2">
            <Pencil class="h-5 w-5 text-primary" />
            Edit hierarchy entry
          </h2>
          <button
            class="h-8 w-8 rounded-md hover:bg-secondary inline-flex items-center justify-center"
            @click="editingId = null"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
        <div class="space-y-3">
          <label class="block">
            <span class="text-xs text-muted-foreground">Person name</span>
            <input
              v-model="edit.person_name"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Phone</span>
            <input
              v-model="edit.phone"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="inline-flex items-center gap-2 text-sm">
            <input
              v-model="edit.whatsapp_enabled"
              type="checkbox"
              class="rounded"
            />
            WhatsApp enabled
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Email</span>
            <input
              v-model="edit.email"
              type="email"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">
              Response-time target (minutes)
            </span>
            <input
              v-model.number="edit.response_time_target_minutes"
              type="number"
              min="1"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="inline-flex items-center gap-2 text-sm">
            <input
              v-model="edit.active"
              type="checkbox"
              class="rounded"
            />
            Active (uncheck to soft-disable without deleting)
          </label>
          <div class="flex gap-2 pt-2">
            <button
              class="flex-1 bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90"
              @click="submitEdit"
            >
              Save
            </button>
            <button
              class="border rounded-md px-4 hover:bg-secondary"
              @click="editingId = null"
            >
              Cancel
            </button>
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>
