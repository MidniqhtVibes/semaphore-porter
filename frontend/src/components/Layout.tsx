import { useTheme } from '../designs/ThemeProvider'
import { DEFAULT_COPY } from '../designs/themes'
import { useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {ChevronDown, ClipboardList, Menu, PanelLeftClose, ShieldCheck, X} from 'lucide-react'
import {ADMIN_NAV_ITEMS, PORTAL_NAV_ITEMS} from './navigation'
import { useAuth } from '../auth'
import { Button } from './ui'
import { BrandMark } from './BrandMark'
import { SiteFooter } from './SiteFooter'

export function Layout({ mode, children }: { mode: 'admin' | 'portal'; children: ReactNode }) {
  const {active}=useTheme()
  const copy={...DEFAULT_COPY,...active.copy}
  const [open, setOpen] = useState(false)
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()
  const items = mode === 'admin' ? ADMIN_NAV_ITEMS : PORTAL_NAV_ITEMS
  return <div className="shell">
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <div className="brand"><BrandMark/><div><strong>{copy.title}</strong><span>{copy.subtitle}</span></div><button className="mobile-close" onClick={() => setOpen(false)}><X/></button></div>
      <div className="mode-label">{mode === 'admin' ? 'ADMINPORTAL' : 'BENUTZERPORTAL'}</div>
      <nav>{items.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === `/${mode}`} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-bottom">
        {mode === 'admin' && <NavLink to="/portal" className="nav-item"><PanelLeftClose size={18}/>Benutzeransicht</NavLink>}
        {mode === 'portal' && isAdmin && <NavLink to="/admin" className="nav-item"><ShieldCheck size={18}/>Administration</NavLink>}
      </div>
    </aside>
    {open && <div className="sidebar-shade" onClick={() => setOpen(false)} />}
    <div className="main-wrap">
      <header className="topbar"><button className="menu-button" onClick={() => setOpen(true)}><Menu/></button><div className="breadcrumbs"><ClipboardList size={16}/><span>{location.pathname.startsWith('/admin') ? 'Administration' : 'Portal'}</span></div><div className="profile"><div className="avatar">{user?.display_name.slice(0, 2).toUpperCase()}</div><div><strong>{user?.display_name}</strong><span>{user?.email}</span></div><ChevronDown size={15}/><Button variant="ghost" onClick={() => void logout()}>Abmelden</Button></div></header>
      <main className="content">{children}</main>
      <SiteFooter/>
    </div>
  </div>
}

