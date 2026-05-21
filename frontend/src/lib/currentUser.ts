/**
 * E3h — reactive current-user store backed by GET /api/v1/auth/me.
 *
 * The frontend calls `loadCurrentUser()` once after login and on app
 * boot when a token already exists. Components read `currentUser` for
 * identity and use `can(perm)` to gate UI by effective permissions.
 *
 * Permission strings come from the backend matrix (see backend/app/
 * services/rbac.py and the PERMISSIONS map in api.ts).
 */
import { ref } from 'vue'
import { api, type CurrentUser } from '../api'

export const currentUser = ref<CurrentUser | null>(null)
const loading = ref(false)

export async function loadCurrentUser(): Promise<CurrentUser | null> {
  if (loading.value) return currentUser.value
  loading.value = true
  try {
    currentUser.value = await api.me()
  } catch {
    // Token may be expired / revoked; let route guards redirect to /login.
    currentUser.value = null
  } finally {
    loading.value = false
  }
  return currentUser.value
}

export function clearCurrentUser(): void {
  currentUser.value = null
}

/**
 * Permission check. Returns false until the user has been loaded
 * (defensive default — hide gated UI rather than flash it).
 * Admin always has every permission (matrix has the full list).
 */
export function can(permission: string): boolean {
  const u = currentUser.value
  if (!u) return false
  return u.permissions.includes(permission)
}

/** Any-of: returns true if the user has at least one of these. */
export function canAny(permissions: string[]): boolean {
  return permissions.some((p) => can(p))
}
