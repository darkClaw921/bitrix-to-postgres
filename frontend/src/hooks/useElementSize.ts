import { useLayoutEffect, useRef, useState } from 'react'

/**
 * Generic ResizeObserver-based hook that tracks the width and height of a DOM element.
 *
 * Returns a ref to attach to an element and the current `{ width, height }` of that
 * element's content box. The size is updated synchronously after the browser layout
 * (via `useLayoutEffect`), which avoids a flicker on the first paint compared to
 * `useEffect` — important when the consumer derives a `fontScale` from the size and
 * needs the very first render to be visually stable.
 *
 * The hook is generic over the element type (defaulting to `HTMLDivElement`) so that
 * callers can attach the ref to any specific HTML element without casting.
 *
 * Edge cases:
 * - In environments without `ResizeObserver` (SSR, very old browsers, jsdom in tests
 *   without polyfill) the hook returns `{ width: 0, height: 0 }` and never updates,
 *   instead of throwing.
 * - The observer is disconnected on unmount to prevent leaks.
 */
export function useElementSize<T extends HTMLElement = HTMLDivElement>(): {
  ref: React.RefObject<T>
  width: number
  height: number
} {
  const ref = useRef<T>(null)
  const [size, setSize] = useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  })

  useLayoutEffect(() => {
    if (typeof ResizeObserver === 'undefined') return
    const element = ref.current
    if (!element) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      setSize((prev) =>
        prev.width === width && prev.height === height ? prev : { width, height },
      )
    })

    observer.observe(element)

    return () => {
      observer.disconnect()
    }
  }, [])

  return { ref, width: size.width, height: size.height }
}

export default useElementSize
