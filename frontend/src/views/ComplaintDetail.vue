<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Send,
  CheckCircle2,
  Circle,
  Languages,
  Star,
  AlertTriangle,
  TrendingUp,
  Car,
  Lock,
} from 'lucide-vue-next'
import {
  api,
  PERMISSIONS,
  type Complaint,
  type Contractor,
  type Message,
} from '../api'
import { can } from '../lib/currentUser'

// E3h — gate action buttons by effective permission.
const canAssign = computed(() => can(PERMISSIONS.ASSIGN))
const canResolve = computed(() => can(PERMISSIONS.RESOLVE))
// Parking P4 — clamping requires the AUTHORIZE_ENFORCEMENT permission
// AND a parking-category complaint.
const canAuthorizeClamping = computed(
  () => can(PERMISSIONS.AUTHORIZE_ENFORCEMENT),
)
const isParkingComplaint = computed(
  () => c.value?.category === 'Parking Management',
)
const isClamped = computed(() => !!c.value?.clamped)
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Spinner from '../components/ui/Spinner.vue'
import ImageLightbox from '../components/ui/ImageLightbox.vue'
import { toast } from '../lib/toast'

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

// #20 rating
const starPick = ref(0)
const starHover = ref(0)
const feedback = ref('')
const ratingMsg = ref('')
const canRate = computed(
  () =>
    !!c.value &&
    !c.value.rating &&
    ['resolved', 'closed'].includes(c.value.status)
)
async function submitRating() {
  if (!starPick.value) return
  ratingMsg.value = ''
  try {
    await api.rate(id, starPick.value, feedback.value)
    await load()
    ratingMsg.value = 'Thank you for your feedback!'
    toast('Rating submitted ✓ · धन्यवाद')
  } catch (e: any) {
    ratingMsg.value = e.message
    toast(e.message || 'Rating failed', 'error')
  }
}

const FLOW = [
  'received',
  'acknowledged',
  'assigned',
  'in_progress',
  'resolved',
  'closed',
]

const LANG_LABEL: Record<string, string> = {
  en: 'English',
  hi: 'हिंदी (Hindi)',
  mr: 'मराठी (Marathi)',
  bn: 'বাংলা (Bengali)',
  te: 'తెలుగు (Telugu)',
  gu: 'ગુજરાતી (Gujarati)',
  pa: 'ਪੰਜਾਬੀ (Punjabi)',
  kn: 'ಕನ್ನಡ (Kannada)',
  ta: 'தமிழ் (Tamil)',
  ml: 'മലയാളം (Malayalam)',
  od: 'ଓଡ଼ିଆ (Odia)',
}
const summaryEntries = computed(() =>
  Object.entries(c.value?.official_summaries || {}).filter(
    ([, v]) => v && v.trim()
  )
)

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
const assignedContractor = computed(() =>
  contractors.value.find((x) => x.id === c.value?.contractor_id) || null
)
const daysPending = computed(() => {
  if (!c.value) return 0
  const ms = Date.now() - new Date(c.value.created_at).getTime()
  return Math.max(0, Math.floor(ms / 86400000))
})
const estCompletion = computed(() =>
  c.value?.estimated_completion_date
    ? new Date(c.value.estimated_completion_date).toLocaleDateString(
        undefined,
        { year: 'numeric', month: 'short', day: 'numeric' }
      )
    : null
)

// E1c/E2a — escalation history. Builds an array of {level, role, at}
// for each level that has fired (null entries dropped). Used to
// render the timestamp-pill strip on the detail view.
const ESCALATION_LEVELS = [
  { level: 1, role: 'manager', key: 'escalated_to_manager_at' },
  { level: 2, role: 'sr_manager', key: 'escalated_to_sr_manager_at' },
  { level: 3, role: 'secretary', key: 'escalated_to_secretary_at' },
  { level: 4, role: 'chairman', key: 'escalated_to_chairman_at' },
] as const
const escalationHistory = computed(() => {
  const cv = c.value
  if (!cv) return []
  return ESCALATION_LEVELS
    .map((lvl) => ({
      level: lvl.level,
      role: lvl.role,
      at: (cv as any)[lvl.key] as string | null,
    }))
    .filter((e) => e.at)
})
const currentEscalationLevel = computed(() => {
  const h = escalationHistory.value
  return h.length ? h[h.length - 1].level : 0
})
const isMajorIncident = computed(() => !!c.value?.major_incident)
const majorIncidentFlaggedAt = computed(() =>
  c.value?.major_incident_flagged_at
    ? new Date(c.value.major_incident_flagged_at).toLocaleString()
    : null
)
const clampedAtFmt = computed(() =>
  c.value?.clamped_at
    ? new Date(c.value.clamped_at).toLocaleString()
    : null
)

