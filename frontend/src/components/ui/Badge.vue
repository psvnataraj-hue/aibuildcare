<script setup lang="ts">
const props = defineProps<{ variant?: string }>()

const MAP: Record<string, string> = {
  urgent: 'bg-destructive/15 text-destructive ring-1 ring-destructive/30',
  high: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 ring-1 ring-amber-500/30',
  normal: 'bg-muted text-muted-foreground',
  received: 'bg-sky-500/15 text-sky-600 dark:text-sky-400',
  acknowledged: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400',
  assigned: 'bg-violet-500/15 text-violet-600 dark:text-violet-400',
  in_progress: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  resolved: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  closed: 'bg-muted text-muted-foreground',
  default: 'bg-secondary text-secondary-foreground',
}
const cls = () => MAP[props.variant || 'default'] || MAP.default
</script>

<template>
  <span
    class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize"
    :class="cls()"
  >
    <slot />
  </span>
</template>
