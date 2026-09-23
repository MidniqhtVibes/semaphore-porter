import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ShieldCheck } from 'lucide-react'
import { api } from '../../api'
import { Badge, Button, Card, Empty, Field, Loading, Notice, PageHeader, StatusBadge, formatDate } from '../../components/ui'
import type { TaskRun, TaskTemplate, Tenant, User } from '../../types'

type Audit={id:string;occurred_at:string;actor_user_id?:string|null;event_type:string;target_type?:string;target_id?:string;details:Record<string,unknown>;success:boolean}
export function AdminTasksPage(){
  const query=useQuery({queryKey:['admin-task-runs'],queryFn:()=>api<TaskRun[]>('/admin/task-runs'),refetchInterval:15_000})
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="Task-Überwachung" description="Alle vom Portal ausgelösten Semaphore-Tasks."/>{query.data?.length?<Card><div className="table-wrap"><table><thead><tr><th>Task</th><th>Tenant</th><th>Ausgeführt von</th><th>Status</th><th>Start</th><th>Semaphore-ID</th></tr></thead><tbody>{query.data.map(run=><tr key={run.id}><td><strong>{run.task_template}</strong></td><td>{run.tenant}</td><td>{run.started_by}</td><td><StatusBadge status={run.status}/></td><td>{formatDate(run.started_at)}</td><td>#{run.semaphore_task_id}</td></tr>)}</tbody></table></div></Card>:<Empty title="Keine Task-Ausführungen" text="Vom Portal gestartete Tasks erscheinen hier."/>}</>
}

export function AuditPage(){
  const [filter,setFilter]=useState(''),query=useQuery({queryKey:['audit',filter],queryFn:()=>api<Audit[]>(`/admin/audit${filter?`?event_type=${encodeURIComponent(filter)}`:''}`)})
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="Audit-Log" description="Nachvollziehbare Aktionen ohne Tokens oder geheime Variablenwerte."/><Card><div className="toolbar"><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="">Alle Ereignisse</option><option value="login">Anmeldungen</option><option value="login_failed">Fehlgeschlagene Anmeldungen</option><option value="tenant_created">Tenant erstellt</option><option value="permission_changed">Berechtigungen</option><option value="task_started">Task gestartet</option></select><span>{query.data?.length||0} Ereignisse</span></div><div className="audit-list">{query.data?.map(event=><div className="audit-row" key={event.id}><div className={`audit-icon ${event.success?'':'error'}`}><Activity size={16}/></div><div><div className="audit-top"><strong>{event.event_type}</strong><Badge tone={event.success?'success':'danger'}>{event.success?'Erfolgreich':'Fehler'}</Badge></div><span>{event.target_type||'Portal'} {event.target_id&&`· ${event.target_id}`}</span><pre>{Object.keys(event.details||{}).length?JSON.stringify(event.details):''}</pre></div><time>{formatDate(event.occurred_at)}</time></div>)}</div></Card></>
}

type TenantDetail=Tenant&{task_templates:TaskTemplate[]}
type Group={id:string;name:string}
type Permission={id:string;user_id?:string|null;group_id?:string|null;can_view:boolean;can_start:boolean;can_stop:boolean}
export function PermissionsPage(){
  const qc=useQueryClient(),[tenantId,setTenantId]=useState(''),[taskId,setTaskId]=useState(''),[kind,setKind]=useState<'user'|'group'>('user'),[principal,setPrincipal]=useState(''),[role,setRole]=useState('operator'),[error,setError]=useState('')
  const tenants=useQuery({queryKey:['admin-tenants'],queryFn:()=>api<Tenant[]>('/admin/tenants')})
  const tenant=useQuery({queryKey:['admin-tenant',tenantId],queryFn:()=>api<TenantDetail>(`/admin/tenants/${tenantId}`),enabled:Boolean(tenantId)})
  const permissions=useQuery({queryKey:['task-permissions',taskId],queryFn:()=>api<Permission[]>(`/admin/task-templates/${taskId}/permissions`),enabled:Boolean(taskId)})
  const users=useQuery({queryKey:['admin-users'],queryFn:()=>api<User[]>('/admin/users')}),groups=useQuery({queryKey:['admin-groups'],queryFn:()=>api<Group[]>('/admin/groups')})
  const add=useMutation({mutationFn:()=>api(`/admin/task-templates/${taskId}/permissions`,{method:'POST',body:JSON.stringify({[kind==='user'?'user_id':'group_id']:principal,can_view:true,can_start:role==='operator',can_stop:role==='operator'}),headers:{'Content-Type':'application/json'}}),onSuccess:()=>{setPrincipal('');setError('');void qc.invalidateQueries({queryKey:['task-permissions',taskId]})},onError:(e:Error)=>setError(e.message)})
  if(tenants.isLoading||users.isLoading||groups.isLoading)return <Loading/>
  const principals=kind==='user'?(users.data||[]):(groups.data||[])
  const label=(p:Permission)=>p.user_id?users.data?.find(x=>x.id===p.user_id)?.display_name:groups.data?.find(x=>x.id===p.group_id)?.name
  return <><PageHeader title="Berechtigungsmatrix" description="Benutzer/Gruppe → Tenant → Task Template → erlaubte Aktionen."/><Card><div className="form-grid columns-3"><Field label="Tenant"><select value={tenantId} onChange={e=>{setTenantId(e.target.value);setTaskId('')}}><option value="">Bitte wählen …</option>{tenants.data?.map(item=><option value={item.id} key={item.id}>{item.display_name}</option>)}</select></Field><Field label="Task Template"><select value={taskId} onChange={e=>setTaskId(e.target.value)} disabled={!tenantId}><option value="">Bitte wählen …</option>{tenant.data?.task_templates.map(item=><option value={item.id} key={item.id}>{item.name}</option>)}</select></Field></div></Card>
    {taskId&&<div className="permissions-grid"><Card><div className="card-heading"><div><h2>Zugewiesene Rechte</h2><p>Direkte und gruppenbasierte Freigaben</p></div><ShieldCheck/></div>{permissions.isLoading?<Loading/>:<div className="compact-list">{permissions.data?.map(item=><div key={item.id}><div><strong>{label(item)||'Unbekannter Principal'}</strong><span>{item.user_id?'Benutzer':'Gruppe'}</span></div><div className="badge-row"><Badge>sehen</Badge>{item.can_start&&<Badge tone="success">starten</Badge>}{item.can_stop&&<Badge tone="warning">abbrechen</Badge>}</div></div>)}</div>}</Card><Card><h2>Berechtigung vergeben</h2>{error&&<Notice type="error">{error}</Notice>}<div className="form-grid"><Field label="Principal-Typ"><select value={kind} onChange={e=>{setKind(e.target.value as 'user'|'group');setPrincipal('')}}><option value="user">Benutzer</option><option value="group">Gruppe</option></select></Field><Field label={kind==='user'?'Benutzer':'Gruppe'}><select value={principal} onChange={e=>setPrincipal(e.target.value)}><option value="">Bitte wählen …</option>{principals.map(item=><option value={item.id} key={item.id}>{'display_name' in item?item.display_name:item.name}</option>)}</select></Field><Field label="Aktionen"><select value={role} onChange={e=>setRole(e.target.value)}><option value="viewer">Nur sehen</option><option value="operator">Sehen, starten, abbrechen</option></select></Field></div><Button disabled={!principal} loading={add.isPending} onClick={()=>add.mutate()}>Berechtigung speichern</Button></Card></div>}
  </>
}

