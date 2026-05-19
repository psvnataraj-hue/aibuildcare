<script setup lang="ts" generic="T extends Record<string, any>">
import { computed, ref } from 'vue'
import { ChevronsUpDown, ChevronUp, ChevronDown } from 'lucide-vue-next'

type Col = { key: string; label: string; sortable?: boolean }
const props = defineProps<{ columns: Col[]; rows: T[] }>()
const emit = defineEmits<{ (e: 'rowClick', row: T): void }>()

const sortKey = ref<string | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')

function toggleSort(c: Col) {
  if (c.sortable === false) return
  if (sortKey.value === c.key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = c.key
    sortDir.value = 'asc'
  }
}

const sorted = computed(() => {
  if (!sortKey.value) return props.rows
  const k = sortKey.value
  const d = sortDir.value === 'asc' ? 1 : -1
  return [...props.rows].sort((a, b) => {
    const av = a[k] ?? ''
    const bv = b[k] ?? ''
    return av < bv ? -d : av > bv ? d : 0
  })
})
</script>

<template>
  <div class="relative w-full overflow-x-auto">
    <table class="w-full caption-bottom text-sm">
      <thead class="[&_tr]:border-b">
        <tr class="border-b text-left text-muted-foreground">
          <th
            v-for="c in columns"
            :key="c.key"
            class="h-11 px-4 font-medium select-none"
            :class="c.sortable === false ? '' : 'cursor-pointer hover:text-foreground'"
            @click="toggleSort(c)"
          >
            <span class="inline-flex items-center gap-1">
              {{ c.label }}
              <template v-if="c.sortable !== false">
                <ChevronsUpDown
                  v-if="sortKey !== c.key"
                  class="h-3.5 w-3.5 opacity-50"
                />
                <ChevronUp
                  v-else-if="sortDir === 'asc'"
                  class="h-3.5 w-3.5"
                />
                <ChevronDown v-else class="h-3.5 w-3.5" />
              </template>
            </span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, i) in sorted"
          :key="i"
          class="border-b last:border-0 transition-colors hover:bg-secondary/50 cursor-pointer"
          @click="emit('rowClick', row)"
        >
          <td v-for="c in columns" :key="c.key" class="p-4 align-middle">
            <slot :name="c.key" :row="row" :value="row[c.key]">
              {{ row[c.key] ?? '—' }}
            </slot>
          </td>
        </tr>
        <tr v-if="!sorted.length">
          <td
            :colspan="columns.length"
            class="p-8 text-center text-muted-foreground"
          >
            <slot name="empty">No records</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
