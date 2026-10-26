import { MAX_LOGIN_BACKGROUND_BLUR } from '../designs/themes'

export function LoginBackground({ image, blur = 0 }: { image?: string; blur?: number }) {
  if (!image) return null
  const radius = Number.isFinite(blur) ? Math.min(MAX_LOGIN_BACKGROUND_BLUR, Math.max(0, blur)) : 0
  return <div className="login-background" aria-hidden="true" style={{
    backgroundImage: `linear-gradient(var(--overlay), var(--overlay)), url("${image}")`,
    filter: `blur(${radius}px)`, inset: -radius * 2,
  }}/>
}
