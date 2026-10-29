import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Field, Notice } from './ui'
import type { SshBinding, SshProfile } from '../credentials'

type Resources=Record<'inventories'|'repositories',Array<Record<string,unknown>>>
export function SshProfilesWizard({templateId,overrides,bindings,onChange}:{templateId:string;overrides?:Resources;bindings:SshBinding[];onChange:(value:SshBinding[])=>void}){
  const profiles=useQuery({queryKey:['ssh-profiles'],queryFn:()=>api<SshProfile[]>('/admin/credentials/profiles')})
  const resources=useQuery({queryKey:['template-resources',templateId],queryFn:()=>api<Resources>(`/admin/project-templates/${templateId}/resources`)})
  const source=overrides||resources.data
  return <section aria-label="SSH-Zugangsprofile"><h3>Zentrale SSH-Zugangsprofile</h3><p>Vorhandene Schlüssel wiederverwenden: für jedes Inventory und SSH-Repository ein passendes Profil wählen. Neue Projekte erhalten eigene Key-Store-Einträge mit demselben privaten Schlüssel.</p>
    {(profiles.error||resources.error)&&<Notice type="error">{profiles.error?.message||resources.error?.message}</Notice>}
    {!profiles.isLoading&&!profiles.data?.length&&<Notice type="info">Noch keine Profile vorhanden. <Link to="/admin/zugangsprofile">Zugangsprofile konfigurieren</Link>. Ohne Auswahl werden SSH-Zugänge nach der Anlage manuell gesetzt.</Notice>}
    {(['inventories','repositories'] as const).map(kind=>(source?.[kind]||[]).map(resource=>{
      const name=String(resource.name),chosen=bindings.find(binding=>binding.resource_kind===kind&&binding.resource_name===name)?.profile_id||''
      return <Field key={`${kind}:${name}`} label={`${kind==='inventories'?'Inventory':'Repository'}: ${name}`}><select value={chosen} onChange={e=>onChange([...bindings.filter(binding=>binding.resource_kind!==kind||binding.resource_name!==name),...(e.target.value?[{resource_kind:kind,resource_name:name,profile_id:e.target.value}]:[])])}>
        <option value="">Kein Profil – Zugang manuell konfigurieren</option>
        {profiles.data?.filter(profile=>profile.purpose===(kind==='inventories'?'host':'git')&&(profile.is_active||profile.id===chosen)).map(profile=><option key={profile.id} value={profile.id}>{profile.name} · Version {profile.vault_version}{profile.is_active?'':' · gesperrt'}</option>)}
      </select></Field>
    }))}
  </section>
}
