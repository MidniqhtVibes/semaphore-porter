import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { navigationGroupContext, navigationGroupPath, type NavigationMode } from '../components/navigation'
import { Empty, PageHeader } from '../components/ui'

export function NavigationPage({mode}:{mode:NavigationMode}){
  const location=useLocation()
  const groups=navigationGroupContext(mode,location.pathname.slice(`/${mode}/bereiche/`.length).split('/'))
  const group=groups?.[groups.length-1]
  if(!group||!groups)return <><PageHeader title="Kategorie nicht gefunden"/><Empty title="Diese Kategorie ist nicht verfügbar" text="Die gewünschte Seite lässt sich über das Hauptmenü öffnen."/><Link className="button button-secondary" to={`/${mode}`}>Zum Dashboard</Link></>
  return <><PageHeader title={group.label} description="Seite auswählen, um diesen Bereich zu öffnen."/><nav className="navigation-overview" aria-label={`Seiten in ${group.label}`}>
    {group.children?.map(child=>{const Icon=child.icon;return <Link className="card navigation-category" key={child.id} to={navigationGroupPath(mode,[...groups,child])}><Icon size={23}/><span><strong>{child.label}</strong><span>Kategorie öffnen · {child.items.length} Seiten</span></span><ChevronRight size={18}/></Link>})}
    {group.items.map(([path,label,Icon])=><Link className="card navigation-category" key={path} to={path}><Icon size={23}/><span><strong>{label}</strong><span>Seite öffnen</span></span><ChevronRight size={18}/></Link>)}
  </nav></>
}
