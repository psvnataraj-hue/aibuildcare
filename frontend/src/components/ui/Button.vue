<script setup lang="ts">
const props = defineProps<{ variant?: string; size?: string }>()
const V: Record<string, string> = {
  default: 'bg-primary text-primary-foreground hover:bg-primary/90',
  outline: 'border border-input bg-card hover:bg-secondary',
  ghost: 'hover:bg-secondary',
  destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
}
const S: Record<string, string> = {
  default: 'h-9 px-4 text-sm',
  sm: 'h-8 px-3 text-xs',
  icon: 'h-9 w-9',
}
</script>

<template>
  <button
    class="inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:pointer-events-none"
    :class="[V[props.variant || 'default'], S[props.size || 'default']]"
  >
    <slot />
  </button>
</template>
