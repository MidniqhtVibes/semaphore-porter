import {Activity, AppWindow, Boxes, CircleUserRound, FileClock, Gauge, LayoutDashboard, ListChecks, PackageOpen, ScrollText, ServerCog, ShieldCheck, Users, Workflow, Palette} from 'lucide-react'

export type NavigationMode = 'admin' | 'portal'

export const ADMIN_NAV_ITEMS = [
  ['/admin', 'Dashboard', LayoutDashboard],
  ['/admin/projekte', 'Semaphore-Projekte', ServerCog],
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
  ['/admin/vault', 'Vault', ShieldCheck],
  ['/admin/designs', 'Designs', Palette],
] as const

export const PORTAL_NAV_ITEMS = [
  ['/portal', 'Dashboard', Gauge],
  ['/portal/projekte', 'Meine Projekte', Boxes],
  ['/portal/laufende-tasks', 'Laufende Tasks', Activity],
  ['/portal/historie', 'Task-Historie', FileClock],
  ['/portal/konto', 'Mein Konto', CircleUserRound],
  ['/portal/designs', 'Designs', Palette],
] as const

