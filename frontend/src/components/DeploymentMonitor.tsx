import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Download, Plus, RefreshCw, RotateCcw, Send, Server, Trash2 } from 'lucide-react'
import { api, apiUrl } from '../api'
import { useRuntime } from '../demo/runtime'
import { Badge, Button, Card, Empty, Field, Loading, Modal, Notice, formatDate } from './ui'

export type Deployment = {
  id:string; deployment_id:string; source_id:string; host:string; tenant_name:string; tenant_slug:string; runtime_scope_id:string
  semaphore_project_id:number|null; application_id:string; application_name:string; release_id:string; database_type:string
  provider_id:string; database_mode:string; dataset_id:string; source_git_commit:string; url:string; host_port:number|null
  created_at:number|null; ready_at:number|null; expires_at:number|null; observed_at:number; status:string; lifecycle_status:string
  container_count:number|null; running_count:number|null; unhealthy_count:number|null; starting_count:number|null; stale:boolean; metadata_error:boolean
}
type Source={id:string;name:string;received_at:string|null;observed_at:number|null;stale:boolean;complete:boolean;warnings:string[];deployment_count:number}
export type MonitoringSnapshot={server_time:number;stale_after_seconds:number;sources:Source[];deployments:Deployment[]}
const labels:Record<string,string>={running:'Läuft',preparing:'Wird vorbereitet',starting:'Container starten',degraded:'Gestört',stopped:'Gestoppt',missing:'Container fehlen',expired:'TTL abgelaufen',cleanup_pending:'Cleanup ausstehend',unknown:'Unbekannt'}
const warningLabels:Record<string,string>={root_unavailable:'Deployment-Verzeichnis nicht lesbar',metadata_unreadable:'Metadaten teilweise nicht lesbar',docker_unavailable:'Containerzustand nicht abrufbar',limit_exceeded:'Grenze von 1.000 Deployments erreicht'}
const date=(value:number|null|undefined)=>value?formatDate(new Date(value*1000).toISOString()):'–'

export function remaining(expires:number|null,now:number){
  if(!expires)return 'Nicht gemeldet'
  const seconds=Math.max(0,Math.ceil(expires-now)),hours=Math.floor(seconds/3600),minutes=Math.floor(seconds%3600/60)
  return `${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`
}
function currentStatus(row:Deployment,now:number,staleAfter:number){
  if(row.stale||now-row.observed_at>staleAfter)return 'unknown'
  if(row.metadata_error)return 'unknown'
  if(row.status==='cleanup_pending')return row.status
  return row.expires_at&&row.expires_at<=now?'expired':row.status
}
function DeploymentBadge({status}:{status:string}){
  const tone=status==='running'?'success':['degraded','missing','stopped'].includes(status)?'danger':status==='unknown'?'neutral':'warning'
  return <Badge tone={tone}>{labels[status]||status}</Badge>
}

