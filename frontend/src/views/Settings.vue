<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'

const loading = ref(true)
const maxJobs = ref('10')
const lbEnabled = ref(true)
const msg = ref('')

onMounted(async () => {
  const cfg = await api.adminConfig()
  maxJobs.value = cfg.max_pending_jobs_per_contractor ?? '10'
  lbEnabled.value =
    (cfg.load_balancing_enabled ?? 'true').toLowerCase() === 'true'
  loading.value = false
})

async function save() {
  msg.value = ''
  try {
    await api.setAdminConfig(
      'max_pending_jobs_per_contractor',
      String(maxJobs.value)
    )
    await api.setAdminConfig(
      'load_balancing_enabled',
      lbEnabled.value ? 'true' : 'false'
    )
    msg.value = 'Saved ✓ · सहेजा गया'
    toast('Settings saved ✓ · सहेजा गया')
  } catch (e: any) {
    msg.value = e.message || 'Save failed'
    toast(e.message || 'Save failed', 'error')
  }
}
</script>

<template>
  <Spinner v-if="loading">Loading…</Spinner>
  <div v-else class="space-y-5 max-w-xl">
    <h1 class="text-xl font-bold">
      Settings · <span class="text-muted-foreground">सेटिंग्स</span>
    </h1>

    <Card>
      <h2 class="font-semibold mb-1">Load balancing · लोड बैलेंसिंग</h2>
      <p class="text-sm text-muted-foreground mb-4">
        Spread work so no contractor is overloaded.
      </p>

      <label
        class="flex items-center justify-between gap-3 py-3 border-b cursor-pointer"
      >
        <span class="font-medium">Enabled · चालू</span>
        <input
          v-model="lbEnabled"
          type="checkbox"
          class="h-6 w-6 accent-primary"
        />
      </label>

      <div class="py-4">
        <label class="block font-medium mb-1"
          >Max pending jobs per contractor</label
        >
        <p class="text-xs text-muted-foreground mb-2">
          अधिकतम लंबित कार्य प्रति ठेकेदार
        </p>
        <input
          v-model="maxJobs"
          type="number"
          min="1"
          class="w-32 h-12 bg-background border rounded-lg px-3 text-lg focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <button
        class="mt-2 h-12 w-full rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90"
        @click="save"
      >
        Save · सहेजें
      </button>
      <p
        v-if="msg"
        class="text-sm mt-3"
        :class="
          msg.includes('✓')
            ? 'text-emerald-600 dark:text-emerald-400'
            : 'text-destructive'
        "
      >
        {{ msg }}
      </p>
    </Card>
  </div>
</template>
