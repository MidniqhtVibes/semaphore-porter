import { KeyRound } from 'lucide-react'
import { useTheme } from '../designs/ThemeProvider'

export function BrandMark({size=21}:{size?:number}){
  const {active}=useTheme()
  return active.branding==='sit'
    ?<div className="brand-mark brand-mark-sit"><img src="/branding/sit-logo.png" alt="Südwestfalen-IT" width={60} height={39}/></div>
    :<div className="brand-mark"><KeyRound size={size}/></div>
}
