import type { Tenant } from '../types'
import { apiUrl } from '../api'

export const projectMarks = [
  {id:'doxis', name:'Doxis', match:/\bdoxis(?:\d+)?\b/i, source:'/branding/projects/doxis.svg'},
  {id:'postgresql', name:'PostgreSQL', match:/\b(?:postgres(?:ql)?)(?:-v?\d+)?\b/i, source:'/branding/projects/postgresql.svg'},
  {id:'wordpress', name:'WordPress', match:/\bwordpress\b/i, source:'/branding/projects/wordpress.png'},
]

/** Decorative only: names remain text and no external image service is contacted. */
export function ProjectArtwork({tenant}: {tenant: Pick<Tenant,'id'|'application_id'|'application_ids'|'database_types'|'display_name'|'project_artwork'>}) {
  const config=tenant.project_artwork||{}
  if(config.mode==='none')return null
  if(config.mode==='custom')return config.image_version?<div className="project-artwork" aria-hidden="true"><img
    className="project-artwork-image" src={apiUrl(`/portal/tenants/${tenant.id}/logo?v=${encodeURIComponent(config.image_version)}`)} alt="" draggable={false}/></div>:null
  const identifiers = [...tenant.application_ids||[], tenant.application_id||'', ...tenant.database_types||[]]
    .map(value=>value.replace(/[_/]/g,' ')).join(' ')
  const selected = projectMarks.filter(mark=>config.mode==='selected'?config.marks?.includes(mark.id):mark.match.test(identifiers))
  if (!selected.length) return null
  return <div className={`project-artwork project-artwork-${Math.min(selected.length,3)}`} aria-hidden="true">
    {selected.map(mark=><span key={mark.id} className={`project-artwork-mark project-artwork-${mark.id}`}/>)}
  </div>
}
