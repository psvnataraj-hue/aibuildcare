<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Wrench, Phone } from 'lucide-vue-next'
import { api, type Contractor } from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'

const list = ref<Contractor[]>([])
const loading = ref(true)
onMounted(async () => {
  list.value = await api.contractors()
  loading.value = false
})
</script>

<template>
  <Spinner v-if="loading" />
  <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
    <Card v-for="ct in list" :key="ct.id">
      <div class="flex items-start gap-3">
        <div
          class="h-10 w-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0"
        >
          <Wrench class="h-5 w-5" />
        </div>
        <div class="min-w-0">
          <div class="font-semibold truncate">{{ ct.name }}</div>
          <div class="text-sm text-muted-foreground">{{ ct.specialty }}</div>
          <div
            class="text-sm mt-2 flex items-center gap-1 text-muted-foreground"
          >
            <Phone class="h-3.5 w-3.5" /> {{ ct.phone }}
          </div>
        </div>
      </div>
    </Card>
    <p v-if="!list.length" class="text-muted-foreground">No contractors</p>
  </div>
</template>
