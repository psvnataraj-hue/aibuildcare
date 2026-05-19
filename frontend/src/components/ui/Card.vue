<script setup lang="ts">
defineProps<{ padded?: boolean; hover?: boolean }>()
</script>

<template>
  <div
    class="bg-card text-card-foreground rounded-xl border elev"
    :class="[
      padded !== false ? 'p-5' : '',
      hover ? 'elev-hover cursor-pointer' : '',
    ]"
  >
    <slot />
  </div>
</template>
