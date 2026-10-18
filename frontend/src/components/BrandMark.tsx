import { ThemeLogo } from './ThemeLogo'
import { useTheme } from '../designs/ThemeProvider'

export function BrandMark({size=21}:{size?:number}){
  const {active}=useTheme()
  return <ThemeLogo theme={active} size={size} className="brand-mark"/>
}
