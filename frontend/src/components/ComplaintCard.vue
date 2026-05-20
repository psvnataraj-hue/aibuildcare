<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Snowflake,
  Droplets,
  Zap,
  ArrowUpDown,
  Trash2,
  Shield,
  Wrench,
  Image as ImageIcon,
  Hammer,
  Sprout,
  Bug,
  Trash,
  Droplet,
  Filter,
  Lightbulb,
  Brush,
  Video,
  Power,
  Flame,
  Building2,
  Waves,
  Car,
  Volume2,
  Dumbbell,
  Baby,
  User,
  AlertTriangle,
  TrendingUp,
} from 'lucide-vue-next'
import Card from './ui/Card.vue'
import Badge from './ui/Badge.vue'
import type { Complaint } from '../api'

const props = defineProps<{ c: Complaint }>()
const router = useRouter()

const ICONS: Record<string, any> = {
  // original 6
  'AC/Cooling': Snowflake,
  Plumbing: Droplets,
  Electrical: Zap,
  Elevator: ArrowUpDown,
  Housekeeping: Trash2,
  Security: Shield,
  // E1 expanded set
  Carpentry: Hammer,
  Gardening: Sprout,
  'Pest Control': Bug,
  'Garbage/Waste': Trash,
  'Water Supply': Droplet,
  'Sewage/Drainage': Filter,
  Lighting: Lightbulb,
  Painting: Brush,
  'CCTV/Intercom': Video,
  'Generator/Power Backup': Power,
  'Fire Safety': Flame,
  'Civil/Structural': Building2,
  'Swimming Pool': Waves,
  'Parking Management': Car,
  'Noise/Visitor': Volume2,
  'Sports/Gym/Clubhouse': Dumbbell,
  "Children's Play Area": Baby,
}
const icon = computed(() => ICONS[props.c.category || ''] || Wrench)

// prefer the staff summary (first configured language); fall back to
// the raw text when no summary was generated
const staffSummary = computed(() => {
  const s = props.c.official_summaries
  if (s) {
    const first = Object.values(s).find((v) => v && v.trim())
    if (first) return first
  }
  return props.c.raw_text
})

const ageDays = computed(() => {
  const d = Math.floor(
    (Date.now() - new Date(props.c.created_at).getTime()) / 86400000
  )
  return d <= 0 ? 'today · आज' : `${d}d ago · ${d} दिन`
})
const eta = computed(() =>
  props.c.estimated_completion_date
    ? new Date(props.c.estimated_completion_date).toLocaleDateString(
        undefined,
        { month: 'short', day: 'numeric', year: 'numeric' }
      )
    : null
)

// E1c/E2a — derive the current escalation level from which timestamps
// the cron-driven escalation job has populated. 0 = not escalated.
const escalationLevel = computed(() => {
  const c = props.c
  if (c.escalated_to_chairman_at) return 4
  if (c.escalated_to_secretary_at) return 3
  if (c.escalated_to_sr_manager_at) return 2
  if (c.escalated_to_manager_at) return 1
  return 0
})
const escalationLabel = computed(() => {
  const map: Record<number, string> = {
    1: 'L1 manager',
    2: 'L2 sr.mgr',
    3: 'L3 secretary',
    4: 'L4 chairman',
  }
  return map[escalationLevel.value] || ''
})

// E2d — major-incident is a 0/1 integer column on the complaint row.
const isMajorIncident = computed(() => !!props.c.major_incident)
</script>

<template>
  <Card
    class="hover:ring-1 hover:ring-ring transition"
    :class="isMajorIncident ? 'ring-2 ring-red-500/60' : ''"
  >
    <!-- E2d: major-incident banner — only renders when flagged.
         Sits at the very top so a glance at the card surfaces the
         flag before any other content. -->
    <div
      v-if="isMajorIncident"
      class="-mx-4 -mt-4 mb-3 px-4 py-2 bg-red-600 text-white rounded-t-md flex items-center gap-2 text-sm font-semibold"
    >
      <AlertTriangle class="h-4 w-4 shrink-0" />
      <span>Major incident · प्रमुख घटना</span>
      <span
        v-if="c.major_incident_reason"
        class="ml-1 text-xs font-normal text-red-100 truncate"
      >· {{ c.major_incident_reason }}</span>
    </div>
    <div class="flex items-start gap-3">
      <div
        class="h-10 w-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0"
      >
        <component :is="icon" class="h-5 w-5" />
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-semibold"
            >Unit {{ c.unit_number || '—' }}</span
          >
          <span class="text-sm text-muted-foreground"
            >· {{ c.category || 'Other' }}</span
          >
          <ImageIcon
            v-if="c.media_urls"
            class="h-3.5 w-3.5 text-muted-foreground"
          />
          <span class="text-xs text-muted-foreground ml-auto">{{
            ageDays
          }}</span>
        </div>
        <div class="flex items-center gap-2 mt-2 flex-wrap">
          <Badge :variant="c.status">{{
            c.status.replace('_', ' ')
          }}</Badge>
          <Badge :variant="c.priority">{{ c.priority }}</Badge>
          <!-- E1c/E2a: escalation badge — color escalates from amber
               (L1) to red (L4). Only shows once escalation has fired. -->
          <span
            v-if="escalationLevel > 0"
            class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset"
            :class="{
              'bg-amber-100 text-amber-800 ring-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-700/40': escalationLevel === 1,
              'bg-orange-200 text-orange-900 ring-orange-400 dark:bg-orange-900/50 dark:text-orange-100 dark:ring-orange-600': escalationLevel === 2,
              'bg-red-200 text-red-900 ring-red-400 dark:bg-red-900/40 dark:text-red-200 dark:ring-red-700/40': escalationLevel === 3,
              'bg-red-600 text-white ring-red-700/40': escalationLevel === 4,
            }"
          >
            <TrendingUp class="h-3.5 w-3.5" />
            {{ escalationLabel }}
          </span>
        </div>
        <p class="text-sm mt-2 text-muted-foreground line-clamp-2">
          {{ staffSummary }}
        </p>
        <p
          v-if="c.assigned_staff_name"
          class="text-xs mt-2 flex items-center gap-1"
        >
          <User class="h-3.5 w-3.5 text-primary" />
          <span class="text-muted-foreground">Assigned · सौंपा गया:</span>
          <strong>{{ c.assigned_staff_name }}</strong>
          <Badge variant="staff" class="ml-1">staff</Badge>
        </p>
        <p v-if="eta" class="text-xs mt-2">
          <span class="text-muted-foreground"
            >Est. completion · अनुमानित:</span
          >
          <strong>{{ eta }}</strong>
        </p>
      </div>
    </div>
    <button
      class="mt-4 w-full h-12 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90"
      @click="router.push(`/complaints/${c.id}`)"
    >
      View Details · विवरण
    </button>
  </Card>
</template>
