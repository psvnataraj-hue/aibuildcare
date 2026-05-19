import { ref } from 'vue'

export interface Toast {
  id: number
  msg: string
  kind: 'success' | 'error'
}

export const toasts = ref<Toast[]>([])
let seq = 0

export function toast(msg: string, kind: 'success' | 'error' = 'success') {
  const id = ++seq
  toasts.value.push({ id, msg, kind })
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }, 3200)
}
