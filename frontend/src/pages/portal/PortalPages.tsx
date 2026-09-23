import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Activity, ArrowRight, Boxes, CheckCircle2, Clock3, KeyRound, Play, Square } from 'lucide-react'
import { api, ApiError } from '../../api'
import { useAuth } from '../../auth'
import { Badge, Button, Card, Empty, Field, Loading, Notice, PageHeader, StatusBadge, formatDate } from '../../components/ui'
import type { TaskRun, TaskTemplate, Tenant } from '../../types'

type PortalDashboard={project_count:number;running_count:number;recent_runs:TaskRun[]}
export function PortalDashboardPage(){
  const {user}=useAuth(),query=useQuery({queryKey:['portal-dashboard'],queryFn:()=>api<PortalDashboard>('/portal/dashboard'),refetchInterval:20_000})
  if(query.isLoading)return <Loading/>
  const data=query.data!
  return <><div className="welcome"><div><span>GUTEN TAG, {user?.display_name.toUpperCase()}</span><h1>Was möchten Sie heute deployen?</h1><p>Sie sehen ausschließlich Projekte und Tasks, die für Sie freigegeben wurden.</p></div><div className="welcome-orb"><Boxes/></div></div><div className="portal-stats"><Card><span>Meine Projekte</span><strong>{data.project_count}</strong><Link to="/portal/projekte">Alle anzeigen <ArrowRight size={15}/></Link></Card><Card><span>Laufende Tasks</span><strong>{data.running_count}</strong><Link to="/portal/laufende-tasks">Überwachen <ArrowRight size={15}/></Link></Card></div><Card><div className="card-heading"><div><h2>Letzte Task-Ausführungen</h2><p>Ihre aktuellen und kürzlich abgeschlossenen Tasks</p></div><Link className="row-link" to="/portal/historie">Gesamte Historie</Link></div>{data.recent_runs.length?<RunsTable rows={data.recent_runs}/>:<Empty title="Noch keine Tasks" text="Starten Sie einen freigegebenen Task aus einem Ihrer Projekte."/>}</Card></>
}

export function MyProjectsPage(){
  const query=useQuery({queryKey:['portal-tenants'],queryFn:()=>api<Tenant[]>('/portal/tenants')})
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="Meine Projekte" description="Aktive Tenants und die für Sie freigegebenen Automatisierungen."/>{query.data?.length?<div className="project-grid">{query.data.map(item=><Link className="project-card" to={`/portal/projekte/${item.id}`} key={item.id}><div className="project-card-top"><div className="project-glyph"><Boxes/></div><Badge tone="success">Aktiv</Badge></div><h2>{item.display_name}</h2><code>{item.tenant_slug}</code><p>{item.description||'Keine Beschreibung hinterlegt.'}</p><span>Projekt öffnen <ArrowRight size={16}/></span></Link>)}</div>:<Empty title="Keine freigegebenen Projekte" text="Wenden Sie sich an einen Administrator, um Zugriff zu erhalten."/>}</>
}

type PortalTenant=Tenant&{task_templates:TaskTemplate[]}
export function ProjectDetailPage(){
  const {tenantId}=useParams(),query=useQuery({queryKey:['portal-tenant',tenantId],queryFn:()=>api<PortalTenant>(`/portal/tenants/${tenantId}`)})
  if(query.isLoading)return <Loading/>
  if(!query.data)return <Notice type="error">Projekt nicht gefunden.</Notice>
  const tenant=query.data
  return <><PageHeader title={tenant.display_name} description={`${tenant.tenant_slug} · ${tenant.application_id||'Keine Anwendung'}`}/><Card className="project-summary"><div><span>Projektbeschreibung</span><p>{tenant.description||'Keine Beschreibung hinterlegt.'}</p></div><div><span>Freigegebene Tasks</span><strong>{tenant.task_templates.length}</strong></div></Card><div className="section-heading"><h2>Verfügbare Tasks</h2><p>Alle Eingaben werden zusätzlich im Backend gegen die Tenant-Policy geprüft.</p></div><div className="task-grid">{tenant.task_templates.map(task=><Card key={task.id} className="task-card"><div className="task-icon"><Play/></div><div><h3>{task.name}</h3><p>{task.description||'Semaphore Task Template'}</p><div className="badge-row"><Badge>{task.app}</Badge>{task.can_start?<Badge tone="success">Start erlaubt</Badge>:<Badge tone="neutral">Nur Ansicht</Badge>}</div></div><Link className={`button ${task.can_start?'button-primary':'button-secondary'}`} to={`/portal/projekte/${tenant.id}/tasks/${task.id}`}>{task.can_start?'Task starten':'Details'}</Link></Card>)}</div></>
}

