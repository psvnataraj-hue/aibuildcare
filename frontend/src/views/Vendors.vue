<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Store,
  Search,
  MessageCircle,
  Star,
  Phone,
} from 'lucide-vue-next'
import { api, type Vendor } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'

// 24 categories — mirrors Staff.vue + ComplaintCard ICONS dict.
// (Keeping the source of truth as code, not an extra API call.)
const CATEGORIES = [
  'AC/Cooling', 'Plumbing', 'Electrical', 'Elevator',
  'Housekeeping', 'Security', 'Carpentry', 'Gardening',
  'Pest Control', 'Garbage/Waste', 'Water Supply',
  'Sewage/Drainage', 'Lighting', 'Painting', 'CCTV/Intercom',
  'Generator/Power Backup', 'Fire Safety', 'Civil/Structural',
  'Swimming Pool', 'Parking Management', 'Noise/Visitor',
  'Sports/Gym/Clubhouse', "Children's Play Area", 'Other',
] as const

const category = ref<string>('Plumbing')
const vendors = ref<Vendor[]>([])
const loading = ref(false)
const fetched = ref(false)

async function load() {
  if (!category.value) return
  loading.value = true
  try {
    vendors.value = await api.vendorsByCategory(category.value)
    fetched.value = true
  } catch (e: any) {
    toast(e.message || 'Failed to load vendors', 'error')
    vendors.value = []
  } finally {
    loading.value = false
  }
}

// Re-fetch when category changes
watch(category, () => {
  load()
})

onMounted(load)

const ratingStars = (r: number | null) => {
  if (r === null) return 0
  return Math.round(Math.min(5, Math.max(0, r)))
}
</script>

<template>
  <div class="space-y-6">
    <!-- header -->
    <div>
      <h1 class="text-2xl font-bold flex items-center gap-2">
        <Store class="h-6 w-6 text-primary" />
        Vendor Directory · विक्रेता निर्देशिका
      </h1>
      <p class="text-sm text-muted-foreground mt-1">
        Society-vetted contractors who handle personal jobs for
        residents. Tap "Chat on WhatsApp" to message them directly
        with a pre-filled opener.
      </p>
    </div>

    <!-- category picker -->
    <Card>
      <label class="block">
        <span class="text-sm font-medium flex items-center gap-1.5 mb-2">
          <Search class="h-4 w-4 text-muted-foreground" />
          Category · श्रेणी
        </span>
        <select
          v-model="category"
          class="w-full bg-background border rounded-md px-3 py-2 text-sm"
        >
          <option v-for="c in CATEGORIES" :key="c" :value="c">
            {{ c }}
          </option>
        </select>
      </label>
    </Card>

    <!-- results -->
    <Spinner v-if="loading" />

    <Card
      v-else-if="fetched && vendors.length === 0"
      class="text-center py-10"
    >
      <Store class="h-10 w-10 mx-auto text-muted-foreground/50" />
      <p class="mt-3 font-semibold">
        No vendors for "{{ category }}" yet
      </p>
      <p class="text-sm text-muted-foreground mt-1">
        The society admin hasn't onboarded any contractor for this
        category, or none have opted in to personal-job referrals.
      </p>
    </Card>

    <div
      v-else-if="vendors.length"
      class="grid gap-3 md:grid-cols-2 lg:grid-cols-3"
    >
      <Card v-for="v in vendors" :key="v.id">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <p class="font-semibold truncate flex items-center gap-1.5">
              {{ v.name }}
              <span
                v-if="v.primary_category"
                class="inline-flex items-center text-[10px] font-bold rounded-full px-1.5 py-0.5 bg-primary/15 text-primary ring-1 ring-primary/30"
                title="This is the contractor's primary category"
              >
                Primary ★
              </span>
            </p>
            <p
              v-if="v.specialty"
              class="text-xs text-muted-foreground mt-0.5 truncate"
            >
              {{ v.specialty }}
            </p>
            <p
              v-if="v.phone"
              class="text-xs text-muted-foreground mt-1 flex items-center gap-1"
            >
              <Phone class="h-3 w-3" /> {{ v.phone }}
            </p>
          </div>
          <div
            v-if="v.average_rating !== null"
            class="flex items-center gap-0.5 shrink-0"
            :title="`Average rating ${v.average_rating}`"
          >
            <Star
              v-for="n in 5"
              :key="n"
              class="h-3.5 w-3.5"
              :class="
                n <= ratingStars(v.average_rating)
                  ? 'fill-amber-400 text-amber-400'
                  : 'text-muted-foreground/30'
              "
            />
            <span class="text-xs ml-1 font-medium">
              {{ v.average_rating?.toFixed(1) }}
            </span>
          </div>
        </div>

        <a
          v-if="v.wa_link"
          :href="v.wa_link"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-4 w-full h-10 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-medium inline-flex items-center justify-center gap-1.5 text-sm"
        >
          <MessageCircle class="h-4 w-4" />
          Chat on WhatsApp · व्हाट्सएप
        </a>
        <p
          v-else
          class="mt-4 text-xs text-muted-foreground italic text-center py-2"
        >
          No phone on file — contact the society office
        </p>
      </Card>
    </div>
  </div>
</template>
