<script setup lang="ts">
import { CheckCircle2, XCircle } from 'lucide-vue-next'
import { toasts } from '../../lib/toast'
</script>

<template>
  <div
    class="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 pointer-events-none"
  >
    <TransitionGroup name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold text-white shadow-lg"
        :class="t.kind === 'success' ? 'bg-emerald-600' : 'bg-red-600'"
      >
        <CheckCircle2 v-if="t.kind === 'success'" class="h-5 w-5" />
        <XCircle v-else class="h-5 w-5" />
        {{ t.msg }}
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
