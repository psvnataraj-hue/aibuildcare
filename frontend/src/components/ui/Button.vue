<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const button = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:scale-[.98] disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground shadow-sm hover:brightness-110 hover:shadow-md',
        outline:
          'border-2 border-input bg-card hover:border-primary hover:text-primary',
        ghost: 'hover:bg-secondary',
        destructive:
          'bg-destructive text-destructive-foreground hover:brightness-110',
      },
      size: {
        default: 'h-11 px-5 text-sm',
        sm: 'h-9 px-3 text-xs',
        lg: 'h-12 px-6 text-base',
        icon: 'h-11 w-11',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  }
)
type Props = {
  variant?: VariantProps<typeof button>['variant']
  size?: VariantProps<typeof button>['size']
}
const props = defineProps<Props>()
</script>

<template>
  <button :class="cn(button({ variant: props.variant, size: props.size }))">
    <slot />
  </button>
</template>