export default function DeploymentMonitor(){
  const runtime=useRuntime()
  const qc=useQueryClient(),[tick,setTick]=useState(Date.now()),[filter,setFilter]=useState(''),[statusFilter,setStatusFilter]=useState(''),[selectedId,setSelectedId]=useState('')
  const [name,setName]=useState(''),[error,setError]=useState(''),[issued,setIssued]=useState<{name:string;token:string}|null>(null)
  const query=useQuery({queryKey:['deployment-monitoring'],queryFn:()=>api<MonitoringSnapshot>('/admin/deployments'),refetchInterval:10_000})
  useEffect(()=>{const id=window.setInterval(()=>setTick(Date.now()),1000);return()=>window.clearInterval(id)},[])
  const create=useMutation({mutationFn:()=>api<{name:string;token:string}>('/admin/deployments/sources',{method:'POST',body:JSON.stringify({name})}),onSuccess:value=>{setIssued(value);setName('');setError('');void qc.invalidateQueries({queryKey:['deployment-monitoring']})},onError:(e:Error)=>setError(e.message)})
  const rotate=useMutation({mutationFn:(id:string)=>api<{name:string;token:string}>(`/admin/deployments/sources/${id}/token`,{method:'POST'}),onSuccess:value=>{setIssued(value);setError('')},onError:(e:Error)=>setError(e.message)})
  const remove=useMutation({mutationFn:(id:string)=>api(`/admin/deployments/sources/${id}`,{method:'DELETE'}),onSuccess:()=>{setError('');void qc.invalidateQueries({queryKey:['deployment-monitoring']})},onError:(e:Error)=>setError(e.message)})
  const data=query.data,now=data?data.server_time+Math.max(0,tick-query.dataUpdatedAt)/1000:tick/1000
  const staleAfter=data?.stale_after_seconds||90,all=data?.deployments||[]
  const stale=(row:Deployment)=>row.stale||now-row.observed_at>staleAfter
  const rows=all.filter(row=>(!statusFilter||currentStatus(row,now,staleAfter)===statusFilter)&&`${row.deployment_id} ${row.host} ${row.tenant_name} ${row.tenant_slug} ${row.runtime_scope_id} ${row.application_id}`.toLowerCase().includes(filter.toLowerCase()))
  const selected=all.find(row=>row.id===selectedId)
  return <section aria-label="Live-Deployments">
    <div className="card-heading monitoring-heading"><div><h2>Live-Deployments</h2><p>Hostzustand alle 15 Sekunden, Ansicht alle 10 Sekunden; Countdown jede Sekunde. Erfasst auch direkt in Semaphore gestartete Deployments auf angebundenen Hosts.</p></div><Button variant="secondary" loading={query.isFetching} onClick={()=>void query.refetch()}><RefreshCw size={15} aria-hidden="true"/>Jetzt aktualisieren</Button></div>
    {query.isError&&<Notice type="error">Überwachung konnte nicht aktualisiert werden: {query.error.message}</Notice>}
    {error&&<Notice type="error">{error}</Notice>}
    {runtime.mode==='demo'&&<Notice type="info">Simulierte Hostdaten: Für die Demo sind kein Collector, Dienstkonto, Docker-Zugriff oder zusätzlicher Port nötig. Die Einrichtung unten zeigt den späteren Ablauf für echte Zielhosts.</Notice>}
    {issued&&<Notice type="info"><strong>Collector-Token für {issued.name}</strong><p>Nur jetzt sichtbar. Als geschützte Token-Datei für den Sender hinterlegen und deren Pfad über SEMAPORTER_MONITOR_TOKEN_FILE übergeben. Dieser Token kann ausschließlich Monitoring-Daten für diese Quelle senden.</p><Field label="Einmaliger Collector-Token"><input readOnly autoComplete="off" spellCheck={false} value={issued.token} onFocus={e=>e.target.select()}/></Field><Button variant="secondary" onClick={()=>setIssued(null)}>Token ausblenden</Button></Notice>}
    {query.isLoading?<Loading/>:<>
      <div className="toolbar"><Badge>{all.length} Deployments</Badge><Badge tone="success">{all.filter(row=>currentStatus(row,now,staleAfter)==='running').length} laufen</Badge><Badge tone="warning">{all.filter(row=>['expired','cleanup_pending'].includes(currentStatus(row,now,staleAfter))).length} abgelaufen / Cleanup</Badge><Badge>{all.filter(stale).length} veraltet</Badge></div>
      <Card><div className="form-grid columns-3"><Field label="Deployment suchen"><input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Tenant, Anwendung, Host, ID …"/></Field><Field label="Deployment-Status"><select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="">Alle Zustände</option>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></Field></div>
      {rows.length?<div className="table-wrap"><table><thead><tr><th>Deployment / Anwendung</th><th>Tenant / Scope</th><th>Host</th><th>Status</th><th>Restlaufzeit (TTL)</th><th>Container</th><th>Details</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}>
        <td><strong>{row.application_name||row.application_id||'Anwendung noch unbekannt'}</strong><span className="subtle">{row.deployment_id}</span></td>
        <td>{row.tenant_name||'Nicht zugeordnet'}<span className="subtle">{row.runtime_scope_id||'–'}</span></td><td>{row.host}</td>
        <td><DeploymentBadge status={currentStatus(row,now,staleAfter)}/>{stale(row)&&<span className="subtle">Meldung veraltet</span>}{row.metadata_error&&<span className="subtle">Metadaten unvollständig</span>}</td>
        <td><strong>{remaining(row.expires_at,now)}</strong><span className="subtle">{row.expires_at?`Bis ${date(row.expires_at)}`:row.lifecycle_status==='preparing'?'Beginnt nach Readiness':'Keine Ablaufzeit verfügbar'}{stale(row)&&row.expires_at?' · letzter bekannter Stand':''}</span></td>
        <td>{row.container_count===null?'Unbekannt':`${row.running_count}/${row.container_count} laufen`}{Boolean(row.unhealthy_count)&&<span className="subtle">{row.unhealthy_count} unhealthy</span>}</td>
        <td><Button variant="ghost" onClick={()=>setSelectedId(row.id)}>Ansehen</Button></td>
      </tr>)}</tbody></table></div>:<Empty title={data?.sources.length?'Keine passenden Deployments':'Noch keine Monitoring-Quelle'} text={data?.sources.length?'Die Ansicht zeigt den letzten gemeldeten Hostzustand. Quellen und letzte Meldung unten prüfen.':'Pro Deployment-Zielhost unten eine Quelle anlegen und den lesenden Collector einrichten.'}/>}</Card>
      <details className="monitoring-setup"><summary><ChevronRight size={17} aria-hidden="true"/>Monitoring-Quellen und Einrichtung ({data?.sources.length||0})</summary><div className="monitoring-setup-content">
        <div className="monitoring-steps">
          <Card><span className="monitoring-step-number">1</span><h3>Quelle anlegen</h3><p>Eine Quelle steht für einen Deployment-Zielhost. Ihr Token berechtigt ausschließlich zum Senden von Monitoring-Daten.</p></Card>
          <Card><Server size={22} aria-hidden="true"/><h3>2 · Lokal erfassen</h3><p>Der Exporter liest Metadaten und Containerzustände und schreibt eine geschützte Statusdatei. Er erhält keinen Token und keinen Netzwerkzugang.</p><a className="button button-secondary" href={apiUrl("/admin/deployments/exporter")} download><Download size={15} aria-hidden="true"/>Status-Exporter herunterladen</a></Card>
          <Card><Send size={22} aria-hidden="true"/><h3>3 · Status übertragen</h3><p>Der Sender läuft unter einem eingeschränkten Dienstkonto ohne Docker-Rechte. Er liest die Statusdatei und meldet sie über HTTPS.</p><a className="button button-secondary" href={apiUrl("/admin/deployments/collector")} download><Download size={15} aria-hidden="true"/>Sender herunterladen</a></Card>
        </div>
        <Card><h3>Neue Monitoring-Quelle</h3><form className="monitoring-source-form" onSubmit={event=>{event.preventDefault();if(name.trim().length>=2&&!issued&&!create.isPending)create.mutate()}}><Field label="Name des Deployment-Zielhosts"><input required minLength={2} value={name} maxLength={160} onChange={e=>setName(e.target.value)} placeholder="Host eindeutig benennen"/></Field><Button type="submit" loading={create.isPending} disabled={name.trim().length<2||Boolean(issued)}><Plus size={16} aria-hidden="true"/>Quelle anlegen</Button></form><p className="monitoring-note">Python 3.10 oder neuer, keine Zusatzpakete. Exporter und Sender werden separat auf dem Zielhost eingerichtet. Die vollständige Anleitung steht im Projekt unter docs/DEPLOYMENT_MONITORING.md.</p></Card>
        <div className="monitoring-sources">{data?.sources.map(source=>{
          const sourceStale=source.stale||!source.observed_at||now-source.observed_at>staleAfter
          return <Card key={source.id}><div className="monitoring-source-heading"><div><Server size={18} aria-hidden="true"/><h3>{source.name}</h3></div><Badge tone={sourceStale?'warning':source.complete?'success':'warning'}>{sourceStale?'Keine aktuelle Meldung':source.complete?'Verbunden':'Teilweise erfasst'}</Badge></div>
            <dl className="monitoring-source-meta"><div><dt>Letzte Meldung</dt><dd>{source.observed_at?date(source.observed_at):'Noch keine'}</dd></div><div><dt>Deployments</dt><dd>{source.deployment_count}</dd></div></dl>
            {!source.complete&&!sourceStale&&<p className="monitoring-note">Letzte bekannte Einträge bleiben erhalten, bis ein vollständiger Snapshot vorliegt.</p>}
            {source.warnings.map(w=><p className="monitoring-source-warning" key={w}>{warningLabels[w]||w}</p>)}
            <div className="monitoring-source-actions"><Button variant="secondary" loading={rotate.isPending&&rotate.variables===source.id} disabled={Boolean(issued)||rotate.isPending||remove.isPending} onClick={()=>{if(window.confirm(`Collector-Token für ${source.name} erneuern? Der bisherige Token wird sofort ungültig.`))rotate.mutate(source.id)}}><RotateCcw size={15} aria-hidden="true"/>Token erneuern</Button><Button variant="danger" loading={remove.isPending&&remove.variables===source.id} disabled={Boolean(issued)||rotate.isPending||remove.isPending} onClick={()=>{if(window.confirm(`Monitoring-Quelle ${source.name} und ihre Anzeige entfernen? Deployments auf dem Host bleiben bestehen.`))remove.mutate(source.id)}}><Trash2 size={15} aria-hidden="true"/>Quelle entfernen</Button></div>
          </Card>
        })}</div>
        <p className="monitoring-note">Mehr als 90 Sekunden ohne frischen Snapshot: Zustand unbekannt. Ein abgelaufener Countdown bestätigt keine Löschung; diese erledigt weiterhin das bestehende Cleanup des Semaphore-Stacks. „Läuft“ bestätigt laufende Container, ohne konfigurierten Healthcheck keine Erreichbarkeit der Anwendung.</p>
      </div></details>
    </>}
    {selected&&<Modal title={`Deployment ${selected.deployment_id}`} onClose={()=>setSelectedId('')}>
      <dl>{Object.entries({'Host':selected.host,'Tenant':selected.tenant_name||selected.tenant_slug||'Nicht zugeordnet','Runtime-Scope':selected.runtime_scope_id,'Semaphore-Projekt':selected.semaphore_project_id?`#${selected.semaphore_project_id} (Tenant-Zuordnung)`:'Kein lokaler Tenant zugeordnet','Anwendung':selected.application_id,'Release':selected.release_id,'Datenbank':selected.database_type,'Provider':selected.provider_id,'DB-Modus':selected.database_mode,'Dataset':selected.dataset_id,'Git-Commit':selected.source_git_commit,'Host-Port':selected.host_port,'Erstellt':date(selected.created_at),'Bereit seit':date(selected.ready_at),'Ablauf':date(selected.expires_at),'Letzte Beobachtung':date(selected.observed_at)}).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value||'–'}</dd></div>)}</dl>
      {selected.url&&<p><a href={selected.url} target="_blank" rel="noopener noreferrer">Anwendung öffnen</a></p>}
      <p>Status: <DeploymentBadge status={currentStatus(selected,now,staleAfter)}/> · TTL {remaining(selected.expires_at,now)}</p>
      {stale(selected)&&<Notice type="info">Dies sind zuletzt bekannte Metadaten. Der aktuelle Containerzustand ist unbekannt.</Notice>}
    </Modal>}
  </section>
}
