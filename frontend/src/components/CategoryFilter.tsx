import { useCategories } from '../api/queries.ts'

interface CategoryFilterProps {
  value: string | undefined
  onChange: (category: string | undefined) => void
}

/** A select rather than chips: the catalog spans hundreds of small categories. */
export function CategoryFilter({ value, onChange }: CategoryFilterProps) {
  const { data: categories } = useCategories()
  const total = categories?.reduce((sum, category) => sum + category.product_count, 0)

  return (
    <label className="flex items-center gap-2 text-sm text-slate-600">
      Category
      <select
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value || undefined)}
        className="max-w-56 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900"
      >
        <option value="">All categories{total !== undefined ? ` (${total})` : ''}</option>
        {/* Keep a category from the URL selectable before the list loads. */}
        {value && !categories?.some((category) => category.name === value) ? (
          <option value={value}>{value}</option>
        ) : null}
        {categories?.map((category) => (
          <option key={category.name} value={category.name}>
            {category.name} ({category.product_count})
          </option>
        ))}
      </select>
    </label>
  )
}
