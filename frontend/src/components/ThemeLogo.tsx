import { KeyRound } from 'lucide-react'
import { LOGO_ASSETS } from '../designs/logoAssets'
import type { Theme } from '../designs/themes'

export function ThemeLogo({theme,size=21,className='',preview=false}:{theme:Theme;size?:number;className?:string;preview?:boolean}) {
  const asset=LOGO_ASSETS.find(item=>item.id===theme.logoAsset)
  const src=theme.logo||asset?.src
  const alt=preview?'Logo-Vorschau':theme.logo?(theme.copy?.title||'Eigenes Logo'):(asset?.alt||'')
  return <span className={`theme-logo ${src?'theme-logo-image':''} ${theme.logoTone==='dark'?'theme-logo-dark':''} ${className}`} style={src?{width:theme.logoWidth??64}:undefined}>
    {src?<img src={src} alt={alt}/>:<KeyRound size={size}/>}
  </span>
}
