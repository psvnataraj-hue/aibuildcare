import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'
import { initTheme } from './lib/theme'
import { hasToken } from './api'
import { loadCurrentUser } from './lib/currentUser'

initTheme()

// E3h: if a token is already cached (returning user), pre-load
// identity + permissions before mount so the nav doesn't flash
// every link on first paint. Fire-and-forget — failures are handled
// inside loadCurrentUser (sets currentUser back to null; route
// guards then redirect to /login on next navigation).
if (hasToken()) {
  loadCurrentUser()
}

createApp(App).use(createPinia()).use(router).mount('#app')
