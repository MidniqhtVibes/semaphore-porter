import { useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Activity, AppWindow, Boxes, ChevronDown, CircleUserRound, ClipboardList, FileClock,
  Gauge, KeyRound, LayoutDashboard, ListChecks, Menu, PackageOpen, PanelLeftClose,
  ScrollText, ServerCog, ShieldCheck, Users, Workflow, X,
} from 'lucide-react'
import { useAuth } from '../auth'
import { Button } from './ui'

const adminItems = [
  ['/admin', 'Dashboard', LayoutDashboard],
  ['/admin/tenants', 'Tenants', Boxes],
  ['/admin/tenant-erstellen', 'Tenant erstellen', Workflow],
  ['/admin/anwendungen', 'Anwendungen', AppWindow],
  ['/admin/vorlagen', 'Projektvorlagen', PackageOpen],
  ['/admin/presets', 'Presets', ListChecks],
  ['/admin/benutzer', 'Benutzer & Gruppen', Users],
  ['/admin/berechtigungen', 'Berechtigungen', ShieldCheck],
  ['/admin/tasks', 'Task-Überwachung', Activity],
  ['/admin/audit', 'Audit-Log', ScrollText],
  ['/admin/semaphore', 'Semaphore', ServerCog],
] as const

const portalItems = [
  ['/portal', 'Dashboard', Gauge],
  ['/portal/projekte', 'Meine Projekte', Boxes],
  ['/portal/laufende-tasks', 'Laufende Tasks', Activity],
  ['/portal/historie', 'Task-Historie', FileClock],
  ['/portal/konto', 'Mein Konto', CircleUserRound],
] as const

export function Layout({ mode, children }: { mode: 'admin' | 'portal'; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()
  const items = mode === 'admin' ? adminItems : portalItems
  return <div className="shell">
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><KeyRound size={21}/></div><div><strong>Semaphore</strong><span>Tenant Portal</span></div><button className="mobile-close" onClick={() => setOpen(false)}><X/></button></div>
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
    </div>
  </div>
}

