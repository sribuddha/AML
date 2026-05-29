import { cn } from "../lib/cn"

export interface SearchField {
  key: string
  label: string
  type?: "text" | "date" | "select"
  placeholder?: string
  options?: { label: string; value: string }[]
}

interface SearchFormProps {
  fields: SearchField[]
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  onSearch: () => void
  onClear?: () => void
  columns?: 1 | 2 | 3 | 4
}

export default function SearchForm({
  fields,
  values,
  onChange,
  onSearch,
  onClear,
  columns = 3,
}: SearchFormProps) {
  return (
    <div className="space-y-3">
      <div
        className={cn(
          "grid gap-3",
          columns === 1 && "grid-cols-1",
          columns === 2 && "grid-cols-1 sm:grid-cols-2",
          columns === 3 && "grid-cols-1 sm:grid-cols-3",
          columns === 4 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
        )}
      >
        {fields.map((field) => {
          const base = cn(
            "px-3 py-2 border border-slate-300 rounded-lg text-sm",
            "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
          )
          if (field.type === "select" && field.options) {
            return (
              <select
                key={field.key}
                value={values[field.key] ?? ""}
                onChange={(e) => onChange(field.key, e.target.value)}
                className={base}
              >
                {field.options.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            )
          }
          return (
            <input
              key={field.key}
              type={field.type === "date" ? "date" : "text"}
              placeholder={field.placeholder || field.label}
              value={values[field.key] ?? ""}
              onChange={(e) => onChange(field.key, e.target.value)}
              className={base}
            />
          )
        })}
      </div>
      <div className="flex gap-2">
        <button
          onClick={onSearch}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          Search
        </button>
        {onClear && (
          <button
            onClick={onClear}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  )
}
