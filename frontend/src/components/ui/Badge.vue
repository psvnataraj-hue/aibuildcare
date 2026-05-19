<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badge = cva(
  'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold capitalize tracking-wide shadow-sm ring-1 ring-inset',
  {
    variants: {
      variant: {
        default: 'bg-secondary text-secondary-foreground ring-black/5',
        urgent:
          'bg-red-600 text-white ring-red-700/40',
        high: 'bg-amber-500 text-white ring-amber-600/40',
        normal: 'bg-slate-200 text-slate-700 ring-slate-300 dark:bg-slate-700 dark:text-slate-200 dark:ring-slate-600',
        received:
          'bg-sky-600 text-white ring-sky-700/40',
        acknowledged:
          'bg-indigo-600 text-white ring-indigo-700/40',
        assigned:
          'bg-violet-600 text-white ring-violet-700/40',
        in_progress:
          'bg-amber-500 text-white ring-amber-600/40',
        resolved:
          'bg-emerald-600 text-white ring-emerald-700/40',
        closed:
          'bg-slate-400 text-white ring-slate-500/40 dark:bg-slate-600',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)
const props = defineProps<{
  variant?: VariantProps<typeof badge>['variant']
}>()
</script>

<template>
  <span :class="cn(badge({ variant: props.variant || 'default' }))">
    <slot />
  </span>
</template>