type FormField={name:string;title:string;help_text:string;type:'enum'|'integer_range'|'string'|'boolean';default:unknown;allowed_values?:unknown[];minimum?:number;maximum?:number;max_length?:number;required:boolean}
type TaskForm={task:{id:string;name:string;description:string};fields:FormField[];can_start:boolean}
export function TaskStartPage(){
  const {tenantId,taskId}=useParams(),navigate=useNavigate(),query=useQuery({queryKey:['task-form',tenantId,taskId],queryFn:()=>api<TaskForm>(`/portal/tenants/${tenantId}/tasks/${taskId}/form`)})
  const [values,setValues]=useState<Record<string,unknown>>({}),[errors,setErrors]=useState<Record<string,string>>({}),[message,setMessage]=useState('')
  useEffect(()=>{if(query.data){const defaults:Record<string,unknown>={};query.data.fields.forEach(field=>{if(field.default!==null&&field.default!==undefined)defaults[field.name]=field.default;else if(field.type==='boolean')defaults[field.name]=false});setValues(defaults)}},[query.data])
  const mutation=useMutation({mutationFn:()=>api<TaskRun>(`/portal/tenants/${tenantId}/tasks/${taskId}/runs`,{method:'POST',body:JSON.stringify({variables:values}),headers:{'Content-Type':'application/json'}}),onSuccess:run=>navigate(`/portal/runs/${run.id}`),onError:reason=>{if(reason instanceof ApiError&&reason.fields)setErrors(reason.fields);else setMessage(reason instanceof Error?reason.message:'Task konnte nicht gestartet werden.')}})
  if(query.isLoading)return <Loading/>
  if(!query.data)return <Notice type="error">Task nicht gefunden.</Notice>
  return <><PageHeader title={`Task starten · ${query.data.task.name}`} description={query.data.task.description||'Eingaben werden serverseitig validiert.'}/><div className="run-layout"><Card><div className="card-heading"><div><h2>Task-Parameter</h2><p>Nur von der Policy freigegebene Felder werden angezeigt.</p></div><Badge tone="info">Servervalidiert</Badge></div>{message&&<Notice type="error">{message}</Notice>}<div className="form-grid columns-2">{query.data.fields.map(field=><DynamicField key={field.name} field={field} value={values[field.name]} error={errors[field.name]} onChange={value=>{setValues(current=>({...current,[field.name]:value}));setErrors(current=>({...current,[field.name]:''}))}}/>)}</div><div className="task-confirm"><ShieldSummary/><Button disabled={!query.data.can_start} loading={mutation.isPending} onClick={()=>mutation.mutate()}><Play size={16}/>Task jetzt starten</Button></div></Card><Card className="policy-card"><h3>Was geschieht beim Start?</h3><ol><li>Zugriff und Benutzerstatus prüfen</li><li>Eingaben gegen die Tenant-Policy validieren</li><li>Fixed/Hidden-Werte serverseitig ergänzen</li><li>Nur validierte Parameter an Semaphore senden</li><li>Task-ID und ausführenden Benutzer protokollieren</li></ol></Card></div></>
}

