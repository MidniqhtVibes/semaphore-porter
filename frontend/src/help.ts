import type { NavigationMode } from './components/navigation'

export type HelpCategory = {id:string;title:string;summary:string}
export type HelpSummary = {id:string;title:string;summary:string;category:string;audience:'all'|'admin';keywords:string[]}
export type HelpCatalog = {content_version:string;categories:HelpCategory[];articles:HelpSummary[]}
export type HelpArticle = HelpSummary & {body:string;headings:Array<{id:string;title:string;level:number;line:number}>;quick_steps:string[];content_version:string;related:HelpSummary[]}
export type HelpContextInfo = {id:string;article_id:string;title:string;summary:string;steps:string[];anchor:string|null;content_version:string}

export const helpBase = (mode:NavigationMode) => `/${mode}/hilfe`
export function helpContextForPath(pathname:string) {
  const admin: Array<[string,string]> = [
    ['/admin/tenant-erstellen','tenants'],['/admin/tenants','tenants'],['/admin/projekte','tenants'],
    ['/admin/anwendungen','applications'],['/admin/vorlagen','policies'],['/admin/presets','policies'],
    ['/admin/zugangsprofile','ssh'],['/admin/registries','registry'],['/admin/semaphore','semaphore'],
    ['/admin/vault','vault'],['/admin/gitlab','gitlab'],['/admin/programmpakete','gitlab'],
    ['/admin/freigaben','gitlab'],['/admin/pruefungen','gitlab'],['/admin/uebernahme','gitlab'],
    ['/admin/genehmigungen','approvals'],['/admin/tasks','monitoring'],['/admin/container','containers'],
    ['/admin/docker-agenten','containers'],['/admin/benutzer','users'],['/admin/berechtigungen','permissions'],
    ['/admin/personen','profiles'],['/admin/teams','profiles'],['/admin/designs','designs'],['/admin/audit','operations'],
  ]
  const match=admin.find(([path])=>pathname===path||pathname.startsWith(path+'/'))
  if(match)return match[1]
  if(pathname.includes('/genehmigungen'))return 'approvals'
  if(/\/projekte\/[^/]+\/tasks\//.test(pathname))return 'task-start'
  if(/\/(runs|laufende-tasks|historie)(\/|$)/.test(pathname))return 'task-feed'
  if(/\/(konto|personen|teams)(\/|$)/.test(pathname))return 'profiles'
  if(pathname.includes('/designs'))return 'designs'
  return 'overview'
}

export function errorHelpContext(message:string, admin:boolean) {
  if(!message.trim())return null
  if(!admin)return /Semaphore|Task|SSH|Policy|API|Genehmigung|Parameter/i.test(message)?'task-start':null
  if(/publickey|SSH|Passphrase|sudo|Inventory/i.test(message))return 'ssh'
  if(/Registry|Image-Pull/i.test(message))return 'registry'
  if(/Vault|AppRole|Secret-ID|Role-ID|KV-v2/i.test(message))return 'vault'
  if(/Semaphore|API-Fehler/i.test(message))return 'semaphore'
  if(/Genehmigung|Freigabe|Kosten|Aufwand/i.test(message))return 'approvals'
  return null
}
