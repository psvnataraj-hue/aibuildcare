<script setup lang="ts">
defineProps<{ padded?: boolean }>()
</script>

<template>
  <div
    class="bg-card text-card-foreground rounded-lg border shadow-sm"
    :class="padded !== false ? 'p-5' : ''"
  >
    <slot />
  </div>
</template>
