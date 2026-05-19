<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badge = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-secondary text-secondary-foreground',
        urgent:
          'border-destructive/30 bg-destructive/15 text-destructive',
        high: 'border-amber-500/30 bg-amber-500/15 text-amber-600 dark:text-amber-400',
        normal: 'border-transparent bg-muted text-muted-foreground',
        received:
          'border-transparent bg-sky-500/15 text-sky-600 dark:text-sky-400',
        acknowledged:
          'border-transparent bg-indigo-500/15 text-indigo-600 dark:text-indigo-400',
        assigned:
          'border-transparent bg-violet-500/15 text-violet-600 dark:text-violet-400',
        in_progress:
          'border-transparent bg-amber-500/15 text-amber-600 dark:text-amber-400',
        resolved:
          'border-transparent bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
        closed: 'border-transparent bg-muted text-muted-foreground',
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
