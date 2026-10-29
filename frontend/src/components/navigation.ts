import {Activity, AppWindow, Boxes, CircleUserRound, FileClock, Gauge, LayoutDashboard, ListChecks, PackageOpen, ScrollText, ServerCog, Settings2, ShieldCheck, Users, Palette, GitBranch, GitMerge, FlaskConical, Download, type LucideIcon} from 'lucide-react'

export type NavigationMode = 'admin' | 'portal'

export type NavigationItem = readonly [path: string, label: string, icon: LucideIcon]
export type NavigationGroup = {
  id: string
  label: string
  icon: LucideIcon
  items: readonly NavigationItem[]
  children?: readonly NavigationGroup[]
}

export const ADMIN_NAV_GROUPS: readonly NavigationGroup[] = [
  { id: 'workspace', label: 'Arbeitsbereich', icon: LayoutDashboard, items: [
    ['/admin', 'Dashboard', LayoutDashboard],
    ['/admin/tenants', 'Tenants', Boxes],
    ['/admin/projekte', 'Semaphore-Projekte', ServerCog],
    ['/admin/tasks', 'Überwachung', Activity],
  ] },
  { id: 'catalog', label: 'Katalog', icon: PackageOpen, items: [
    ['/admin/anwendungen', 'Anwendungen', AppWindow],
    ['/admin/vorlagen', 'Projektvorlagen', PackageOpen],
    ['/admin/presets', 'Presets', ListChecks],
  ] },
  { id: 'development', label: 'Entwicklung', icon: GitBranch, items: [
    ['/admin/programmpakete', 'Programmpakete', PackageOpen],
    ['/admin/freigaben', 'Änderungen & Freigaben', GitMerge],
    ['/admin/pruefungen', 'Prüfungen', FlaskConical],
    ['/admin/uebernahme', 'Versionen & Übernahme', Download],
  ] },
  { id: 'access', label: 'Zugriff', icon: ShieldCheck, items: [
    ['/admin/benutzer', 'Benutzer & Gruppen', Users],
    ['/admin/berechtigungen', 'Berechtigungen', ShieldCheck],
    ['/admin/audit', 'Audit-Log', ScrollText],
  ] },
  { id: 'settings', label: 'Einstellungen', icon: Settings2, items: [
    ['/admin/designs', 'Designs', Palette],
    ['/admin/zugangsprofile', 'Zugangsprofile', ShieldCheck],
  ], children: [
    { id: 'connections', label: 'Verbindungen', icon: ServerCog, items: [
      ['/admin/semaphore', 'Semaphore-Verbindung', ServerCog],
      ['/admin/vault', 'Vault', ShieldCheck],
      ['/admin/gitlab', 'GitLab', GitBranch],
    ] },
  ] },
]

export const PORTAL_NAV_GROUPS: readonly NavigationGroup[] = [
  { id: 'workspace', label: 'Arbeitsbereich', icon: Gauge, items: [
    ['/portal', 'Dashboard', Gauge],
    ['/portal/projekte', 'Meine Projekte', Boxes],
    ['/portal/laufende-tasks', 'Laufende Tasks', Activity],
    ['/portal/historie', 'Task-Historie', FileClock],
  ] },
  { id: 'personal', label: 'Persönlich', icon: CircleUserRound, items: [
    ['/portal/konto', 'Mein Konto', CircleUserRound],
    ['/portal/designs', 'Designs', Palette],
  ] },
]

export function navigationGroups(mode: NavigationMode) {
  return mode === 'admin' ? ADMIN_NAV_GROUPS : PORTAL_NAV_GROUPS
}

export function navigationContext(mode: NavigationMode, pathname: string) {
  const groups = navigationGroups(mode)
  const find = (branches: readonly NavigationGroup[], parents: NavigationGroup[] = []): { group: NavigationGroup; groups: NavigationGroup[]; label: string } | undefined => {
    for (const group of branches) {
      const path = [...parents, group]
      const nested = find(group.children || [], path)
      if (nested) return nested
      const item = group.items.find(([to]) => pathname === to || to !== `/${mode}` && pathname.startsWith(`${to}/`))
      if (item) return { group: path[0], groups: path, label: item[1] }
    }
  }
  return find(groups) || { group: groups[0], groups: [groups[0]], label: pathname === '/admin/tenant-erstellen' ? 'Tenant erstellen' : 'Dashboard' }
}

