export type ToastVariant = "success" | "error" | "info" | "warning"

export interface Toast {
  id: string
  message: string
  variant: ToastVariant
  duration: number
}

type ToastListener = (toasts: Toast[]) => void

let toasts: Toast[] = []
let counter = 0
const listeners = new Set<ToastListener>()

function notify() {
  for (const listener of listeners) {
    listener(toasts)
  }
}

export function subscribe(fn: ToastListener) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function dispatch(message: string, variant: ToastVariant, duration: number) {
  const id = `toast_${++counter}`
  toasts = [...toasts, { id, message, variant, duration }]
  notify()
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id)
    notify()
  }, duration)
}

type ToastArg = string | { message: string; variant?: ToastVariant; duration?: number }

export function toast(arg: ToastArg) {
  if (typeof arg === "string") {
    dispatch(arg, "info", 4000)
  } else {
    dispatch(arg.message, arg.variant ?? "info", arg.duration ?? 4000)
  }
}

toast.success = (message: string, duration?: number) => dispatch(message, "success", duration ?? 4000)
toast.error = (message: string, duration?: number) => dispatch(message, "error", duration ?? 4000)
toast.info = (message: string, duration?: number) => dispatch(message, "info", duration ?? 4000)
toast.warning = (message: string, duration?: number) => dispatch(message, "warning", duration ?? 4000)

export function dismiss(id: string) {
  toasts = toasts.filter((t) => t.id !== id)
  notify()
}
