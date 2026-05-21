<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Car,
  Plus,
  Pencil,
  Trash2,
  RotateCcw,
  X,
  Search,
  Phone,
} from 'lucide-vue-next'
import {
  api,
  PERMISSIONS,
  type Vehicle,
  type VehicleCreatePayload,
  type VehiclePatchPayload,
} from '../api'
import Card from '../components/ui/Card.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'
import { can } from '../lib/currentUser'

const VEHICLE_TYPES = [
  '', 'car', 'two-wheeler', 'scooter', 'bike', 'suv',
  'van', 'auto', 'truck', 'other',
] as const

const canModify = computed(() => can(PERMISSIONS.MODIFY_STAFF))

const loading = ref(true)
const includeInactive = ref(false)
const search = ref('')
const vehicles = ref<Vehicle[]>([])

// add modal
const showCreate = ref(false)
const create = ref<VehicleCreatePayload>(emptyCreate())
function emptyCreate(): VehicleCreatePayload {
  return {
    plate_number: '',
    owner_unit_number: '',
    owner_name: '',
    owner_phone: '',
    vehicle_type: '',
    make_model: '',
    color: '',
    notes: '',
  }
}

// edit modal
const editingId = ref<number | null>(null)
const edit = ref<VehiclePatchPayload>({})

async function load() {
  loading.value = true
  try {
    vehicles.value = await api.listVehicles(
      includeInactive.value, search.value.trim() || undefined,
    )
  } catch (e: any) {
    toast(e.message || 'Failed to load vehicles', 'error')
  } finally {
    loading.value = false
  }
}

// debounce-ish: re-fetch when the search term settles
let searchTimer: number | undefined
watch(search, () => {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(load, 250)
})
watch(includeInactive, load)

function normalizeBlanks<T extends Record<string, any>>(obj: T): T {
  const out: any = { ...obj }
  for (const k of Object.keys(out)) {
    if (out[k] === '') out[k] = null
  }
  return out as T
}

async function submitCreate() {
  if (!create.value.plate_number?.trim()) {
    toast('Plate number is required', 'error')
    return
  }
  submitting.value = true
  try {
    await api.createVehicle(normalizeBlanks(create.value))
    toast(`Vehicle ${create.value.plate_number} registered ✓`)
    showCreate.value = false
    create.value = emptyCreate()
    await load()
  } catch (e: any) {
    toast(e.message || 'Create failed', 'error')
  } finally {
    submitting.value = false
  }
}

function openEdit(v: Vehicle) {
  editingId.value = v.id
  edit.value = {
    plate_number: v.plate_number,
    owner_unit_number: v.owner_unit_number || '',
    owner_name: v.owner_name || '',
    owner_phone: v.owner_phone || '',
    vehicle_type: v.vehicle_type || '',
    make_model: v.make_model || '',
    color: v.color || '',
    notes: v.notes || '',
    active: v.active,
  }
}

async function submitEdit() {
  if (!editingId.value) return
  submitting.value = true
  try {
    await api.updateVehicle(editingId.value, normalizeBlanks(edit.value))
    toast('Vehicle updated ✓')
    editingId.value = null
    await load()
  } catch (e: any) {
    toast(e.message || 'Update failed', 'error')
  } finally {
    submitting.value = false
  }
}

