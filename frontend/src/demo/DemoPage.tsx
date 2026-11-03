import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, FlaskConical, RotateCcw, ShieldCheck, Users } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Badge, Button, Card, Field, Notice, PageHeader } from '../components/ui'
import { useRuntime } from './runtime'

const actors=[['admin','Administrator','Alle Verwaltungsbereiche mit Dummy-Daten ausprobieren.'],['tenant_admin','Tenant-Admin','Freigegebene Tasks für Südtal ansehen und ausführen.'],['operator','Operator','Tasks für Nordstadt starten und abbrechen.'],['viewer','Viewer','Freigegebene Daten ansehen; Taskstarts werden abgelehnt.']] as const
const scenarios:Record<string,string>={normal:'Normaler Ablauf',task_failure:'Task schlägt nach dem Start fehl',task_http500:'Taskstart antwortet mit HTTP 500',vault_conflict:'Vault-Pfad existiert bereits',vault_uncertain:'Vault-Timeout nach erfolgtem Schreiben',gitlab_conflict:'GitLab-Versionskonflikt',commit_uncertain:'GitLab-Timeout nach erfolgtem Commit',monitor_stale:'Monitoring-Meldung veraltet',monitor_degraded:'Deployment gestört',ttl_expired:'Deployment-TTL abgelaufen',container_uncertain:'Agent-Antwort nach Containeraktion verloren'}
type Status={scenario:string;last_error:string|null;simulated:boolean}

export default function DemoPage(){
  const runtime=useRuntime(),auth=useAuth(),navigate=useNavigate(),qc=useQueryClient(),[error,setError]=useState(''),[pending,setPending]=useState(''),[message,setMessage]=useState('')
  const status=useQuery({queryKey:['demo-status'],queryFn:()=>api<Status>('/demo/status'),enabled:runtime.mode==='demo'&&auth.isAdmin,refetchInterval:5000})
  const scenario=useMutation({mutationFn:(name:string)=>api('/demo/scenario',{method:'POST',body:JSON.stringify({name})}),onSuccess:()=>{setError('');void qc.invalidateQueries({queryKey:['demo-status']});void qc.invalidateQueries({queryKey:['deployment-monitoring']})},onError:(e:Error)=>setError(e.message)})
  const merge=useMutation({mutationFn:()=>api<{merged:number}>('/demo/merge',{method:'POST'}),onSuccess:value=>{setMessage(`${value.merged} Merge Requests als zusammengeführt simuliert.`)},onError:(e:Error)=>setError(e.message)})
  const reset=useMutation({mutationFn:()=>api('/demo/reset',{method:'POST',body:JSON.stringify({confirm:true})}),onSuccess:()=>window.location.assign('/demo/'),onError:(e:Error)=>setError(e.message)})
  const choose=async(role:string)=>{setError('');setPending(role);try{const user=await auth.loginDemo(role);navigate(user.roles.includes('system_admin')?'/admin':'/portal')}catch(reason){setError((reason as Error).message)}finally{setPending('')}}
  if(runtime.mode==='production'){
    const target=runtime.demo_available?'/demo/':null
    return <div className="demo-entry"><PageHeader title="Semaporter ausprobieren" description="Die integrierte Präsentationsumgebung mit erfundenen Daten."/><Card><div className="demo-entry-icon"><FlaskConical size={30}/></div><h2>Die Oberfläche kennenlernen</h2><p>Benutzer und Tenants verwalten, simulierte Tasks starten, Deploymentzustände ansehen und Fehlerfälle vorführen. Die Demo verwendet eigene Daten und Sitzungen.</p>{target?<a className="button button-primary" href={target}><ArrowRight size={17}/>Demo öffnen</a>:<Notice type="info">Die Demo ist für dieses Portal deaktiviert.</Notice>}<p className="account-note">Ein Präsentationsdurchlauf ersetzt keinen Betriebstest der echten Integrationen.</p><Link className="button button-secondary" to={auth.user?(auth.isAdmin?'/admin':'/portal'):'/login'}>Zurück zum Portal</Link></Card></div>
  }
  return <div className="demo-entry demo-control"><PageHeader title="Demo-Steuerung" description="Alle Änderungen betreffen ausschließlich diese flüchtige Demo-Instanz."/>
    {error&&<Notice type="error">{error}</Notice>}{message&&<Notice type="success">{message}</Notice>}
    <Card><div className="card-heading"><div><h2>Mit einer Beispielrolle starten</h2><p>Die vorhandene Rechteprüfung bleibt aktiv. Wähle eine andere Rolle, um den Unterschied zu sehen.</p></div><Users size={22}/></div><div className="demo-actors">{actors.map(([value,label,description])=><div key={value}><ShieldCheck size={19}/><h3>{label}</h3><p>{description}</p><Button loading={pending===value} disabled={Boolean(pending)||auth.loading} onClick={()=>void choose(value)}>{label} starten</Button></div>)}</div><p className="account-note">Diese Rollenauswahl ist nur im isolierten Demo-Betriebsmodus vorhanden. <Link to="/login">Mit selbst angelegten Demo-Kontodaten anmelden</Link></p></Card>
    {auth.user&&<Card><div className="card-heading"><div><h2>Angemeldet als {auth.user.display_name}</h2><Badge tone="warning">Simulierte Integrationen</Badge></div><Link className="button button-secondary" to={auth.isAdmin?'/admin':'/portal'}>Oberfläche öffnen</Link></div></Card>}
    {auth.isAdmin&&<Card><h2>Vorführung steuern</h2>{status.error&&<Notice type="error">{status.error.message}</Notice>}{status.data?.last_error&&<Notice type="error">{status.data.last_error}</Notice>}
      <Field label="Simulationsszenario"><select value={status.data?.scenario||'normal'} disabled={scenario.isPending||!status.data} onChange={event=>scenario.mutate(event.target.value)}>{Object.entries(scenarios).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Field>
      <p className="account-note">Neue Aufrufe verwenden das gewählte Szenario. Bereits angelegte Objekte bleiben bestehen. Nach Konflikt- und Timeout-Szenarien kannst du den realen Wiederaufnahmeablauf im Portal zeigen.</p>
      <div className="demo-shortcuts">{[['/admin/benutzer','Benutzer & Gruppen'],['/admin/tenant-erstellen','Tenant erstellen'],['/admin/tasks','Deployment-Monitoring'],['/admin/container','Container-Verwaltung'],['/admin/programmpakete','Programmpakete'],['/admin/vault','Vault'],['/admin/zugangsprofile','SSH-Profile']].map(([to,label])=><Link key={to} className="button button-secondary" to={to}>{label}</Link>)}</div>
      <div className="demo-maintenance"><Button variant="secondary" loading={merge.isPending} onClick={()=>{if(window.confirm('Offene Demo-Merge-Requests als zusammengeführt simulieren?'))merge.mutate()}}>Review &amp; Merge simulieren</Button><Button variant="danger" loading={reset.isPending} onClick={()=>{if(window.confirm('Alle Daten und Sitzungen dieser Demo zurücksetzen?'))reset.mutate()}}><RotateCcw size={15}/>Demo zurücksetzen</Button></div>
      <p className="account-note">Die Demo-Daten werden von allen Besuchern dieser Instanz gemeinsam verwendet. Reset und Neustart beenden ihre Demo-Sitzungen. Browserlokale Designs werden dabei nicht gelöscht.</p>
    </Card>}
  </div>
}
