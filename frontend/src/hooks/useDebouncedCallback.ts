import { useCallback, useEffect, useMemo, useRef } from 'react'

export interface DebouncedCallback<TArgs extends unknown[]> {
  /** Calls `callback` with `args` once `delayMs` passes without another call. */
  schedule: (...args: TArgs) => void
  /** Drops a pending call. */
  cancel: () => void
}

/** Debounces `callback`, always invoking its latest version. Pending calls die on unmount. */
export function useDebouncedCallback<TArgs extends unknown[]>(
  callback: (...args: TArgs) => void,
  delayMs: number,
): DebouncedCallback<TArgs> {
  const callbackRef = useRef(callback)
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  const cancel = useCallback(() => {
    clearTimeout(timerRef.current)
    timerRef.current = undefined
  }, [])

  const schedule = useCallback(
    (...args: TArgs) => {
      cancel()
      timerRef.current = setTimeout(() => {
        timerRef.current = undefined
        callbackRef.current(...args)
      }, delayMs)
    },
    [cancel, delayMs],
  )

  useEffect(() => cancel, [cancel])

  return useMemo(() => ({ schedule, cancel }), [schedule, cancel])
}
