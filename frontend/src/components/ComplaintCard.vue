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
} from 'lucide-vue-next'
import Card from './ui/Card.vue'
import Badge from './ui/Badge.vue'
import type { Complaint } from '../api'

const props = defineProps<{ c: Complaint }>()
const router = useRouter()

const ICONS: Record<string, any> = {
  'AC/Cooling': Snowflake,
  Plumbing: Droplets,
  Electrical: Zap,
  Elevator: ArrowUpDown,
  Housekeeping: Trash2,
  Security: Shield,
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
</script>

<template>
  <Card class="hover:ring-1 hover:ring-ring transition">
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
        </div>
        <p class="text-sm mt-2 text-muted-foreground line-clamp-2">
          {{ staffSummary }}
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