async function deactivate(v: Vehicle) {
  if (!confirm(`Deactivate ${v.plate_number}? Soft-delete; can be reactivated.`)) return
  try {
    await api.deactivateVehicle(v.id)
    toast(`${v.plate_number} deactivated ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Deactivate failed', 'error')
  }
}

async function reactivate(v: Vehicle) {
  try {
    await api.updateVehicle(v.id, { active: true })
    toast(`${v.plate_number} reactivated ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Reactivate failed', 'error')
  }
}

// Polish — busy state on submit buttons + Esc-to-close modal.
const submitting = ref(false)
function onKey(ev: KeyboardEvent) {
  if (ev.key !== 'Escape') return
  if (showCreate.value) showCreate.value = false
  else if (editingId.value !== null) editingId.value = null
}
onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Spinner v-if="loading" />
  <div v-else class="space-y-6">
    <!-- header -->
    <div class="flex items-start justify-between gap-3 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold flex items-center gap-2">
          <Car class="h-6 w-6 text-primary" />
          Vehicles · वाहन निर्देशिका
        </h1>
        <p class="text-sm text-muted-foreground mt-1">
          Plate → owner registry. Parking complaints auto-link to a
          vehicle by plate so the owner gets a WhatsApp the moment
          the ticket lands.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <label class="inline-flex items-center gap-2 text-sm">
          <input
            v-model="includeInactive"
            type="checkbox"
            class="rounded"
          />
          Show inactive
        </label>
        <button
          v-if="canModify"
          class="inline-flex items-center gap-1 bg-primary text-primary-foreground px-4 py-2 rounded-md font-medium hover:bg-primary/90"
          @click="showCreate = true"
        >
          <Plus class="h-4 w-4" /> Register vehicle
        </button>
      </div>
    </div>

    <!-- search -->
    <Card>
      <label class="block">
        <span class="text-sm font-medium flex items-center gap-1.5 mb-2">
          <Search class="h-4 w-4 text-muted-foreground" />
          Search by plate
        </span>
        <input
          v-model="search"
          type="text"
          placeholder="e.g. MH01 or partial match"
          class="w-full bg-background border rounded-md px-3 py-2 text-sm"
        />
      </label>
    </Card>

    <!-- empty -->
    <Card v-if="vehicles.length === 0" class="text-center py-10">
      <Car class="h-10 w-10 mx-auto text-muted-foreground/50" />
      <p class="mt-3 font-semibold">No vehicles registered</p>
      <p class="text-sm text-muted-foreground mt-1">
        Add vehicles to enable auto-linking + owner WhatsApp notifications
        on parking complaints.
      </p>
      <button
        v-if="canModify"
        class="mt-4 inline-flex items-center gap-1 bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90"
        @click="showCreate = true"
      >
        <Plus class="h-4 w-4" /> Register first vehicle
      </button>
    </Card>

    <!-- list -->
    <div v-else class="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      <Card
        v-for="v in vehicles"
        :key="v.id"
        :class="!v.active ? 'opacity-60 ring-1 ring-muted' : ''"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <p class="font-mono font-bold text-base truncate">
              {{ v.plate_number }}
            </p>
            <p
              v-if="v.owner_name || v.owner_unit_number"
              class="text-sm mt-0.5 truncate"
            >
              {{ v.owner_name || 'unknown owner' }}
              <span
                v-if="v.owner_unit_number"
                class="text-muted-foreground"
              >· flat {{ v.owner_unit_number }}</span>
            </p>
            <p
              v-if="v.owner_phone"
              class="text-xs text-muted-foreground mt-0.5 flex items-center gap-1"
            >
              <Phone class="h-3 w-3" /> {{ v.owner_phone }}
            </p>
            <p
              v-if="v.vehicle_type || v.make_model || v.color"
              class="text-xs text-muted-foreground mt-1 truncate"
            >
              {{ [v.vehicle_type, v.make_model, v.color]
                  .filter(Boolean).join(' · ') }}
            </p>
          </div>
        </div>

        <div v-if="canModify" class="mt-4 flex gap-2">
          <button
            class="flex-1 inline-flex items-center justify-center gap-1 border rounded-md px-2 py-1.5 text-sm hover:bg-secondary"
            @click="openEdit(v)"
          >
            <Pencil class="h-3.5 w-3.5" /> Edit
          </button>
          <button
            v-if="v.active"
            class="inline-flex items-center justify-center gap-1 border rounded-md px-2 py-1.5 text-sm hover:bg-destructive/10 text-destructive"
            @click="deactivate(v)"
          >
            <Trash2 class="h-3.5 w-3.5" /> Deactivate
          </button>
          <button
            v-else
            class="inline-flex items-center justify-center gap-1 border rounded-md px-2 py-1.5 text-sm hover:bg-emerald-50 dark:hover:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
            @click="reactivate(v)"
          >
            <RotateCcw class="h-3.5 w-3.5" /> Reactivate
          </button>
        </div>
      </Card>
    </div>

    <!-- CREATE modal — fade transition -->
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      @click.self="showCreate = false"
    >
      <Card class="w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold flex items-center gap-2">
            <Plus class="h-5 w-5 text-primary" />
            Register vehicle
          </h2>
          <button
            class="h-8 w-8 rounded-md hover:bg-secondary inline-flex items-center justify-center"
            @click="showCreate = false"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
        <div class="space-y-3">
          <label class="block">
            <span class="text-xs text-muted-foreground">Plate number *</span>
            <input
              v-model="create.plate_number"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm font-mono uppercase"
              placeholder="e.g. MH01AB1234"
            />
            <span class="text-[10px] text-muted-foreground">
              Spaces + dashes are stripped automatically.
            </span>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-xs text-muted-foreground">Owner name</span>
              <input
                v-model="create.owner_name"
                type="text"
                class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              />
            </label>
            <label class="block">
              <span class="text-xs text-muted-foreground">Unit / flat</span>
              <input
                v-model="create.owner_unit_number"
                type="text"
                class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
                placeholder="e.g. 5B"
              />
            </label>
          </div>
          <label class="block">
            <span class="text-xs text-muted-foreground">Owner phone</span>
            <input
              v-model="create.owner_phone"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              placeholder="+91XXXXXXXXXX"
            />
          </label>
          <div class="grid grid-cols-3 gap-3">
            <label class="block">
              <span class="text-xs text-muted-foreground">Type</span>
              <select
                v-model="create.vehicle_type"
                class="mt-1 w-full bg-background border rounded-md px-2 py-2 text-sm"
              >
                <option v-for="t in VEHICLE_TYPES" :key="t" :value="t">
                  {{ t || '—' }}
                </option>
              </select>
            </label>
            <label class="block col-span-2">
              <span class="text-xs text-muted-foreground">Make / model</span>
              <input
                v-model="create.make_model"
                type="text"
                class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
                placeholder="e.g. Maruti Swift"
              />
            </label>
          </div>
          <label class="block">
            <span class="text-xs text-muted-foreground">Color</span>
            <input
              v-model="create.color"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Notes</span>
            <textarea
              v-model="create.notes"
              rows="2"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <div class="flex gap-2 pt-2">
            <button
              :disabled="submitting"
              class="flex-1 bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90 disabled:opacity-60"
              @click="submitCreate"
            >
              {{ submitting ? 'Registering…' : 'Register' }}
            </button>
            <button
              :disabled="submitting"
              class="border rounded-md px-4 hover:bg-secondary disabled:opacity-60"
              @click="showCreate = false"
            >
              Cancel
            </button>
          </div>
        </div>
      </Card>
    </div>
    </Transition>

    <!-- EDIT modal -->
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div
      v-if="editingId"
      class="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      @click.self="editingId = null"
    >
      <Card class="w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold flex items-center gap-2">
            <Pencil class="h-5 w-5 text-primary" />
            Edit vehicle
          </h2>
          <button
            class="h-8 w-8 rounded-md hover:bg-secondary inline-flex items-center justify-center"
            @click="editingId = null"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
        <div class="space-y-3">
          <label class="block">
            <span class="text-xs text-muted-foreground">Plate number</span>
            <input
              v-model="edit.plate_number"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm font-mono uppercase"
            />
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-xs text-muted-foreground">Owner name</span>
              <input
                v-model="edit.owner_name"
                type="text"
                class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              />
            </label>
            <label class="block">
              <span class="text-xs text-muted-foreground">Unit / flat</span>
              <input
                v-model="edit.owner_unit_number"
                type="text"
                class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              />
            </label>
          </div>
          <label class="block">
            <span class="text-xs text-muted-foreground">Owner phone</span>
            <input
              v-model="edit.owner_phone"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <div class="grid grid-cols-3 gap-3">
            <label class="block">
              <span class="text-xs text-muted-foreground">Type</span>
              <select
                v-model="edit.vehicle_type"
                class="mt-1 w-full bg-background border rounded-md px-2 py-2 text-sm"
              >
                <option v-for="t in VEHICLE_TYPES" :key="t" :value="t">
                  {{ t || '—' }}
                </option>
              </select>
            </label>
            <label class="block col-span-2">
              <span class="text-xs text-muted-foreground">Make / model</span>
              <input
                v-model="edit.make_model"
                type="text"
                class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              />
            </label>
          </div>
          <label class="block">
            <span class="text-xs text-muted-foreground">Color</span>
            <input
              v-model="edit.color"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Notes</span>
            <textarea
              v-model="edit.notes"
              rows="2"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="inline-flex items-center gap-2 text-sm">
            <input
              v-model="edit.active"
              type="checkbox"
              class="rounded"
            />
            Active
          </label>
          <div class="flex gap-2 pt-2">
            <button
              :disabled="submitting"
              class="flex-1 bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90 disabled:opacity-60"
              @click="submitEdit"
            >
              {{ submitting ? 'Saving…' : 'Save' }}
            </button>
            <button
              :disabled="submitting"
              class="border rounded-md px-4 hover:bg-secondary disabled:opacity-60"
              @click="editingId = null"
            >
              Cancel
            </button>
          </div>
        </div>
      </Card>
    </div>
    </Transition>
  </div>
</template>
