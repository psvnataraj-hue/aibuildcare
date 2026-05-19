<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'
</script>

<template>
  <div class="flex items-center justify-center gap-2 text-muted-foreground py-10">
    <Loader2 class="h-5 w-5 animate-spin" />
    <span class="text-sm"><slot>Loading…</slot></span>
  </div>
</template>