async function authorizeClamping() {
  if (!c.value) return
  if (!confirm(
    `Authorize clamping vehicle ${c.value.vehicle_plate || ''}? ` +
    'This action is logged + notifies the owner via WhatsApp.',
  )) return
  try {
    await api.authorizeClamping(id)
    await load()
    toast('Clamping authorized ✓ — owner notified')
  } catch (e: any) {
    toast(e.message || 'Clamping failed', 'error')
  }
}

onMounted(async () => {
  await load()
  // category-specific list, best-rated first (for manual override)
  contractors.value = c.value?.category
    ? await api.contractorsByCategory(c.value.category)
    : await api.contractors()
})

async function send() {
  if (!msg.value.trim()) return
  await api.addMessage(id, msg.value)
  msg.value = ''
  await load()
  toast('Note added ✓ · नोट जोड़ा')
}
async function assign() {
  if (!pick.value) return
  error.value = ''
  try {
    await api.assign(id, pick.value)
    await load()
    const name = contractors.value.find((x) => x.id === pick.value)?.name
    toast(`Assigned to ${name || 'contractor'} ✓`)
    pick.value = null
  } catch (e: any) {
    error.value = e.message
    toast(e.message || 'Assign failed', 'error')
  }
}
async function setStatus(s: string) {
  error.value = ''
  try {
    await api.setStatus(id, s)
    await load()
    toast(`Status → ${s.replace('_', ' ')} ✓`)
  } catch (e: any) {
    error.value = e.message
    toast(e.message || 'Update failed', 'error')
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

    <!-- E2d: prominent major-incident banner (full width, with reason +
         flagged_at). Sits above all other detail content so it's the
         first thing the eye lands on. -->
    <div
      v-if="isMajorIncident"
      class="rounded-lg bg-red-600 text-white px-4 py-3 flex items-start gap-3"
    >
      <AlertTriangle class="h-5 w-5 shrink-0 mt-0.5" />
      <div class="min-w-0 flex-1">
        <p class="font-bold">Major incident · प्रमुख घटना</p>
        <p v-if="c.major_incident_reason" class="text-sm mt-0.5">
          {{ c.major_incident_reason }}
        </p>
        <p v-if="majorIncidentFlaggedAt" class="text-xs text-red-100 mt-1">
          Flagged {{ majorIncidentFlaggedAt }}
        </p>
      </div>
    </div>

    <!-- P2/P4: parking-specific card. Renders only on Parking
         Management complaints. Shows the linked vehicle (or "plate
         not in registry") and the clamping state + action. -->
    <Card
      v-if="isParkingComplaint"
      :class="isClamped ? 'ring-2 ring-red-500/50' : ''"
    >
      <div class="flex items-center gap-2 mb-2">
        <Car class="h-5 w-5 text-primary" />
        <h2 class="font-semibold">Parking · पार्किंग</h2>
        <Badge
          v-if="isClamped"
          variant="urgent"
          class="ml-auto"
        >Clamped</Badge>
      </div>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p class="text-xs text-muted-foreground">Plate</p>
          <p class="font-mono font-bold mt-0.5">
            {{ c.vehicle_plate || '—' }}
          </p>
        </div>
        <div>
          <p class="text-xs text-muted-foreground">Violation</p>
          <p class="font-semibold mt-0.5 capitalize">
            {{ (c.violation_type || '—').replace(/_/g, ' ') }}
          </p>
        </div>
      </div>
      <p
        v-if="c.vehicle_plate && !c.vehicle_id"
        class="text-xs text-amber-700 dark:text-amber-300 mt-3 italic"
      >
        Plate not in vehicle registry. Add it via Vehicles to enable
        owner notifications.
      </p>
      <p
        v-if="c.vehicle_id"
        class="text-xs text-muted-foreground mt-3"
      >
        Linked to vehicle #{{ c.vehicle_id }} — owner notified on
        ticket creation.
      </p>
      <div v-if="isClamped" class="mt-3 pt-3 border-t">
        <p class="text-xs text-muted-foreground">
          Clamped by user #{{ c.clamping_authorized_by }} at
          {{ clampedAtFmt }}
        </p>
      </div>
      <button
        v-else-if="canAuthorizeClamping"
        class="mt-3 w-full inline-flex items-center justify-center gap-1.5 bg-red-600 hover:bg-red-700 text-white font-medium py-2 rounded-md"
        @click="authorizeClamping"
      >
        <Lock class="h-4 w-4" />
        Authorize clamping · क्लैम्पिंग
      </button>
    </Card>

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

    <!-- staff-facing AI summary (for officials who may not read the
         resident's language) -->
    <Card v-if="summaryEntries.length">
      <div class="flex items-center gap-2 mb-3">
        <Languages class="h-4 w-4 text-primary" />
        <h2 class="font-semibold">
          Summary for staff · स्टाफ हेतु सारांश
        </h2>
      </div>
      <div class="space-y-3">
        <div v-for="[code, txt] in summaryEntries" :key="code">
          <p
            class="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
          >
            {{ LANG_LABEL[code] || code }}
          </p>
          <p class="text-sm mt-0.5">{{ txt }}</p>
        </div>
      </div>
    </Card>

    <!-- key info cards (at a glance) -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Card>
        <p class="text-xs text-muted-foreground">Status · स्थिति</p>
        <div class="mt-2">
          <Badge :variant="c.status">{{
            c.status.replace('_', ' ')
          }}</Badge>
        </div>
      </Card>
      <Card>
        <p class="text-xs text-muted-foreground">
          Assigned to · सौंपा गया
        </p>
        <p
          v-if="c.assigned_staff_name"
          class="font-semibold mt-1 truncate flex items-center gap-1.5"
        >
          <span>{{ c.assigned_staff_name }}</span>
          <Badge variant="staff">staff</Badge>
        </p>
        <p
          v-else-if="assignedContractor"
          class="font-semibold mt-1 truncate"
        >
          {{ assignedContractor.name }}
          <span
            v-if="assignedContractor.average_rating"
            class="text-amber-500"
            >⭐ {{ assignedContractor.average_rating }}</span
          >
        </p>
        <p v-else class="font-semibold mt-1 text-muted-foreground">
          — none —
        </p>
      </Card>
      <Card>
        <p class="text-xs text-muted-foreground">
          Est. completion · अनुमानित
        </p>
        <p class="font-semibold mt-1">{{ estCompletion || '—' }}</p>
      </Card>
      <Card>
        <p class="text-xs text-muted-foreground">
          Days pending · दिन
        </p>
        <p class="text-2xl font-bold mt-1">{{ daysPending }}</p>
      </Card>
    </div>

    <!-- E1c/E2a: escalation history. Empty state = "no escalations yet"
         so staff can confirm the chain is dormant rather than missing.
         Each pill is one fired escalation event with its timestamp. -->
    <Card>
      <div class="flex items-center gap-2 mb-3">
        <TrendingUp class="h-4 w-4 text-primary" />
        <h2 class="font-semibold">
          Escalation history · वृद्धि इतिहास
        </h2>
        <span
          v-if="currentEscalationLevel > 0"
          class="ml-auto inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset"
          :class="{
            'bg-amber-100 text-amber-800 ring-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-700/40': currentEscalationLevel === 1,
            'bg-orange-200 text-orange-900 ring-orange-400 dark:bg-orange-900/50 dark:text-orange-100 dark:ring-orange-600': currentEscalationLevel === 2,
            'bg-red-200 text-red-900 ring-red-400 dark:bg-red-900/40 dark:text-red-200 dark:ring-red-700/40': currentEscalationLevel === 3,
            'bg-red-600 text-white ring-red-700/40': currentEscalationLevel === 4,
          }"
        >
          Current: L{{ currentEscalationLevel }}
        </span>
      </div>
      <div
        v-if="escalationHistory.length === 0"
        class="text-sm text-muted-foreground italic"
      >
        No escalations yet — within SLA.
      </div>
      <div v-else class="flex flex-wrap gap-2">
        <div
          v-for="e in escalationHistory"
          :key="e.level"
          class="rounded-md border bg-secondary/40 px-3 py-2 text-sm"
        >
          <p class="font-semibold capitalize">
            L{{ e.level }} · {{ e.role.replace('_', ' ') }}
          </p>
          <p class="text-xs text-muted-foreground mt-0.5">
            {{ e.at ? new Date(e.at).toLocaleString() : '' }}
          </p>
        </div>
      </div>
    </Card>

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

    <!-- #20 rating -->
    <Card v-if="c.rating">
      <div class="flex items-center gap-2">
        <Star
          v-for="n in 5"
          :key="n"
          class="h-5 w-5"
          :class="
            n <= c.rating.rating
              ? 'fill-amber-400 text-amber-400'
              : 'text-muted-foreground/40'
          "
        />
        <span class="text-sm font-medium ml-1"
          >{{ c.rating.rating }}/5</span
        >
      </div>
      <p
        v-if="c.rating.feedback"
        class="text-sm text-muted-foreground mt-2 italic"
      >
        “{{ c.rating.feedback }}”
      </p>
    </Card>

    <Card v-else-if="canRate">
      <h2 class="font-semibold mb-1">Rate this resolution</h2>
      <p class="text-sm text-muted-foreground mb-3">
        How was your experience?
      </p>
      <div class="flex items-center gap-1 mb-3">
        <button
          v-for="n in 5"
          :key="n"
          type="button"
          @click="starPick = n"
          @mouseenter="starHover = n"
          @mouseleave="starHover = 0"
        >
          <Star
            class="h-7 w-7 transition-colors"
            :class="
              n <= (starHover || starPick)
                ? 'fill-amber-400 text-amber-400'
                : 'text-muted-foreground/40'
            "
          />
        </button>
      </div>
      <textarea
        v-model="feedback"
        rows="3"
        placeholder="What was your experience?"
        class="w-full bg-background border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring mb-3"
      />
      <button
        :disabled="!starPick"
        class="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        @click="submitRating"
      >
        Submit Rating
      </button>
      <p
        v-if="ratingMsg"
        class="text-sm mt-2"
        :class="
          ratingMsg.startsWith('Thank')
            ? 'text-emerald-600 dark:text-emerald-400'
            : 'text-destructive'
        "
      >
        {{ ratingMsg }}
      </p>
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
        <div v-if="canResolve" class="flex gap-2 mt-4">
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
        <div v-if="canResolve">
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
        <div v-if="canAssign">
          <p class="text-sm text-muted-foreground mb-1">Contractor</p>
          <div
            v-if="assignedContractor"
            class="rounded-md border bg-secondary/40 px-3 py-2 mb-2"
          >
            <div class="flex items-center justify-between">
              <span class="font-semibold">{{
                assignedContractor.name
              }}</span>
              <span
                class="inline-flex items-center gap-1 text-amber-500 text-sm font-medium"
              >
                <Star class="h-4 w-4 fill-amber-400 text-amber-400" />
                {{ assignedContractor.average_rating ?? '—' }}
              </span>
            </div>
            <p class="text-xs text-muted-foreground mt-0.5">
              Auto-selected by rating · change below to override
            </p>
          </div>
          <select
            v-model="pick"
            class="w-full bg-background border rounded-md px-2 py-2 mb-2"
          >
            <option :value="null">
              {{ assignedContractor ? 'Change contractor…' : 'Select…' }}
            </option>
            <option v-for="ct in contractors" :key="ct.id" :value="ct.id">
              {{ ct.name }} — ⭐ {{ ct.average_rating ?? '—' }}
            </option>
          </select>
          <button
            class="w-full bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90"
            @click="assign"
          >
            {{ assignedContractor ? 'Reassign' : 'Assign' }}
          </button>
        </div>
        <!-- Read-only viewers see why the action panel is empty. -->
        <p
          v-if="!canResolve && !canAssign"
          class="text-sm text-muted-foreground italic"
        >
          Read-only access — sign in as a staff/manager/admin to act
          on this ticket.
        </p>
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
