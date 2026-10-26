import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, RefreshCw } from 'lucide-react'
import { api } from '../../api'
import { Badge, Button, Card, Empty, Field, Loading, Modal, Notice, PageHeader, StatusBadge, formatDate } from '../../components/ui'
import type { GitLabConfig, PackageDraft, Repository } from '../../gitlab'

export function ProgramPackagesPage(){
  const navigate=useNavigate(),[create,setCreate]=useState<{source_id?:string}|null>(null),[error,setError]=useState('')
  const config=useQuery({queryKey:['gitlab-config'],queryFn:()=>api<GitLabConfig>('/admin/gitlab')})
  const repo=useQuery({queryKey:['gitlab-repository',config.data?.connection_id],queryFn:()=>api<Repository>('/admin/gitlab/repository'),enabled:!!config.data?.configured,retry:false,staleTime:60000})
  const drafts=useQuery({queryKey:['package-drafts'],queryFn:()=>api<PackageDraft[]>('/admin/program-packages')})
  const edit=useMutation({mutationFn:(id:string)=>api<PackageDraft>('/admin/program-packages',{method:'POST',body:JSON.stringify({package_id:id,source_id:id,name:repo.data?.programs.find(p=>p.id===id)?.name||id})}),onSuccess:data=>navigate(`/admin/programmpakete/${data.id}`),onError:(e:Error)=>setError(e.message)})
  if(config.isLoading||drafts.isLoading)return <Loading/>
  return <><PageHeader title="Programmpakete" description="Deployment-Pakete aus vorhandenen Images erstellen, bearbeiten und über GitLab freigeben." actions={<Button disabled={!repo.data||edit.isPending} onClick={()=>setCreate({})}><Plus size={16}/>Programmpaket erstellen</Button>}/>
    {(error||config.error||drafts.error||repo.error)&&<Notice type="error">{error||config.error?.message||drafts.error?.message||repo.error?.message}</Notice>}
    {!config.data?.configured?<Empty title="GitLab noch nicht verbunden" text="Instanz, Projekt-ID, Basisbranch und Token unter Einstellungen → Verbindungen → GitLab hinterlegen."/>:<Card><div className="card-heading"><div><h2>Repository-Pakete</h2><p>{repo.data?.project_name||config.data.project_name} · {repo.data?.sha.slice(0,12)}</p></div><Button variant="secondary" loading={repo.isFetching} onClick={()=>void repo.refetch()}><RefreshCw size={15}/>Aktualisieren</Button></div>
      {repo.isLoading?<Loading label="Paketverträge werden aus GitLab gelesen …"/>:<div className="cards-grid">{repo.data?.programs.map(p=><Card key={p.id}><h3>{p.name}</h3><p><code>{p.id}</code> · {p.release}</p><div className="badge-row">{p.database_types.map(kind=><Badge key={kind}>{kind}</Badge>)}</div><div className="button-row"><Button variant="secondary" loading={edit.isPending} onClick={()=>edit.mutate(p.id)}>Bearbeiten</Button><Button variant="ghost" onClick={()=>setCreate({source_id:p.id})}>Als Vorlage</Button></div></Card>)}</div>}
    </Card>}
    <p><Link to="/admin/gitlab">GitLab-Verbindung</Link> · <Link to="/admin/uebernahme">Versionen & Übernahme</Link></p>
    <Card><h2>Gespeicherte Entwürfe</h2>{drafts.data?.length?<div className="table-wrap"><table><thead><tr><th>Paket</th><th>Status</th><th>Basis</th><th>Geändert</th></tr></thead><tbody>{drafts.data.map(d=><tr key={d.id}><td><Link to={`/admin/programmpakete/${d.id}`}>{d.name}</Link><small className="block muted">{d.package_id}{d.connection_id!==config.data?.connection_id?' · andere Verbindung':''}</small></td><td><StatusBadge status={d.status}/></td><td><code>{d.base_sha.slice(0,12)}</code></td><td>{formatDate(d.updated_at)}</td></tr>)}</tbody></table></div>:<p>Noch keine Entwürfe.</p>}</Card>
    {create&&repo.data&&<CreatePackageModal source={create.source_id} repository={repo.data} onClose={()=>setCreate(null)}/>}
  </>
}

function CreatePackageModal({source,repository,onClose}:{source?:string;repository:Repository;onClose:()=>void}){
  const navigate=useNavigate(),[form,setForm]=useState({source_id:source||'',package_id:'',name:'',image_repository:'',release:'1.0.0',container_port:8080}),[error,setError]=useState('')
  const create=useMutation({mutationFn:()=>api<PackageDraft>('/admin/program-packages',{method:'POST',body:JSON.stringify({...form,source_id:form.source_id||null,image_repository:form.image_repository||null})}),onSuccess:data=>navigate(`/admin/programmpakete/${data.id}`),onError:(e:Error)=>setError(e.message)})
  return <Modal title="Programmpaket erstellen" onClose={onClose}><form onSubmit={e=>{e.preventDefault();create.mutate()}}>{error&&<Notice type="error">{error}</Notice>}<div className="form-grid columns-2">
    <Field label="Vorlage" help="SQL-Anwendungen von einem passenden Paket kopieren; Dateien und Providerverträge anschließend anpassen."><select value={form.source_id} onChange={e=>setForm(v=>({...v,source_id:e.target.value}))}><option value="">HTTP-Anwendung ohne Datenbank</option>{repository.programs.map(p=><option key={p.id} value={p.id}>{p.name} · {p.database_types.join(', ')}</option>)}</select></Field>
    <Field label="Technische Paket-ID"><input required pattern="[a-z0-9][a-z0-9-]{0,62}" maxLength={63} value={form.package_id} onChange={e=>setForm(v=>({...v,package_id:e.target.value}))}/></Field>
    <Field label="Anzeigename"><input required maxLength={128} value={form.name} onChange={e=>setForm(v=>({...v,name:e.target.value}))}/></Field>
    <Field label="Image-Repository" help="Vorhandenes Image ohne Tag, z. B. registry.firma.de/team/app. Bei einer Kopie optional."><input required={!form.source_id} value={form.image_repository} onChange={e=>setForm(v=>({...v,image_repository:e.target.value}))}/></Field>
    <Field label="Release / Image-Tag"><input required value={form.release} onChange={e=>setForm(v=>({...v,release:e.target.value}))}/></Field>
    {!form.source_id&&<Field label="HTTP-Container-Port"><input type="number" min={1} max={65535} value={form.container_port} onChange={e=>setForm(v=>({...v,container_port:Number(e.target.value)}))}/></Field>}
  </div><p>Es entsteht zuerst ein lokaler Entwurf. Vault-Profil und programmspezifische Registry-Variablen erhalten beim Kopieren die neue Paket-ID. Services und Datenbankkonfiguration müssen fachlich zur Anwendung passen.</p><div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Abbrechen</Button><Button type="submit" loading={create.isPending}>Entwurf erstellen</Button></div></form></Modal>
}
