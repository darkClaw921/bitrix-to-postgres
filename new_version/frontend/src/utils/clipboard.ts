/**
 * Copies the given text to the clipboard.
 *
 * Tries the modern asynchronous Clipboard API first (`navigator.clipboard.writeText`),
 * which is the only path that works reliably in modern Chromium/Firefox/Safari.
 *
 * Falls back to the legacy `document.execCommand('copy')` approach via a hidden
 * `<textarea>` for environments where the Clipboard API is unavailable:
 *  - HTTP (non-secure) origins, where `navigator.clipboard` is undefined.
 *  - Older browsers without Clipboard API support.
 *  - Iframes / contexts where Clipboard API permission is denied.
 *
 * Returns a promise that resolves to `true` on success and `false` on failure
 * (so callers can show a "copied!" toast or fall back to a manual prompt).
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // Modern API — only available in secure contexts (HTTPS, localhost).
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Fall through to the legacy path — Clipboard API can throw on
      // permission denial even when the API itself exists.
    }
  }

  // Legacy fallback — works on HTTP and older browsers. Creates an off-screen
  // textarea, selects its contents, and asks the document to copy. The textarea
  // is positioned far off-screen (not `display: none`) because hidden inputs
  // cannot be selected for the copy operation.
  if (typeof document === 'undefined') return false
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    textarea.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}
