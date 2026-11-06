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
    ['/admin/tasks', 'Deployment-Monitoring', Activity],
    ['/admin/genehmigungen', 'Task-Genehmigungen', ShieldCheck],
    ['/admin/container', 'Container-Verwaltung', Boxes],
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
    ['/admin/personen', 'Personen & Teams', Users],
    ['/admin/benutzer', 'Benutzer & Gruppen', Users],
    ['/admin/berechtigungen', 'Berechtigungen', ShieldCheck],
    ['/admin/audit', 'Audit-Log', ScrollText],
  ] },
  { id: 'settings', label: 'Einstellungen', icon: Settings2, items: [
    ['/admin/designs', 'Designs', Palette],
    ['/admin/zugangsprofile', 'Zugangsprofile', ShieldCheck],
    ['/admin/registries', 'Registry-Zugänge', PackageOpen],
  ], children: [
    { id: 'connections', label: 'Verbindungen', icon: ServerCog, items: [
      ['/admin/semaphore', 'Semaphore-Verbindung', ServerCog],
      ['/admin/vault', 'Vault', ShieldCheck],
      ['/admin/gitlab', 'GitLab', GitBranch],
      ['/admin/docker-agenten', 'Docker-Agenten', Boxes],
    ] },
  ] },
]

export const PORTAL_NAV_GROUPS: readonly NavigationGroup[] = [
  { id: 'workspace', label: 'Arbeitsbereich', icon: Gauge, items: [
    ['/portal', 'Dashboard', Gauge],
    ['/portal/projekte', 'Meine Projekte', Boxes],
    ['/portal/laufende-tasks', 'Laufende Tasks', Activity],
    ['/portal/genehmigungen', 'Task-Genehmigungen', ShieldCheck],
    ['/portal/historie', 'Task-Historie', FileClock],
  ] },
  { id: 'personal', label: 'Persönlich', icon: CircleUserRound, items: [
    ['/portal/konto', 'Mein Profil', CircleUserRound],
    ['/portal/personen', 'Personen & Teams', Users],
    ['/portal/designs', 'Designs', Palette],
  ] },
]

export function navigationGroups(mode: NavigationMode) {
  return mode === 'admin' ? ADMIN_NAV_GROUPS : PORTAL_NAV_GROUPS
}

export function navigationGroupPath(mode: NavigationMode, groups: readonly NavigationGroup[]) {
  return `/${mode}/bereiche/${groups.map(group=>group.id).join('/')}`
}

export function navigationGroupContext(mode: NavigationMode, ids: readonly string[]) {
  const result: NavigationGroup[]=[]
  let branches=navigationGroups(mode)
  for(const id of ids){
    const group=branches.find(branch=>branch.id===id)
    if(!group)return undefined
    result.push(group)
    branches=group.children||[]
  }
  return result.length?result:undefined
}

export function navigationContext(mode: NavigationMode, pathname: string) {
  const categoryPrefix=`/${mode}/bereiche/`
  if(pathname.startsWith(categoryPrefix)){
    const path=navigationGroupContext(mode,pathname.slice(categoryPrefix.length).split('/'))
    if(path)return {group:path[0],groups:path,label:path[path.length-1].label,path:pathname,category:true}
  }
  const navigationPath=pathname.replace(/^\/(admin|portal)\/teams\//,'/$1/personen/')
    .replace(/^\/admin\/tenant-erstellen$/,'/admin/tenants').replace(/^\/portal\/runs\/.+$/,'/portal/historie')
  const groups = navigationGroups(mode)
  const find = (branches: readonly NavigationGroup[], parents: NavigationGroup[] = []): { group: NavigationGroup; groups: NavigationGroup[]; label: string; path: string; category: boolean } | undefined => {
    for (const group of branches) {
      const path = [...parents, group]
      const nested = find(group.children || [], path)
      if (nested) return nested
      const item = group.items.find(([to]) => navigationPath === to || to !== `/${mode}` && navigationPath.startsWith(`${to}/`))
      if (item) return { group: path[0], groups: path, label: pathname==='/admin/tenant-erstellen'?'Tenant erstellen':item[1], path:item[0], category:false }
    }
  }
  return find(groups) || { group: groups[0], groups: [groups[0]], label: pathname.startsWith(categoryPrefix)?'Kategorie nicht gefunden':'Dashboard', path:pathname, category:false }
}

export function navigationBreadcrumbs(mode: NavigationMode, pathname: string) {
  const context=navigationContext(mode,pathname)
  const crumbs=[{label:mode==='admin'?'Administration':'Portal',path:`/${mode}`},
    ...context.groups.map((group,index)=>({label:group.label,path:navigationGroupPath(mode,context.groups.slice(0,index+1))}))]
  if(context.category)return crumbs
  const label=pathname==='/admin/tenant-erstellen'?'Tenants':context.label
  crumbs.push({label,path:context.path})
  if(pathname!==context.path){
    const detail=pathname==='/admin/tenant-erstellen'?'Tenant erstellen'
      :/\/teams\//.test(pathname)?'Teamprofil':/\/personen\//.test(pathname)?'Personenprofil'
      :pathname.startsWith('/admin/tenants/')?'Tenantdetails'
      :pathname.startsWith('/admin/programmpakete/')?'Programmpaket'
      :/^\/portal\/projekte\/[^/]+\/tasks\//.test(pathname)?'Task starten'
      :pathname.startsWith('/portal/runs/')?'Taskdetails':pathname.includes('/projekte/')?'Projektdetails':'Details'
    if(detail==='Task starten'){
      crumbs.push({label:'Projekt',path:pathname.split('/').slice(0,4).join('/')})
    }
    crumbs.push({label:detail,path:pathname})
  }
  return crumbs
}
