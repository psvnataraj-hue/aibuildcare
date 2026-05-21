<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ShieldCheck,
  RotateCcw,
  Check,
  X,
  AlertTriangle,
} from 'lucide-vue-next'
import {
  api,
  type EffectiveMatrix,
  type Override,
} from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'

// 11 permissions (rbac.py order, abbreviated for column headers)
const PERMS = [
  { id: 'file_complaint',        short: 'File',     full: 'File complaint' },
  { id: 'view_own',              short: 'ViewOwn',  full: 'View own complaints' },
  { id: 'view_all',              short: 'ViewAll',  full: 'View all complaints' },
  { id: 'assign',                short: 'Assign',   full: 'Assign to contractor/staff' },
  { id: 'resolve',               short: 'Resolve',  full: 'Update status / messages' },
  { id: 'escalate',              short: 'Escal',    full: 'Manually escalate' },
  { id: 'authorize_enforcement', short: 'AuthEnf',  full: 'Authorize enforcement (fines, clamping)' },
  { id: 'modify_staff',          short: 'Staff',    full: 'Manage staff' },
  { id: 'modify_config',         short: 'Config',   full: 'Modify society config' },
  { id: 'approve_reports',       short: 'Reports',  full: 'Approve reports' },
  { id: 'view_financial',        short: 'Finance',  full: 'View financial data' },
] as const

// 11 roles, with admin separated (hard-coded ALL, not overridable)
const EDITABLE_ROLES = [
  'resident', 'staff', 'contractor',
  'manager', 'sr_manager', 'secretary', 'chairman',
  'committee_member', 'enforcement_officer', 'viewer',
] as const
const ADMIN_ROLE = 'admin'

const loading = ref(true)
const matrix = ref<EffectiveMatrix | null>(null)
const overrides = ref<Override[]>([])
const busyCell = ref<string | null>(null)  // `${role}|${perm}` while flipping

async function load() {
  loading.value = true
  try {
    const [m, o] = await Promise.all([
      api.adminEffectiveMatrix(),
      api.adminListOverrides(),
    ])
    matrix.value = m
    overrides.value = o
  } catch (e: any) {
    toast(e.message || 'Failed to load permissions', 'error')
  } finally {
    loading.value = false
  }
}

// Lookup: `${role}|${permission}` -> Override (else not present)
const overrideMap = computed(() => {
  const m = new Map<string, Override>()
  for (const o of overrides.value) {
    m.set(`${o.role}|${o.permission}`, o)
  }
  return m
})

function isGranted(role: string, perm: string): boolean {
  const roleSet = matrix.value?.roles[role] ?? []
  return roleSet.includes(perm)
}
function isOverride(role: string, perm: string): boolean {
  return overrideMap.value.has(`${role}|${perm}`)
}

async function toggle(role: string, perm: string) {
  const key = `${role}|${perm}`
  if (busyCell.value) return
  const current = isGranted(role, perm)
  busyCell.value = key
  try {
    await api.adminUpsertOverride(role, perm, !current)
    toast(
      `${role} · ${perm} → ${!current ? 'GRANTED' : 'REVOKED'} ✓`,
    )
    await load()
  } catch (e: any) {
    toast(e.message || 'Failed to update override', 'error')
  } finally {
    busyCell.value = null
  }
}

