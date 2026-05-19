<script setup lang="ts">
import {
  DialogRoot,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogClose,
  DialogTitle,
  VisuallyHidden,
} from 'reka-ui'
import { X } from 'lucide-vue-next'

defineProps<{ src: string | null }>()
const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <DialogRoot
    :open="!!src"
    @update:open="(v: boolean) => !v && emit('close')"
  >
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/80 animate-fade-in"
      />
      <DialogContent
        class="fixed inset-0 z-50 flex items-center justify-center p-6 focus:outline-none"
      >
        <VisuallyHidden><DialogTitle>Complaint photo</DialogTitle></VisuallyHidden>
        <img
          v-if="src"
          :src="src"
          alt="complaint photo full view"
          class="max-h-full max-w-full rounded-lg shadow-2xl animate-zoom-in"
        />
        <DialogClose
          class="absolute top-4 right-4 text-white/80 hover:text-white focus:outline-none"
          aria-label="Close"
        >
          <X class="h-7 w-7" />
        </DialogClose>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
