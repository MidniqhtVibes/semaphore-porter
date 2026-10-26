import { useTheme } from '../designs/ThemeProvider'
import { DEFAULT_COPY } from '../designs/themes'
import { useId, useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {ChevronDown, ChevronRight, ClipboardList, Menu, PanelLeftClose, ShieldCheck, X} from 'lucide-react'
import {navigationContext} from './navigation'
import {GroupedNavigation} from './GroupedNavigation'
import { useAuth } from '../auth'
import { Button } from './ui'
import { BrandMark } from './BrandMark'
import { SiteFooter } from './SiteFooter'
import { DoomEasterEgg } from '../hooks/useDoomEasterEgg'

export function Layout({ mode, children }: { mode: 'admin' | 'portal'; children: ReactNode }) {
  const {active}=useTheme()
  const copy={...DEFAULT_COPY,...active.copy}
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()
  const context = navigationContext(mode, location.pathname)
  return <div className="shell">
    {__PORTAL_ARCADE__ && <DoomEasterEgg/>}
    <aside id={menuId} className={`sidebar ${open ? 'sidebar-open' : ''}`} onKeyDown={event=>{if(event.key==='Escape')setOpen(false)}}>
      <div className="brand"><BrandMark/><div><strong>{copy.title}</strong><span>{copy.subtitle}</span></div><button className="mobile-close" aria-label="Hauptmenü schließen" onClick={() => setOpen(false)}><X/></button></div>
      <div className="mode-label">{mode === 'admin' ? 'ADMINPORTAL' : 'BENUTZERPORTAL'}</div>
      <GroupedNavigation mode={mode} pathname={location.pathname} renderItem={([to, label, Icon]) => <NavLink key={to} to={to} end={to === `/${mode}`} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}><Icon size={18}/><span>{label}</span></NavLink>}/>
      <div className="sidebar-bottom">
        {mode === 'admin' && <NavLink to="/portal" className="nav-item"><PanelLeftClose size={18}/>Benutzeransicht</NavLink>}
        {mode === 'portal' && isAdmin && <NavLink to="/admin" className="nav-item"><ShieldCheck size={18}/>Administration</NavLink>}
      </div>
    </aside>
    {open && <button className="sidebar-shade" aria-label="Menühintergrund schließen" onClick={() => setOpen(false)} />}
    <div className="main-wrap">
      <header className="topbar"><button className="menu-button" aria-label="Hauptmenü öffnen" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen(true)}><Menu/></button><nav className="breadcrumbs" aria-label="Seitenpfad"><ClipboardList size={16} aria-hidden="true"/><span>{mode==='admin'?'Administration':'Portal'}</span>{context.groups.map(group=><span className="breadcrumb-group" key={group.id}><ChevronRight size={12} aria-hidden="true"/>{group.label}</span>)}<ChevronRight size={12} aria-hidden="true"/><span aria-current="page">{context.label}</span></nav><div className="profile"><div className="avatar">{user?.display_name.slice(0, 2).toUpperCase()}</div><div><strong>{user?.display_name}</strong><span>{user?.email}</span></div><ChevronDown size={15}/><Button variant="ghost" onClick={() => void logout()}>Abmelden</Button></div></header>
      <main className="content">{children}</main>
      <SiteFooter/>
    </div>
  </div>
}

