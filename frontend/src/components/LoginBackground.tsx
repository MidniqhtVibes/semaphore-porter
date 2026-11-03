import { MAX_LOGIN_BACKGROUND_BLUR } from '../designs/themes'

export function LoginBackground({ image, blur = 0, dim, milk = 0, className = '' }: { image?: string; blur?: number; dim?: number; milk?: number; className?: string }) {
  if (!image) return null
  const radius = Number.isFinite(blur) ? Math.min(MAX_LOGIN_BACKGROUND_BLUR, Math.max(0, blur)) : 0
  const percent=(value:number)=>Number.isFinite(value)?Math.min(100,Math.max(0,value))/100:0
  const shade=dim===undefined?'var(--overlay)':`rgba(0, 0, 0, ${percent(dim)})`
  const veil=`rgba(255, 255, 255, ${percent(milk)})`
  return <div className={`login-background ${className}`.trim()} aria-hidden="true" style={{
    backgroundImage: `linear-gradient(${veil}, ${veil}), linear-gradient(${shade}, ${shade}), url("${image}")`,
    filter: `blur(${radius}px)`, inset: -radius * 2,
  }}/>
}
