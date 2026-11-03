import { ChevronRight, ClipboardList } from 'lucide-react'
import { Link } from 'react-router-dom'
import { navigationBreadcrumbs, type NavigationMode } from './navigation'

export function Breadcrumbs({mode,pathname}:{mode:NavigationMode;pathname:string}){
  const crumbs=navigationBreadcrumbs(mode,pathname)
  return <nav className="breadcrumbs" aria-label="Seitenpfad"><ClipboardList size={16} aria-hidden="true"/><ol>{crumbs.map((crumb,index)=><li key={`${index}:${crumb.path}`}>
    {index>0&&<ChevronRight size={12} aria-hidden="true"/>}
    {index===crumbs.length-1?<span aria-current="page" title={crumb.label}>{crumb.label}</span>:<Link to={crumb.path}>{crumb.label}</Link>}
  </li>)}</ol></nav>
}
