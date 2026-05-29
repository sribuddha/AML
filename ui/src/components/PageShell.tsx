import type { ReactNode } from "react"

interface PageShellProps {
  title: string
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
}

export default function PageShell({ title, description, actions, children }: PageShellProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{title}</h2>
          {description && (
            <p className="text-sm text-slate-500 mt-0.5">{description}</p>
          )}
        </div>
        {actions && (
          <div className="shrink-0 flex items-center gap-2">{actions}</div>
        )}
      </div>
      {children}
    </div>
  )
}