function DynamicField({field,value,error,onChange}:{field:FormField;value:unknown;error?:string;onChange:(value:unknown)=>void}){
  if(field.type==='enum')return <Field label={field.title} help={field.help_text} error={error}><select value={String(value??'')} onChange={e=>{const original=field.allowed_values?.find(item=>String(item)===e.target.value);onChange(original??e.target.value)}}>{field.allowed_values?.map(item=><option value={String(item)} key={String(item)}>{String(item)}</option>)}</select></Field>
  if(field.type==='integer_range')return <Field label={field.title} help={`${field.help_text} (${field.minimum}–${field.maximum})`} error={error}><input type="number" min={field.minimum} max={field.maximum} value={Number(value??field.minimum??0)} onChange={e=>onChange(Number(e.target.value))}/></Field>
  if(field.type==='boolean')return <Field label={field.title} help={field.help_text} error={error}><label className="toggle-row compact"><input type="checkbox" checked={Boolean(value)} onChange={e=>onChange(e.target.checked)}/><span>{value?'Ja':'Nein'}</span></label></Field>
  return <Field label={field.title} help={field.help_text} error={error}><input value={String(value??'')} maxLength={field.max_length} onChange={e=>onChange(e.target.value)}/></Field>
}
function ShieldSummary(){return <div className="shield-summary"><CheckCircle2/><div><strong>Sichere Ausführung</strong><span>Nicht freigegebene Variablen werden abgelehnt.</span></div></div>}

export function RunsPage({runningOnly=false}:{runningOnly?:boolean}){
  const query=useQuery({queryKey:['portal-runs'],queryFn:()=>api<TaskRun[]>('/portal/runs'),refetchInterval:runningOnly?10_000:30_000})
  if(query.isLoading)return <Loading/>
  const rows=(query.data||[]).filter(run=>!runningOnly||['queued','running'].includes(run.status))
  return <><PageHeader title={runningOnly?'Laufende Tasks':'Task-Historie'} description={runningOnly?'Aktive Semaphore-Ausführungen und deren aktueller Zustand.':'Alle für Sie sichtbaren Portal-Ausführungen.'}/>{rows.length?<Card><RunsTable rows={rows}/></Card>:<Empty title={runningOnly?'Keine laufenden Tasks':'Keine Task-Historie'} text={runningOnly?'Derzeit laufen keine freigegebenen Tasks.':'Gestartete Tasks erscheinen hier.'}/>}</>
}