async function revert(role: string, perm: string) {
  if (busyCell.value) return
  const key = `${role}|${perm}`
  busyCell.value = key
  try {
    await api.adminClearOverride(role, perm)
    toast(`${role} · ${perm} reverted to default ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Revert failed', 'error')
  } finally {
    busyCell.value = null
  }
}

onMounted(load)
</script>

<template>
  <Spinner v-if="loading" />
  <div v-else class="space-y-6">
    <!-- header -->
    <div>
      <h1 class="text-2xl font-bold flex items-center gap-2">
        <ShieldCheck class="h-6 w-6 text-primary" />
        Permission overrides · अनुमति
      </h1>
      <p class="text-sm text-muted-foreground mt-1">
        Per-society role × permission matrix. Click a cell to flip the
        permission for that role; cells with a coloured ring are
        explicit overrides (different from the default matrix). Use
        the ↺ button to revert an override back to the default.
        Admin (OEM superuser) is shown for reference but cannot be
        overridden.
      </p>
    </div>

    <!-- safety banner -->
    <div
      class="rounded-lg bg-amber-100 dark:bg-amber-900/40 px-4 py-3 flex items-start gap-2 text-amber-900 dark:text-amber-200 text-sm"
    >
      <AlertTriangle class="h-5 w-5 shrink-0 mt-0.5" />
      <div>
        <p class="font-semibold">Changes take effect immediately.</p>
        <p class="mt-1">
          Granting <strong>modify_config</strong> or
          <strong>authorize_enforcement</strong> to lower-trust roles
          (resident/contractor/viewer) is a privilege-escalation
          surface. Audit overrides regularly.
        </p>
      </div>
    </div>

    <!-- matrix table -->
    <Card class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b">
            <th class="text-left font-semibold py-2 pr-3 sticky left-0 bg-card">
              Role
            </th>
            <th
              v-for="p in PERMS"
              :key="p.id"
              :title="p.full"
              class="text-center font-semibold py-2 px-2 text-[11px] uppercase tracking-wide whitespace-nowrap"
            >
              {{ p.short }}
            </th>
          </tr>
        </thead>
        <tbody>
          <!-- admin row (informational only) -->
          <tr class="border-b bg-secondary/40">
            <td class="py-2 pr-3 sticky left-0 bg-secondary/40">
              <p class="font-semibold">{{ ADMIN_ROLE }}</p>
              <p class="text-[10px] text-muted-foreground italic">
                OEM — all permissions, not overridable
              </p>
            </td>
            <td
              v-for="p in PERMS"
              :key="p.id"
              class="text-center py-2 px-2"
            >
              <Check class="h-4 w-4 text-emerald-600 inline" />
            </td>
          </tr>
          <!-- editable rows -->
          <tr
            v-for="role in EDITABLE_ROLES"
            :key="role"
            class="border-b"
          >
            <td class="py-2 pr-3 font-medium sticky left-0 bg-card capitalize">
              {{ role.replace('_', ' ') }}
            </td>
            <td
              v-for="p in PERMS"
              :key="p.id"
              class="text-center py-2 px-2"
            >
              <div
                class="inline-flex items-center gap-0.5"
                :class="isOverride(role, p.id) ? 'rounded p-0.5 ring-2 ring-amber-400 dark:ring-amber-500' : ''"
                :title="
                  isOverride(role, p.id)
                    ? 'Explicit override — click to flip or use ↺ to revert'
                    : 'Default — click to override'
                "
              >
                <button
                  type="button"
                  :disabled="busyCell === `${role}|${p.id}`"
                  class="h-6 w-6 rounded inline-flex items-center justify-center transition-colors disabled:opacity-50"
                  :class="
                    isGranted(role, p.id)
                      ? 'bg-emerald-100 hover:bg-emerald-200 dark:bg-emerald-900/40 dark:hover:bg-emerald-800/60 text-emerald-700 dark:text-emerald-300'
                      : 'bg-red-100 hover:bg-red-200 dark:bg-red-900/40 dark:hover:bg-red-800/60 text-red-700 dark:text-red-300'
                  "
                  @click="toggle(role, p.id)"
                >
                  <Check v-if="isGranted(role, p.id)" class="h-3.5 w-3.5" />
                  <X v-else class="h-3.5 w-3.5" />
                </button>
                <button
                  v-if="isOverride(role, p.id)"
                  type="button"
                  :disabled="busyCell === `${role}|${p.id}`"
                  class="h-6 w-6 rounded inline-flex items-center justify-center text-muted-foreground hover:bg-secondary disabled:opacity-50"
                  title="Revert to default"
                  @click="revert(role, p.id)"
                >
                  <RotateCcw class="h-3 w-3" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </Card>

    <!-- override summary -->
    <Card v-if="overrides.length">
      <h2 class="font-semibold mb-2">
        Active overrides ({{ overrides.length }})
      </h2>
      <ul class="text-sm space-y-1">
        <li
          v-for="o in overrides"
          :key="`${o.role}|${o.permission}`"
          class="flex items-center gap-2"
        >
          <span class="font-medium capitalize">
            {{ o.role.replace('_', ' ') }}
          </span>
          <span class="text-muted-foreground">·</span>
          <span class="font-mono text-xs">{{ o.permission }}</span>
          <span class="text-muted-foreground">→</span>
          <span
            class="font-semibold"
            :class="o.granted ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'"
          >
            {{ o.granted ? 'GRANTED' : 'REVOKED' }}
          </span>
        </li>
      </ul>
    </Card>
    <Card v-else class="text-sm text-muted-foreground italic">
      No overrides — every role currently uses the default permission
      matrix.
    </Card>
  </div>
</template>
