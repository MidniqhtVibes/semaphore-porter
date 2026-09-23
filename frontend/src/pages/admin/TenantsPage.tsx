import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { Boxes, CheckCircle2, Download, ExternalLink, Plus, RefreshCw, Save, Trash2 } from 'lucide-react'
import { api } from '../../api'
import { Badge, Button, Card, Empty, Field, Loading, Modal, Notice, PageHeader, StatusBadge, formatDate } from '../../components/ui'
import type { TaskTemplate, Tenant, User } from '../../types'

export function TenantsPage() {
  const query = useQuery({ queryKey: ['admin-tenants'], queryFn: () => api<Tenant[]>('/admin/tenants') })
  const [search, setSearch] = useState('')
  if (query.isLoading) return <Loading />
  const rows = (query.data || []).filter(item => `${item.display_name} ${item.tenant_slug}`.toLowerCase().includes(search.toLowerCase()))
  return <><PageHeader title="Tenants" description="Portalzuordnungen basieren auf stabilen Semaphore-Projekt-IDs." actions={<Link className="button button-primary" to="/admin/tenant-erstellen"><Plus size={16}/>Tenant erstellen</Link>}/>
    <Card><div className="toolbar"><input className="search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Tenants durchsuchen …"/><span>{rows.length} Einträge</span></div>
      {rows.length ? <div className="table-wrap"><table><thead><tr><th>Tenant</th><th>Anwendung</th><th>Semaphore-Projekt</th><th>Status</th><th>Geändert</th><th/></tr></thead><tbody>{rows.map(item => <tr key={item.id}><td><div className="name-cell"><div className="square-icon"><Boxes size={17}/></div><div><strong>{item.display_name}</strong><span>{item.tenant_slug}</span></div></div></td><td>{item.application_id || '–'}</td><td>{item.semaphore_project ? <><strong>{item.semaphore_project.name}</strong><span className="subtle">#{item.semaphore_project.id}</span></> : <Badge tone="warning">Nicht zugeordnet</Badge>}</td><td><StatusBadge status={item.status}/></td><td>{formatDate((item as Tenant & {updated_at?: string}).updated_at)}</td><td><Link className="row-link" to={`/admin/tenants/${item.id}`}>Öffnen <ExternalLink size={14}/></Link></td></tr>)}</tbody></table></div> : <Empty title="Keine Tenants" text="Erstellen Sie den ersten Tenant über den geführten Wizard."/>}
    </Card></>
}

type TenantDetail = Omit<Tenant, 'memberships' | 'task_templates'> & { memberships: Array<{ id: string; user_id?: string; group_id?: string; principal_name: string; role_code: string }>; task_templates: TaskTemplate[] }
type Group = { id: string; name: string; user_ids: string[] }

export function TenantDetailPage() {
  const { tenantId } = useParams()
  const qc = useQueryClient()
  const query = useQuery({ queryKey: ['admin-tenant', tenantId], queryFn: () => api<TenantDetail>(`/admin/tenants/${tenantId}`), enabled: Boolean(tenantId) })
  const users = useQuery({ queryKey: ['admin-users'], queryFn: () => api<User[]>('/admin/users') })
  const groups = useQuery({ queryKey: ['admin-groups'], queryFn: () => api<Group[]>('/admin/groups') })
  const [editOpen, setEditOpen] = useState(false)
  const [memberOpen, setMemberOpen] = useState(false)
  const [policyTask, setPolicyTask] = useState<TaskTemplate | null>(null)
  const [message, setMessage] = useState('')
  const refresh = () => void qc.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
  const sync = useMutation({ mutationFn: () => api(`/admin/tenants/${tenantId}/sync-templates`, { method: 'POST' }), onSuccess: () => { setMessage('Task Templates wurden synchronisiert.'); refresh() } })
  const check = useMutation({ mutationFn: () => api(`/admin/tenants/${tenantId}/check`, { method: 'POST' }), onSuccess: () => { setMessage('Semaphore-Projekt wurde erfolgreich geprüft.'); refresh() } })
  if (query.isLoading) return <Loading />
  if (!query.data) return <Notice type="error">Tenant konnte nicht geladen werden.</Notice>
  const tenant = query.data
  return <><PageHeader title={tenant.display_name} description={`${tenant.tenant_slug} · Tenant-Detailansicht`} actions={<><a className="button button-secondary" href={`/api/admin/tenants/${tenant.id}/export`} target="_blank"><Download size={16}/>Export</a><Button variant="secondary" onClick={() => setEditOpen(true)}><Save size={16}/>Bearbeiten</Button></>}/>
    {message && <Notice type="success">{message}</Notice>}
    <div className="detail-grid"><Card><div className="card-heading"><div><h2>Konfiguration</h2><p>Portal- und Semaphore-Zuordnung</p></div><StatusBadge status={tenant.status}/></div><dl className="detail-list"><div><dt>Anwendung</dt><dd>{tenant.application_id || 'Nicht gesetzt'}</dd></div><div><dt>Konfiguration</dt><dd>{tenant.configuration_complete ? <Badge tone="success">Vollständig</Badge> : <Badge tone="warning">Unvollständig</Badge>}</dd></div><div><dt>Semaphore-Projekt</dt><dd>{tenant.semaphore_project ? `${tenant.semaphore_project.name} (#${tenant.semaphore_project.id})` : 'Nicht zugeordnet'}</dd></div></dl><div className="button-row"><Button variant="secondary" loading={check.isPending} onClick={() => check.mutate()}><CheckCircle2 size={16}/>Verbindung prüfen</Button><Button variant="secondary" loading={sync.isPending} onClick={() => sync.mutate()}><RefreshCw size={16}/>Tasks synchronisieren</Button></div></Card>
      <Card><div className="card-heading"><div><h2>Zugeordnete Benutzer & Gruppen</h2><p>Direkte und gruppenbasierte Tenant-Zugriffe</p></div><Button variant="secondary" onClick={() => setMemberOpen(true)}><Plus size={16}/>Zuweisen</Button></div>{tenant.memberships.length ? <div className="compact-list">{tenant.memberships.map(item => <div key={item.id}><div><strong>{item.principal_name}</strong><span>{item.user_id ? 'Benutzer' : 'Gruppe'}</span></div><Badge>{item.role_code}</Badge></div>)}</div> : <p className="muted">Noch keine Zugriffe vergeben.</p>}</Card>
    </div>
    <Card><div className="card-heading"><div><h2>Freigegebene Task Templates</h2><p>Eine aktive Policy ist Voraussetzung für die Benutzerfreigabe.</p></div></div>{tenant.task_templates.length ? <div className="table-wrap"><table><thead><tr><th>Task</th><th>Semaphore-ID</th><th>Survey-Felder</th><th>Freigabe</th><th/></tr></thead><tbody>{tenant.task_templates.map(task => <tr key={task.id}><td><strong>{task.name}</strong><span className="subtle">{task.description}</span></td><td>#{task.semaphore_template_id}</td><td>{task.survey_schema?.length || 0}</td><td>{task.has_policy ? <Badge tone={task.is_enabled ? 'success' : 'warning'}>{task.is_enabled ? 'Aktiv' : 'Inaktiv'}</Badge> : <Badge tone="neutral">Keine Policy</Badge>}</td><td><Button variant="ghost" onClick={() => setPolicyTask(task)}>Policy bearbeiten</Button></td></tr>)}</tbody></table></div> : <Empty title="Keine Task Templates" text="Synchronisieren Sie die Task Templates mit Semaphore."/>}</Card>
    {editOpen && <EditTenantModal tenant={tenant} onClose={() => setEditOpen(false)} onSaved={() => { setEditOpen(false); refresh() }}/>} 
    {memberOpen && <MembershipModal tenant={tenant} users={users.data || []} groups={groups.data || []} onClose={() => setMemberOpen(false)} onSaved={() => { setMemberOpen(false); refresh() }}/>} 
    {policyTask && <PolicyModal task={policyTask} onClose={() => setPolicyTask(null)} onSaved={() => { setPolicyTask(null); refresh() }}/>} 
  </>
}

function EditTenantModal({ tenant, onClose, onSaved }: { tenant: TenantDetail; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(tenant.display_name), [description, setDescription] = useState(tenant.description), [status, setStatus] = useState(tenant.status)
  const [error, setError] = useState('')
  const mutation = useMutation({ mutationFn: () => api(`/admin/tenants/${tenant.id}`, { method: 'PATCH', body: JSON.stringify({ display_name: name, description, status }), headers: {'Content-Type':'application/json'} }), onSuccess: onSaved, onError: (e: Error) => setError(e.message) })
  const [confirm, setConfirm] = useState('')
  const remove = useMutation({ mutationFn: () => api(`/admin/tenants/${tenant.id}?confirm=${encodeURIComponent(confirm)}`, { method: 'DELETE' }), onSuccess: () => window.location.assign('/admin/tenants'), onError: (e: Error) => setError(e.message) })
  return <Modal title="Tenant bearbeiten" onClose={onClose}>{error && <Notice type="error">{error}</Notice>}<div className="form-grid"><Field label="Anzeigename"><input value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Status"><select value={status} onChange={e=>setStatus(e.target.value as Tenant['status'])}><option value="draft">Entwurf</option><option value="active">Aktiv</option><option value="inactive">Deaktiviert</option></select></Field><Field label="Beschreibung"><textarea rows={4} value={description} onChange={e=>setDescription(e.target.value)}/></Field></div><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>mutation.mutate()}>Speichern</Button></div><div className="danger-zone"><h3><Trash2 size={17}/>Portal-Tenant entfernen</h3><p>Das Semaphore-Projekt bleibt ausdrücklich erhalten. Zur Bestätigung <strong>{tenant.tenant_slug}</strong> eingeben.</p><div className="button-row"><input value={confirm} onChange={e=>setConfirm(e.target.value)} placeholder={tenant.tenant_slug}/><Button variant="danger" disabled={confirm!==tenant.tenant_slug} loading={remove.isPending} onClick={()=>remove.mutate()}>Tenant entfernen</Button></div></div></Modal>
}

function MembershipModal({ tenant, users, groups, onClose, onSaved }: { tenant: TenantDetail; users: User[]; groups: Group[]; onClose:()=>void; onSaved:()=>void }) {
  const [kind,setKind]=useState<'user'|'group'>('user'), [id,setId]=useState(''), [role,setRole]=useState('viewer'), [error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>api(`/admin/tenants/${tenant.id}/memberships`,{method:'POST',body:JSON.stringify({[kind==='user'?'user_id':'group_id']:id,role_code:role}),headers:{'Content-Type':'application/json'}}),onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  const options=kind==='user'?users:groups
  return <Modal title="Tenant-Zugriff zuweisen" onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<div className="form-grid columns-2"><Field label="Typ"><select value={kind} onChange={e=>{setKind(e.target.value as 'user'|'group');setId('')}}><option value="user">Benutzer</option><option value="group">Gruppe</option></select></Field><Field label="Rolle"><select value={role} onChange={e=>setRole(e.target.value)}><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="tenant_admin">Tenant Admin</option></select></Field><Field label={kind==='user'?'Benutzer':'Gruppe'}><select value={id} onChange={e=>setId(e.target.value)}><option value="">Bitte wählen …</option>{options.map(item=><option key={item.id} value={item.id}>{'display_name' in item?item.display_name:item.name}</option>)}</select></Field></div><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button disabled={!id} loading={mutation.isPending} onClick={()=>mutation.mutate()}>Zuweisen</Button></div></Modal>
}

function PolicyModal({ task, onClose, onSaved }: { task: TaskTemplate; onClose:()=>void; onSaved:()=>void }) {
  const existing=useQuery({queryKey:['task-policy',task.id],queryFn:()=>api<{name:string;rules:unknown[]}|null>(`/admin/task-templates/${task.id}/policy`)})
  const defaults=(task.survey_schema||[]).map((field,index)=>({variable_name:String(field.name||''),title:String(field.title||field.name||''),help_text:String(field.description||''),rule_type:field.type==='enum'?'enum':'string',default_value:field.default_value??null,allowed_values:Array.isArray(field.values)?field.values.map((v:unknown)=>typeof v==='object'&&v!==null&&'value' in v?(v as {value:unknown}).value:v):null,is_required:Boolean(field.required),position:index}))
  const [text,setText]=useState(''),[name,setName]=useState(`${task.name} Policy`),[error,setError]=useState('')
  useEffect(()=>{if(existing.data!==undefined){setText(JSON.stringify(existing.data?.rules||defaults,null,2));if(existing.data?.name)setName(existing.data.name)}},[existing.data])
  if(existing.isLoading)return <Modal title="Task Policy" onClose={onClose}><Loading/></Modal>
  const mutation=useMutation({mutationFn:()=>api(`/admin/task-templates/${task.id}/policy`,{method:'PUT',body:JSON.stringify({name,is_active:true,rules:JSON.parse(text)}),headers:{'Content-Type':'application/json'}}),onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  return <Modal title={`Policy · ${task.name}`} onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<p className="muted">Fixed und Hidden werden nur serverseitig ergänzt. Enum, Zahlenbereiche, Text und Boolean erzeugen Benutzerfelder.</p><Field label="Policy-Name"><input value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Variablenregeln (JSON)" help="Regeln dürfen ausschließlich Namen aus dem aktuellen Semaphore-Survey verwenden."><textarea className="code-editor" rows={18} value={text} onChange={e=>setText(e.target.value)} spellCheck={false}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>{try{JSON.parse(text);setError('');mutation.mutate()}catch{setError('Das Regelwerk enthält ungültiges JSON.')}}}>Policy speichern</Button></div></Modal>
}
