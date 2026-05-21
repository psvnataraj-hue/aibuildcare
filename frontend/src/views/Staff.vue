<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  Users,
  UserPlus,
  Pencil,
  Trash2,
  RotateCcw,
  X,
  CheckCircle2,
  XCircle,
  Phone,
  Mail,
  MessageSquare,
} from 'lucide-vue-next'
import {
  api,
  PERMISSIONS,
  type Staff,
  type StaffCategory,
  type StaffCreatePayload,
  type StaffPatchPayload,
} from '../api'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Spinner from '../components/ui/Spinner.vue'
import { toast } from '../lib/toast'
import { can } from '../lib/currentUser'

// E3h: read-only viewers (roles with VIEW_ALL but not MODIFY_STAFF)
// can see the list; add/edit/delete/category-mgmt UI hides for them.
const canModify = computed(() => can(PERMISSIONS.MODIFY_STAFF))

// 24 categories from the seed (kept in sync with ComplaintCard ICONS dict)
const CATEGORIES = [
  'AC/Cooling', 'Plumbing', 'Electrical', 'Elevator',
  'Housekeeping', 'Security', 'Carpentry', 'Gardening',
  'Pest Control', 'Garbage/Waste', 'Water Supply',
  'Sewage/Drainage', 'Lighting', 'Painting', 'CCTV/Intercom',
  'Generator/Power Backup', 'Fire Safety', 'Civil/Structural',
  'Swimming Pool', 'Parking Management', 'Noise/Visitor',
  'Sports/Gym/Clubhouse', "Children's Play Area", 'Other',
]

const SKILL_LEVELS = ['junior', 'senior', 'expert'] as const

const loading = ref(true)
const includeInactive = ref(false)
const staff = ref<Staff[]>([])

// "create" form state (modal)
const showCreate = ref(false)
const create = ref<StaffCreatePayload>(emptyCreate())
function emptyCreate(): StaffCreatePayload {
  return {
    name: '',
    phone_primary: '',
    phone_secondary: '',
    email: '',
    whatsapp_enabled: true,
    sms_fallback: true,
    shift_pattern: '',
    notes: '',
    categories: [],
  }
}

// "edit" form state (modal)
const editingId = ref<number | null>(null)
const edit = ref<StaffPatchPayload>({})
const editing = computed(() =>
  editingId.value
    ? staff.value.find((s) => s.id === editingId.value) || null
    : null
)

// category-assign form state (inside edit modal)
const catPick = ref<StaffCategory>({
  category: 'Plumbing',
  primary_category: false,
  skill_level: 'junior',
})

// Polish — busy state on submit buttons (prevents double-click).
const submitting = ref(false)

// Polish — Esc-to-close on whichever modal is open.
function onKey(ev: KeyboardEvent) {
  if (ev.key !== 'Escape') return
  if (showCreate.value) showCreate.value = false
  else if (editingId.value !== null) editingId.value = null
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))

