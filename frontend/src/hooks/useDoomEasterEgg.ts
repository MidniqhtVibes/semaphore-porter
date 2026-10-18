import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

export function DoomEasterEgg() {
  useDoomEasterEgg()
  return null
}

export function useDoomEasterEgg() {
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    let sequence = ''
    let lastKeyAt = 0
    const reset = () => { sequence = ''; lastKeyAt = 0 }
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target
      if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.altKey || event.metaKey ||
        target instanceof Element && target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]')) {
        reset()
        return
      }
      if (event.repeat) return
      if (event.key.length !== 1) { reset(); return }
      const now = performance.now()
      if (now - lastKeyAt > 1800) sequence = ''
      lastKeyAt = now
      sequence = (sequence + event.key.toLowerCase()).slice(-5)
      if (sequence === 'iddqd') {
        reset()
        navigate('/portal/iddqd', { state: { returnTo: location.pathname + location.search } })
      }
    }
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('blur', reset)
    document.addEventListener('focusin', reset)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('blur', reset)
      document.removeEventListener('focusin', reset)
    }
  }, [navigate, location.pathname, location.search])
}