function RunsTable({rows}:{rows:TaskRun[]}){return <div className="table-wrap"><table><thead><tr><th>Task</th><th>Tenant</th><th>Benutzer</th><th>Status</th><th>Start</th><th>Laufzeit</th><th/></tr></thead><tbody>{rows.map(run=><tr key={run.id}><td><strong>{run.task_template}</strong><span className="subtle">Semaphore #{run.semaphore_task_id}</span></td><td>{run.tenant}</td><td>{run.started_by}</td><td><StatusBadge status={run.status}/></td><td>{formatDate(run.started_at)}</td><td>{run.duration_seconds==null?'–':`${run.duration_seconds}s`}</td><td><Link className="row-link" to={`/portal/runs/${run.id}`}>Öffnen <ArrowRight size={14}/></Link></td></tr>)}</tbody></table></div>}

type RunDetail=TaskRun&{output:Array<{task_id:number;time:string;output:string}>}
export function RunDetailPage(){
  const {runId}=useParams(),qc=useQueryClient(),query=useQuery({queryKey:['run',runId],queryFn:()=>api<RunDetail>(`/portal/runs/${runId}`)}),[liveLines,setLiveLines]=useState<RunDetail['output']>([]),[streamError,setStreamError]=useState('')
  const stop=useMutation({mutationFn:()=>api(`/portal/runs/${runId}/stop`,{method:'POST'}),onSuccess:()=>void qc.invalidateQueries({queryKey:['run',runId]})})
  useEffect(()=>{if(!runId)return;const source=new EventSource(`/api/portal/runs/${runId}/events`);source.addEventListener('update',event=>{const data=JSON.parse((event as MessageEvent).data) as {lines:RunDetail['output']};if(data.lines.length)setLiveLines(current=>[...current,...data.lines])});source.addEventListener('complete',()=>{source.close();void qc.invalidateQueries({queryKey:['run',runId]})});source.addEventListener('error',()=>{setStreamError('Live-Verbindung wurde beendet.');source.close()});return()=>source.close()},[runId,qc])
  if(query.isLoading)return <Loading/>
  if(!query.data)return <Notice type="error">Task nicht gefunden.</Notice>
  const run=query.data,lines=liveLines.length?liveLines:run.output
  return <><PageHeader title={run.task_template} description={`${run.tenant} · Semaphore Task #${run.semaphore_task_id}`} actions={['running','queued'].includes(run.status)?<Button variant="danger" loading={stop.isPending} onClick={()=>stop.mutate()}><Square size={15}/>Abbrechen</Button>:undefined}/><div className="run-meta"><Card><span>Status</span><StatusBadge status={run.status}/></Card><Card><span>Gestartet</span><strong>{formatDate(run.started_at)}</strong></Card><Card><span>Ausgeführt von</span><strong>{run.started_by}</strong></Card><Card><span>Laufzeit</span><strong>{run.duration_seconds||0}s</strong></Card></div>{streamError&&<Notice type="info">{streamError}</Notice>}<Card className="terminal-card"><div className="terminal-head"><div><span/><span/><span/></div><strong>Task-Ausgabe</strong><Badge tone={run.status==='running'?'warning':'neutral'}>{run.status==='running'?'LIVE':'LOG'}</Badge></div><div className="terminal">{lines.length?lines.map((line,index)=><div key={`${line.time}-${index}`}><time>{new Date(line.time).toLocaleTimeString('de-DE')}</time><code>{line.output}</code></div>):<span className="terminal-empty">Warte auf Ausgabe …</span>}</div></Card></>
}

export function AccountPage(){
  const {user,refresh}=useAuth(),[current,setCurrent]=useState(''),[next,setNext]=useState(''),[repeat,setRepeat]=useState(''),[message,setMessage]=useState(''),[error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>api<{message:string}>('/auth/password',{method:'POST',body:JSON.stringify({current_password:current,new_password:next}),headers:{'Content-Type':'application/json'}}),onSuccess:data=>{setMessage(data.message);setError('');setCurrent('');setNext('');setRepeat('');void refresh()},onError:(e:Error)=>setError(e.message)})
  return <><PageHeader title="Mein Konto" description="Persönliche Kontodaten und Passwortsicherheit."/><div className="settings-grid"><Card><div className="account-hero"><div className="avatar large">{user?.display_name.slice(0,2).toUpperCase()}</div><div><h2>{user?.display_name}</h2><p>{user?.email}</p><div className="badge-row">{user?.roles.map(role=><Badge key={role}>{role}</Badge>)}</div></div></div></Card><Card><div className="card-heading"><div><h2>Passwort ändern</h2><p>Alle anderen aktiven Sitzungen werden beendet.</p></div><KeyRound/></div>{message&&<Notice type="success">{message}</Notice>}{error&&<Notice type="error">{error}</Notice>}<div className="form-grid"><Field label="Aktuelles Passwort"><input type="password" value={current} onChange={e=>setCurrent(e.target.value)}/></Field><Field label="Neues Passwort" help="Mindestens 12 Zeichen"><input type="password" value={next} onChange={e=>setNext(e.target.value)}/></Field><Field label="Neues Passwort wiederholen" error={repeat&&repeat!==next?'Passwörter stimmen nicht überein.':undefined}><input type="password" value={repeat} onChange={e=>setRepeat(e.target.value)}/></Field></div><Button disabled={!current||next.length<12||next!==repeat} loading={mutation.isPending} onClick={()=>mutation.mutate()}>Passwort ändern</Button></Card></div></>
}
