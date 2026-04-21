import { useEffect, useState, useCallback } from 'react'

/**
 * Reads the current value of the `?tv` query parameter and returns whether
 * TV mode is currently enabled.
 *
 * Considered enabled only when `?tv=1` is present. Any other value (including
 * absent) yields `false`.
 */
function readTvFromUrl(): boolean {
  if (typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).get('tv') === '1'
}

/**
 * Synchronizes a boolean TV-mode flag with the `?tv=1` query parameter in the URL.
 *
 * Behaviour:
 * - Lazy initialization reads the URL on mount, so a bookmark like
 *   `/embed/dashboard/foo?tv=1` opens directly into TV mode.
 * - `setTvMode(next)` rewrites the URL via `history.replaceState` (NOT `pushState`),
 *   so toggling the checkbox repeatedly does not pollute browser back-history.
 * - A `popstate` listener keeps the local state aligned with browser back/forward
 *   navigation when the user moves between history entries with different `tv` values.
 * - The hook deliberately avoids `react-router`'s `useSearchParams` because the
 *   embed pages do not use react-router for URL state.
 */
export function useTvMode(): { tvMode: boolean; setTvMode: (next: boolean) => void } {
  const [tvMode, setState] = useState<boolean>(() => readTvFromUrl())

  const setTvMode = useCallback((next: boolean) => {
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href)
      if (next) {
        url.searchParams.set('tv', '1')
      } else {
        url.searchParams.delete('tv')
      }
      // replaceState (not pushState): repeated toggles must not stack history entries.
      window.history.replaceState({}, '', url.toString())
    }
    setState(next)
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const handler = () => {
      setState(readTvFromUrl())
    }
    window.addEventListener('popstate', handler)
    return () => {
      window.removeEventListener('popstate', handler)
    }
  }, [])

  return { tvMode, setTvMode }
}

export default useTvMode
