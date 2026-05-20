export function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ');
}

const buttonBase =
  'inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-sm border border-transparent px-4 py-2 font-sans text-[13px] font-semibold text-white transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none disabled:translate-y-0';

export const ui = {
  card: 'rounded-md border border-border bg-bg-card p-5',
  cardSm: 'rounded-md border border-border bg-bg-card px-4 py-3.5',
  tag: 'inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium text-blue-300 border border-blue-500/20 bg-blue-500/10',
  input:
    'w-full rounded-sm border border-border bg-bg-base px-3 py-2 font-sans text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-blue-500 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]',
  label: 'mb-1.5 block text-[11px] text-text-muted',
  sectionTitle: 'mb-3 text-[13px] font-semibold text-text-secondary',
  button: {
    base: buttonBase,
    primary: 'bg-blue-600 hover:-translate-y-px hover:bg-blue-700 hover:shadow-[0_4px_14px_rgba(37,99,235,0.4)]',
    secondary: 'border-border bg-bg-card text-text-primary hover:border-border-lite hover:bg-bg-card-hover',
    ghost: 'bg-transparent text-text-secondary hover:bg-white/5 hover:text-text-primary',
    danger: 'border-red-500/25 bg-red-500/15 text-red-400 hover:bg-red-500/25',
    sm: 'px-[11px] py-[5px] text-xs',
    lg: 'px-[22px] py-2.5 text-sm',
  },
  badge: {
    base: 'inline-flex items-center gap-[5px] rounded-full px-[9px] py-[3px] text-[11px] font-semibold',
    normal: 'bg-green-400/12 text-green-400',
    warn: 'bg-amber-400/12 text-amber-400',
    danger: 'bg-red-400/15 text-red-400',
    info: 'bg-blue-500/12 text-blue-400',
  },
  dot: {
    base: 'relative size-[7px] shrink-0 rounded-full',
    normal: 'bg-green-400',
    warn: 'bg-amber-400 shadow-[0_0_6px_var(--color-amber-500)]',
    danger:
      'bg-red-400 shadow-[0_0_8px_var(--color-red-500)] after:absolute after:inset-0 after:rounded-full after:bg-red-400 after:content-[""] after:animate-pulse-ring',
  },
  radioOption:
    'min-w-20 flex-1 cursor-pointer rounded-sm border border-border bg-bg-base px-3 py-2 text-center text-xs font-medium text-text-secondary transition-all hover:border-border-lite hover:text-text-primary',
  radioSelected: 'border-blue-500 bg-blue-500/8 text-blue-400',
};

export function buttonClass(...variants: Array<keyof typeof ui.button>) {
  return cn(ui.button.base, ...variants.map((variant) => ui.button[variant]));
}

export function badgeClass(kind: keyof typeof ui.badge) {
  return cn(ui.badge.base, ui.badge[kind]);
}

export function dotClass(kind: keyof typeof ui.dot) {
  return cn(ui.dot.base, ui.dot[kind]);
}
