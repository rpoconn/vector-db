import { useEffect, useRef } from 'react'

/**
 * Runs `effect` once per mounted component, even under StrictMode's double effects.
 *
 * For single-use side effects such as redeeming an e-mailed token or an OAuth `code`,
 * where a second request would fail.
 */
export function useRunOnce(effect: () => void): void {
  const ran = useRef(false)
  const effectRef = useRef(effect)

  useEffect(() => {
    if (!ran.current) {
      ran.current = true
      effectRef.current()
    }
  }, [])
}
