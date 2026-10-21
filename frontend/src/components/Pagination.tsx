interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)
  const buttonClasses =
    'rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40'

  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-4 pt-6">
      <p className="text-sm text-slate-500">
        {first}–{last} of {total}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className={buttonClasses}
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        <span className="text-sm text-slate-600">
          Page {page} of {pageCount}
        </span>
        <button
          type="button"
          className={buttonClasses}
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </nav>
  )
}
