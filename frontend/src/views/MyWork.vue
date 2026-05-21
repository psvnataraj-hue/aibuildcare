<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Briefcase,
  Phone,
  ChevronRight,
  CheckCircle2,
  PlayCircle,
  AlertTriangle,
  RotateCw,
} from 'lucide-vue-next'
import { api, type Complaint } from '../api'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'

const router = useRouter()
const loading = ref(true)
const includeResolved = ref(false)
const staff = ref<{ id: number; name: string; phone_primary: string } | null>(null)
const complaints = ref<Complaint[]>([])
const busy = ref<number | null>(null)  // complaint id while a status flip is in-flight

async function load() {
  loading.value = true
  try {
    const r = await api.listMyAssignments(includeResolved.value)
    staff.value = r.staff
    complaints.value = r.complaints
  } catch (e: any) {
    toast(e.message || 'Failed to load my work', 'error')
  } finally {
    loading.value = false
  }
}

async function flip(c: Complaint, status: string) {
  busy.value = c.id
  try {
    await api.setStatus(c.id, status)
    toast(`#${c.ticket_number} → ${status.replace('_', ' ')} ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Status change failed', 'error')
  } finally {
    busy.value = null
  }
}

const counts = computed(() => {
  const out = { open: 0, in_progress: 0, total: complaints.value.length }
  for (const c of complaints.value) {
    if (c.status === 'in_progress') out.in_progress++
    if (['received', 'acknowledged', 'assigned'].includes(c.status)) out.open++
  }
  return out
})

onMounted(load)
</script>

<template>
  <Spinner v-if="loading" />
  <div v-else class="space-y-4">
    <!-- header — compact, mobile-first -->
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <h1 class="text-xl sm:text-2xl font-bold flex items-center gap-2">
          <Briefcase class="h-5 w-5 sm:h-6 sm:w-6 text-primary" />
          My Work · मेरा काम
        </h1>
        <p
          v-if="staff"
          class="text-xs sm:text-sm text-muted-foreground mt-1 truncate"
        >
          {{ staff.name }} · {{ staff.phone_primary }}
        </p>
      </div>
      <button
        class="shrink-0 h-9 w-9 inline-flex items-center justify-center rounded-md hover:bg-secondary"
        title="Refresh"
        @click="load"
      >
        <RotateCw class="h-4 w-4" />
      </button>
    </div>

    <!-- "no staff record linked" empty state -->
    <Card v-if="!staff" class="text-center py-10">
      <AlertTriangle class="h-10 w-10 mx-auto text-amber-500" />
      <p class="mt-3 font-semibold">No staff record linked</p>
      <p class="text-sm text-muted-foreground mt-1">
        Your login email isn't yet linked to any staff member in this
        society. Ask your admin to add you via the Staff page
        (matching this email).
      </p>
    </Card>

    <!-- summary chips -->
    <div v-else-if="complaints.length" class="flex gap-2 flex-wrap">
      <span
        class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold bg-sky-100 text-sky-800 ring-1 ring-sky-300 dark:bg-sky-900/40 dark:text-sky-200 dark:ring-sky-700/40"
      >
        {{ counts.open }} open
      </span>
      <span
        class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold bg-amber-100 text-amber-800 ring-1 ring-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-700/40"
      >
        {{ counts.in_progress }} in progress
      </span>
      <label class="ml-auto inline-flex items-center gap-1.5 text-xs">
        <input
          v-model="includeResolved"
          type="checkbox"
          class="rounded"
          @change="load"
        />
        Show resolved
      </label>
    </div>

    <!-- empty state — no assignments -->
    <Card
      v-else-if="staff && !complaints.length"
      class="text-center py-10"
    >
      <CheckCircle2 class="h-10 w-10 mx-auto text-emerald-500" />
      <p class="mt-3 font-semibold">All caught up 🎉</p>
      <p class="text-sm text-muted-foreground mt-1">
        No open complaints assigned to you. Check back later, or
        toggle "Show resolved" to see history.
      </p>
    </Card>

    <!-- complaint cards — single column, thumb-friendly action buttons -->
    <div v-if="staff && complaints.length" class="space-y-3">
      <Card
        v-for="c in complaints"
        :key="c.id"
        :class="
          c.major_incident
            ? 'ring-2 ring-red-500/60'
            : c.priority === 'urgent'
              ? 'ring-1 ring-red-300/60'
              : ''
        "
      >
        <!-- top row: unit + category + ETA -->
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <p class="font-bold">
              Unit {{ c.unit_number || '—' }}
              <span class="text-muted-foreground font-normal text-sm">
                · {{ c.category || 'Other' }}
              </span>
            </p>
            <p class="text-xs text-muted-foreground mt-0.5">
              #{{ c.ticket_number }}
            </p>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <Badge :variant="c.priority" class="text-[10px]">
              {{ c.priority }}
            </Badge>
            <Badge :variant="c.status" class="text-[10px]">
              {{ c.status.replace('_', ' ') }}
            </Badge>
          </div>
        </div>

        <!-- gist of the raw text -->
        <p class="text-sm mt-2 line-clamp-2 text-muted-foreground">
          {{ c.raw_text }}
        </p>

        <!-- thumb-friendly action row -->
        <div class="mt-4 grid grid-cols-2 gap-2">
          <button
            v-if="c.status === 'assigned' || c.status === 'received' || c.status === 'acknowledged'"
            :disabled="busy === c.id"
            class="h-11 rounded-lg bg-amber-500 hover:bg-amber-600 text-white font-medium inline-flex items-center justify-center gap-1.5 disabled:opacity-60"
            @click="flip(c, 'in_progress')"
          >
            <PlayCircle class="h-4 w-4" />
            Start
          </button>
          <button
            v-if="c.status !== 'resolved' && c.status !== 'closed'"
            :disabled="busy === c.id"
            class="h-11 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-medium inline-flex items-center justify-center gap-1.5 disabled:opacity-60"
            @click="flip(c, 'resolved')"
          >
            <CheckCircle2 class="h-4 w-4" />
            Resolve
          </button>
          <button
            class="col-span-2 h-10 rounded-lg border text-sm font-medium hover:bg-secondary inline-flex items-center justify-center gap-1"
            @click="router.push(`/complaints/${c.id}`)"
          >
            Open details
            <ChevronRight class="h-4 w-4" />
          </button>
        </div>

        <!-- contact / context strip — small affordance to call the resident -->
        <div
          v-if="c.assigned_staff_name || c.contractor_id"
          class="mt-3 pt-3 border-t flex items-center gap-2 text-xs text-muted-foreground"
        >
          <Phone class="h-3 w-3" />
          <span class="truncate">
            {{ c.assigned_staff_name || `contractor #${c.contractor_id}` }}
          </span>
        </div>
      </Card>
    </div>
  </div>
</template>
