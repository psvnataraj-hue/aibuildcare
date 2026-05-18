<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type Contractor } from '../api'

const list = ref<Contractor[]>([])
onMounted(async () => {
  list.value = await api.contractors()
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-4">Contractors</h1>
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="ct in list"
        :key="ct.id"
        class="bg-white rounded-xl shadow p-4"
      >
        <div class="font-semibold">{{ ct.name }}</div>
        <div class="text-sm text-slate-500">{{ ct.specialty }}</div>
        <div class="text-sm mt-2">{{ ct.phone }}</div>
      </div>
      <div v-if="!list.length" class="text-slate-400">No contractors</div>
    </div>
  </div>
</template>
