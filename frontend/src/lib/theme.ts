import { ref } from 'vue'

const KEY = 'aibuildcare-theme'
export const isDark = ref(false)

function apply() {
  document.documentElement.classList.toggle('dark', isDark.value)
}

export function initTheme() {
  const saved = localStorage.getItem(KEY)
  isDark.value = saved
    ? saved === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches
  apply()
}

export function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem(KEY, isDark.value ? 'dark' : 'light')
  apply()
}
