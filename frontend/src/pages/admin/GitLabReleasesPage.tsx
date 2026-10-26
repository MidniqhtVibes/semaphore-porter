import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Badge, Button, Card, Field, Loading, Modal, Notice, PageHeader, formatDate } from '../../components/ui'
import type { Snapshot, Snapshots } from '../../gitlab'

type ProjectTemplate={id:string;name:string;catalog_snapshot_id?:string}
type Resources={repositories:Array<{name:string;git_url:string;git_branch:string}>}

export function GitLabReleasesPage(){
  const qc=useQueryClient(),query=useQuery({queryKey:['gitlab-snapshots'],queryFn:()=>api<Snapshots>('/admin/gitlab/snapshots')})
  const [selected,setSelected]=useState<Snapshot|null>(null),[message,setMessage]=useState('')
  const prepare=useMutation({mutationFn:()=>api<Snapshot>('/admin/gitlab/snapshots',{method:'POST'}),onSuccess:()=>{void qc.invalidateQueries({queryKey:['gitlab-snapshots']});setMessage('Katalogstand geprüft und vorbereitet. Zum Aktivieren eine passende Projektvorlage auswählen.')}})
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="Versionen & Übernahme" description="Freigegebenen GitLab-Stand zusammen mit einer passenden Projektvorlage aktivieren." actions={<Button loading={prepare.isPending} onClick={()=>prepare.mutate()}>Aktuellen Basisstand prüfen und vorbereiten</Button>}/>
    {(query.error||prepare.error)&&<Notice type="error">{query.error?.message||prepare.error?.message}</Notice>}{message&&<Notice type="success">{message}</Notice>}
    <Card><h2>Aktiver Katalog</h2><p>Revision: <code>{query.data?.current_catalog.source_revision}</code></p><div className="badge-row">{Object.entries(query.data?.current_catalog.applications||{}).map(([id,app])=><Badge key={id}>{app.display_name}</Badge>)}</div><p>Die Übernahme prüft alle Paketverträge und eine erfolgreiche Pipeline der exakten Revision auf dem geschützten Basisbranch. Bestehende Tenants und reale Semaphore-Projekte werden dadurch nicht geändert.</p><Link to="/admin/gitlab">GitLab-Verbindung</Link></Card>
    {query.data?.snapshots.map(snapshot=><Card key={snapshot.id}><div className="card-heading"><div><h2>{snapshot.project_name}</h2><p><code>{snapshot.source_sha}</code> · {formatDate(snapshot.created_at)}</p></div><Badge tone={snapshot.active?'success':'neutral'}>{snapshot.active?'Aktiv':'Vorbereitet / historisch'}</Badge></div>
      <div className="badge-row"><Badge tone="success">Neu: {snapshot.diff.added.join(', ')||'keine'}</Badge><Badge tone="warning">Geändert: {snapshot.diff.changed.join(', ')||'keine'}</Badge><Badge tone="danger">Entfernt: {snapshot.diff.removed.join(', ')||'keine'}</Badge></div>
      <p>{snapshot.validation.checks.length} Vertragskombinationen · Pipeline #{snapshot.validation.pipeline?.pipeline_id||snapshot.validation.pipeline?.id||'–'}</p>
      <details><summary>Verträge und Prüfungen anzeigen</summary><pre className="json-preview">{JSON.stringify({catalog:snapshot.catalog,validation:snapshot.validation},null,2)}</pre></details>
      <Button variant="secondary" disabled={snapshot.active} onClick={()=>setSelected(snapshot)}>Übernahme / Rücknahme vorbereiten</Button>
    </Card>)}
    {selected&&<ActivationModal snapshot={selected} activeId={query.data?.active_id||null} onClose={()=>setSelected(null)} onSaved={message=>{setSelected(null);setMessage(message);for(const key of ['gitlab-snapshots','project-templates','vault-catalog'])void qc.invalidateQueries({queryKey:[key]})}}/>}
  </>
}

function ActivationModal({snapshot,activeId,onClose,onSaved}:{snapshot:Snapshot;activeId:string|null;onClose:()=>void;onSaved:(message:string)=>void}){
  const templates=useQuery({queryKey:['project-templates'],queryFn:()=>api<ProjectTemplate[]>('/admin/project-templates')})
  const [source,setSource]=useState(''),[repository,setRepository]=useState(''),[name,setName]=useState(`GitLab ${snapshot.source_sha.slice(0,12)}`),[reviewed,setReviewed]=useState(false),[historical,setHistorical]=useState(false)
  const resources=useQuery({queryKey:['template-resources',source],queryFn:()=>api<Resources>(`/admin/project-templates/${source}/resources`),enabled:!!source})
  const activate=useMutation({mutationFn:()=>api<{message:string}>(`/admin/gitlab/snapshots/${snapshot.id}/activate`,{method:'POST',body:JSON.stringify({expected_active_id:activeId,confirm_reviewed:reviewed,project_template_id:source,repository_name:repository,template_name:name,historical})}),onSuccess:data=>onSaved(data.message)})
  return <Modal title="Katalog und Projektvorlage übernehmen" onClose={onClose}><form onSubmit={e=>{e.preventDefault();activate.mutate()}}>{(activate.error||templates.error||resources.error)&&<Notice type="error">{activate.error?.message||templates.error?.message||resources.error?.message}</Notice>}
    <p>Revision <code>{snapshot.source_sha}</code>. Es entsteht eine neue lokale Projektvorlage mit dieser unveränderlichen Git-Revision und den geprüften Survey-Auswahllisten.</p>
    <Field label="Bestehende Projektvorlage als Grundlage"><select required value={source} onChange={e=>{setSource(e.target.value);setRepository('')}}><option value="">Bitte wählen …</option>{templates.data?.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
    <Field label="Repository des Stack-Projekts" help="Die Clone-URL muss exakt zum verbundenen GitLab-Projekt passen."><select required disabled={resources.isLoading||!source} value={repository} onChange={e=>setRepository(e.target.value)}><option value="">Bitte wählen …</option>{resources.data?.repositories.map(r=><option key={r.name} value={r.name}>{r.name} · {r.git_url}</option>)}</select></Field>
    <Field label="Name der neuen Projektvorlage"><input required minLength={2} maxLength={255} value={name} onChange={e=>setName(e.target.value)}/></Field>
    <label className="toggle-row"><input type="checkbox" checked={historical} onChange={e=>setHistorical(e.target.checked)}/><span>Rücknahme auf einen früher bereits aktivierten Stand</span></label>
    <label className="toggle-row"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/><span>Ich habe den Review in GitLab und die Auswirkungen dieser Revision geprüft und bestätige die Übernahme.</span></label>
    <p>Registry-Zugänge und erforderliche Vorgaben für neue Anwendungen anschließend unter Vault beziehungsweise in den Projektvariablen ergänzen.</p>
    <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Abbrechen</Button><Button type="submit" loading={activate.isPending} disabled={!reviewed||!repository||!source}>Katalog aktivieren und Vorlage erstellen</Button></div>
  </form></Modal>
}