async function load() {
  loading.value = true
  try {
    staff.value = await api.listStaff(includeInactive.value)
  } catch (e: any) {
    toast(e.message || 'Failed to load staff', 'error')
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  if (!create.value.name?.trim() || !create.value.phone_primary?.trim()) {
    toast('Name + primary phone are required', 'error')
    return
  }
  // strip empty optional strings so backend sees nulls, not ''
  const payload: StaffCreatePayload = { ...create.value }
  for (const k of [
    'phone_secondary', 'email', 'shift_pattern', 'notes',
  ] as const) {
    if (payload[k] === '') (payload as any)[k] = null
  }
  submitting.value = true
  try {
    await api.createStaff(payload)
    toast(`Staff "${create.value.name}" added ✓`)
    showCreate.value = false
    create.value = emptyCreate()
    await load()
  } catch (e: any) {
    toast(e.message || 'Create failed', 'error')
  } finally {
    submitting.value = false
  }
}

function openEdit(s: Staff) {
  editingId.value = s.id
  edit.value = {
    name: s.name,
    phone_primary: s.phone_primary,
    phone_secondary: s.phone_secondary || '',
    email: s.email || '',
    whatsapp_enabled: s.whatsapp_enabled,
    sms_fallback: s.sms_fallback,
    shift_pattern: s.shift_pattern || '',
    notes: s.notes || '',
    active: s.active,
  }
}
async function submitEdit() {
  if (!editingId.value) return
  const payload: StaffPatchPayload = { ...edit.value }
  for (const k of [
    'phone_secondary', 'email', 'shift_pattern', 'notes',
  ] as const) {
    if (payload[k] === '') (payload as any)[k] = null
  }
  submitting.value = true
  try {
    await api.updateStaff(editingId.value, payload)
    toast('Staff updated ✓')
    editingId.value = null
    await load()
  } catch (e: any) {
    toast(e.message || 'Update failed', 'error')
  } finally {
    submitting.value = false
  }
}
async function deactivate(s: Staff) {
  if (!confirm(`Deactivate staff "${s.name}"? (Soft-delete, can be re-activated.)`)) return
  try {
    await api.deactivateStaff(s.id)
    toast(`"${s.name}" deactivated ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Deactivate failed', 'error')
  }
}
async function reactivate(s: Staff) {
  try {
    await api.updateStaff(s.id, { active: true })
    toast(`"${s.name}" reactivated ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Reactivate failed', 'error')
  }
}

async function addCategoryToEditing() {
  if (!editingId.value) return
  try {
    await api.addStaffCategory(editingId.value, { ...catPick.value })
    toast(`Category "${catPick.value.category}" assigned ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Category add failed', 'error')
  }
}
async function removeCategory(staffId: number, category: string) {
  try {
    await api.removeStaffCategory(staffId, category)
    toast(`Category "${category}" removed ✓`)
    await load()
  } catch (e: any) {
    toast(e.message || 'Category remove failed', 'error')
  }
}

function toggleCreateCategory(cat: string) {
  const cats = create.value.categories ?? []
  const idx = cats.findIndex((c) => c.category === cat)
  if (idx >= 0) {
    cats.splice(idx, 1)
  } else {
    cats.push({
      category: cat,
      primary_category: cats.length === 0,
      skill_level: 'junior',
    })
  }
  create.value.categories = cats
}

onMounted(load)
</script>

<template>
  <Spinner v-if="loading" />
  <div v-else class="space-y-6">
    <!-- header -->
    <div class="flex items-start justify-between gap-3 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold flex items-center gap-2">
          <Users class="h-6 w-6 text-primary" />
          Staff Management · स्टाफ प्रबंधन
        </h1>
        <p class="text-sm text-muted-foreground mt-1">
          In-house staff routed by category. Auto-assignment prefers
          staff over contractors (E1b routing).
        </p>
      </div>
      <div class="flex items-center gap-2">
        <label class="inline-flex items-center gap-2 text-sm">
          <input
            v-model="includeInactive"
            type="checkbox"
            class="rounded"
            @change="load"
          />
          Show inactive
        </label>
        <button
          v-if="canModify"
          class="inline-flex items-center gap-1 bg-primary text-primary-foreground px-4 py-2 rounded-md font-medium hover:bg-primary/90"
          @click="showCreate = true"
        >
          <UserPlus class="h-4 w-4" /> Add staff
        </button>
      </div>
    </div>

    <!-- empty state -->
    <Card v-if="staff.length === 0" class="text-center py-10">
      <Users class="h-10 w-10 mx-auto text-muted-foreground/50" />
      <p class="mt-3 font-semibold">No staff yet</p>
      <p class="text-sm text-muted-foreground mt-1">
        Add staff to enable category-aware auto-routing. Complaints
        without an in-house staff match will fall through to
        contractors.
      </p>
      <button
        v-if="canModify"
        class="mt-4 inline-flex items-center gap-1 bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90"
        @click="showCreate = true"
      >
        <UserPlus class="h-4 w-4" /> Add first staff
      </button>
    </Card>

    <!-- list -->
    <div v-else class="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      <Card
        v-for="s in staff"
        :key="s.id"
        :class="!s.active ? 'opacity-60 ring-1 ring-muted' : ''"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <p class="font-semibold truncate">{{ s.name }}</p>
            <p class="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
              <Phone class="h-3 w-3" /> {{ s.phone_primary }}
              <span v-if="s.whatsapp_enabled" class="text-emerald-600">
                · WA ✓
              </span>
            </p>
            <p
              v-if="s.email"
              class="text-xs text-muted-foreground mt-0.5 flex items-center gap-1"
            >
              <Mail class="h-3 w-3" /> {{ s.email }}
            </p>
            <p
              v-if="s.shift_pattern"
              class="text-xs text-muted-foreground mt-0.5 flex items-center gap-1"
            >
              <MessageSquare class="h-3 w-3" /> {{ s.shift_pattern }}
            </p>
          </div>
          <div class="flex items-center gap-1">
            <CheckCircle2
              v-if="s.active"
              class="h-4 w-4 text-emerald-600"
              title="active"
            />
            <XCircle
              v-else
              class="h-4 w-4 text-muted-foreground"
              title="inactive"
            />
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-1">
          <span
            v-for="c in s.categories"
            :key="c.category"
            class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset"
            :class="
              c.primary_category
                ? 'bg-primary/15 text-primary ring-primary/30'
                : 'bg-secondary text-secondary-foreground ring-black/5'
            "
          >
            {{ c.category }}
            <span class="text-[10px] opacity-70">· {{ c.skill_level }}</span>
            <span v-if="c.primary_category" class="text-[10px]">★</span>
          </span>
          <span
            v-if="s.categories.length === 0"
            class="text-[11px] italic text-muted-foreground"
          >
            No categories assigned
          </span>
        </div>

        <div v-if="canModify" class="mt-4 flex gap-2">
          <button
            class="flex-1 inline-flex items-center justify-center gap-1 border rounded-md px-2 py-1.5 text-sm hover:bg-secondary"
            @click="openEdit(s)"
          >
            <Pencil class="h-3.5 w-3.5" /> Edit
          </button>
          <button
            v-if="s.active"
            class="inline-flex items-center justify-center gap-1 border rounded-md px-2 py-1.5 text-sm hover:bg-destructive/10 text-destructive"
            @click="deactivate(s)"
          >
            <Trash2 class="h-3.5 w-3.5" /> Deactivate
          </button>
          <button
            v-else
            class="inline-flex items-center justify-center gap-1 border rounded-md px-2 py-1.5 text-sm hover:bg-emerald-50 dark:hover:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
            @click="reactivate(s)"
          >
            <RotateCcw class="h-3.5 w-3.5" /> Reactivate
          </button>
        </div>
      </Card>
    </div>

    <!-- CREATE modal — Transition wrappers for fade-in backdrop + scale-in card -->
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
            <UserPlus class="h-5 w-5 text-primary" />
            Add new staff
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
            <span class="text-xs text-muted-foreground">Name *</span>
            <input
              v-model="create.name"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              placeholder="e.g. Ramesh Plumber"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Primary phone *</span>
            <input
              v-model="create.phone_primary"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              placeholder="+91XXXXXXXXXX"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Secondary phone</span>
            <input
              v-model="create.phone_secondary"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Email</span>
            <input
              v-model="create.email"
              type="email"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Shift pattern</span>
            <input
              v-model="create.shift_pattern"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
              placeholder="e.g. Mon-Sat 9am-6pm"
            />
          </label>
          <div class="flex items-center gap-4 text-sm">
            <label class="inline-flex items-center gap-2">
              <input
                v-model="create.whatsapp_enabled"
                type="checkbox"
                class="rounded"
              />
              WhatsApp enabled
            </label>
            <label class="inline-flex items-center gap-2">
              <input
                v-model="create.sms_fallback"
                type="checkbox"
                class="rounded"
              />
              SMS fallback
            </label>
          </div>
          <div>
            <p class="text-xs text-muted-foreground mb-1">
              Categories (click to toggle; first selected becomes
              primary)
            </p>
            <div class="flex flex-wrap gap-1">
              <button
                v-for="cat in CATEGORIES"
                :key="cat"
                type="button"
                class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset"
                :class="
                  create.categories?.some((c) => c.category === cat)
                    ? 'bg-primary/15 text-primary ring-primary/30'
                    : 'bg-secondary text-muted-foreground ring-black/5 hover:bg-secondary/80'
                "
                @click="toggleCreateCategory(cat)"
              >
                {{ cat }}
              </button>
            </div>
          </div>
          <div class="flex gap-2 pt-2">
            <button
              :disabled="submitting"
              class="flex-1 bg-primary text-primary-foreground py-2 rounded-md hover:bg-primary/90 disabled:opacity-60"
              @click="submitCreate"
            >
              {{ submitting ? 'Creating…' : 'Create' }}
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
            Edit staff
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
            <span class="text-xs text-muted-foreground">Name</span>
            <input
              v-model="edit.name"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Primary phone</span>
            <input
              v-model="edit.phone_primary"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Email</span>
            <input
              v-model="edit.email"
              type="email"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="text-xs text-muted-foreground">Shift pattern</span>
            <input
              v-model="edit.shift_pattern"
              type="text"
              class="mt-1 w-full bg-background border rounded-md px-3 py-2 text-sm"
            />
          </label>
          <div class="flex items-center gap-4 text-sm">
            <label class="inline-flex items-center gap-2">
              <input
                v-model="edit.whatsapp_enabled"
                type="checkbox"
                class="rounded"
              />
              WhatsApp enabled
            </label>
            <label class="inline-flex items-center gap-2">
              <input
                v-model="edit.sms_fallback"
                type="checkbox"
                class="rounded"
              />
              SMS fallback
            </label>
          </div>

          <!-- per-staff category management -->
          <div
            v-if="editing"
            class="border-t pt-3"
          >
            <p class="text-xs text-muted-foreground mb-2 font-semibold">
              Categories assigned
            </p>
            <div class="flex flex-wrap gap-1 mb-3">
              <span
                v-for="c in editing.categories"
                :key="c.category"
                class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset"
                :class="
                  c.primary_category
                    ? 'bg-primary/15 text-primary ring-primary/30'
                    : 'bg-secondary text-secondary-foreground ring-black/5'
                "
              >
                {{ c.category }} · {{ c.skill_level }}
                <span v-if="c.primary_category">★</span>
                <button
                  type="button"
                  class="ml-1 hover:text-destructive"
                  @click="removeCategory(editing.id, c.category)"
                >
                  <X class="h-3 w-3" />
                </button>
              </span>
              <span
                v-if="editing.categories.length === 0"
                class="text-[11px] italic text-muted-foreground"
              >
                None assigned
              </span>
            </div>
            <div class="flex items-end gap-2">
              <label class="flex-1">
                <span class="text-xs text-muted-foreground">
                  Add category
                </span>
                <select
                  v-model="catPick.category"
                  class="mt-1 w-full bg-background border rounded-md px-2 py-2 text-sm"
                >
                  <option v-for="cat in CATEGORIES" :key="cat">
                    {{ cat }}
                  </option>
                </select>
              </label>
              <label>
                <span class="text-xs text-muted-foreground">Skill</span>
                <select
                  v-model="catPick.skill_level"
                  class="mt-1 w-full bg-background border rounded-md px-2 py-2 text-sm"
                >
                  <option v-for="s in SKILL_LEVELS" :key="s">
                    {{ s }}
                  </option>
                </select>
              </label>
              <label class="inline-flex items-center gap-1 text-xs pb-2">
                <input
                  v-model="catPick.primary_category"
                  type="checkbox"
                  class="rounded"
                />
                Primary
              </label>
              <button
                class="bg-primary text-primary-foreground px-3 py-2 rounded-md text-sm hover:bg-primary/90"
                @click="addCategoryToEditing"
              >
                Add
              </button>
            </div>
          </div>

          <div class="flex gap-2 pt-2 border-t">
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
