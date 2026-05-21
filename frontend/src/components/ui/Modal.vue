<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { X } from 'lucide-vue-next'
import Card from './Card.vue'

const props = defineProps<{
  open: boolean
  /** Tailwind max-width class for the modal card. Default 'max-w-lg'. */
  maxWidth?: string
  /** Header title text (optional — omit if header is custom-rendered). */
  title?: string
  /** Disable Esc-to-close (e.g. while a destructive request is in-flight). */
  persistent?: boolean
}>()
const emit = defineEmits<{
  (e: 'close'): void
}>()

function onKey(ev: KeyboardEvent) {
  if (props.persistent) return
  if (ev.key === 'Escape' && props.open) {
    ev.stopPropagation()
    emit('close')
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop fades in/out -->
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
        @click.self="persistent || emit('close')"
      >
        <!-- Card scales + fades in/out -->
        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="open"
            :class="['w-full', maxWidth || 'max-w-lg', 'max-h-[90vh] overflow-y-auto']"
          >
            <Card>
              <div
                v-if="title || $slots.header"
                class="flex items-center justify-between mb-4"
              >
                <h2 class="font-semibold flex items-center gap-2">
                  <slot name="header">{{ title }}</slot>
                </h2>
                <button
                  type="button"
                  class="h-8 w-8 rounded-md hover:bg-secondary inline-flex items-center justify-center"
                  @click="emit('close')"
                >
                  <X class="h-4 w-4" />
                </button>
              </div>
              <slot />
              <div
                v-if="$slots.footer"
                class="flex gap-2 pt-3"
              >
                <slot name="footer" />
              </div>
            </Card>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
