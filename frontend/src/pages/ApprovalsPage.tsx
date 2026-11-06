import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import type { ApprovalClass, TaskRun } from '../types'
import { classLabels } from '../components/ApprovalConfiguration'
import { Badge, Button, Card, Empty, Field, Loading, Notice, PageHeader, formatDate } from '../components/ui'

type Approval = {id:string;tenant:string;task:string;requester:string;approver:string;status:string;reason:string;decision_note:string;
  cost_class:ApprovalClass;effort_class:ApprovalClass;variables:Record<string,unknown>;notification_status:string;
  created_at:string;expires_at:string;run_id:string|null;can_decide:boolean;can_start:boolean;can_cancel:boolean;can_resolve:boolean}
const labels:Record<string,string>={pending:'Wartet auf Entscheidung',approved:'Genehmigt',rejected:'Abgelehnt',cancelled:'Zurückgezogen',expired:'Abgelaufen',executing:'Start wird abgeglichen',executed:'Ausgeführt',uncertain:'Start unklar',closed:'Manuell geschlossen'}

export default function ApprovalsPage(){
  const [params]=useSearchParams(), selected=params.get('anfrage')
  const query=useQuery({queryKey:['approvals',selected],queryFn:()=>selected?api<Approval>(`/portal/approvals/${selected}`).then(row=>[row]):api<Approval[]>('/portal/approvals'),refetchInterval:10_000})
  return <><PageHeader title="Task-Genehmigungen" description="Eigene Anträge und zugewiesene Entscheidungen. Eine Zustimmung startet noch keinen Task."/>
    {selected&&<Link className="row-link" to="?">Alle Anfragen anzeigen</Link>}
    {query.isLoading?<Loading/>:query.error?<Notice type="error">{query.error.message}</Notice>:query.data?.length?
    <div className="approval-list">{query.data.map(row=><ApprovalCard key={row.id} row={row}/>)}</div>:
    <Empty title="Keine Genehmigungsanfragen" text="Genehmigungspflichtige Tasks werden über ihr Startformular beantragt. Als zugeordneter Vorgesetzter erscheinen Anträge hier."/>}</>
}

function ApprovalCard({row}: {row:Approval}) {
  const qc=useQueryClient(), navigate=useNavigate(),[note,setNote]=useState(''),[confirmed,setConfirmed]=useState(false)
  const refresh=()=>void qc.invalidateQueries({queryKey:['approvals']})
  const action=useMutation({mutationFn:({route,body}:{route:string;body?:unknown})=>api(`/portal/approvals/${row.id}/${route}`,{method:'POST',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined}),onSuccess:refresh})
  const start=useMutation({mutationFn:()=>api<TaskRun>(`/portal/approvals/${row.id}/start`,{method:'POST'}),onSuccess:run=>navigate(`/portal/runs/${run.id}`),onError:refresh})
  const resolve=useMutation({mutationFn:()=>api(`/admin/approvals/${row.id}/resolve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed_remote_checked:confirmed})}),onSuccess:refresh})
  const busy=action.isPending||start.isPending||resolve.isPending
  return <Card className="approval-request"><div className="card-heading"><div><h2>{row.task}</h2><p>{row.tenant}</p></div>
    <Badge tone={row.status==='approved'?'success':row.status==='rejected'||row.status==='uncertain'?'danger':row.status==='pending'?'warning':'neutral'}>{labels[row.status]||row.status}</Badge></div>
    <div className="badge-row"><Badge>Kosten: {classLabels[row.cost_class]}</Badge><Badge>Aufwand: {classLabels[row.effort_class]}</Badge></div>
    <dl className="detail-list"><div><dt>Antragsteller</dt><dd>{row.requester}</dd></div><div><dt>Vorgesetzter</dt><dd>{row.approver}</dd></div><div><dt>Beantragt</dt><dd>{formatDate(row.created_at)}</dd></div><div><dt>Gültig bis</dt><dd>{formatDate(row.expires_at)}</dd></div></dl>
    <p className="approval-reason">{row.reason}</p>
    <details><summary>Beantragte Parameter</summary><pre className="json-preview">{JSON.stringify(row.variables,null,2)}</pre></details>
    {row.decision_note&&<Notice>{row.decision_note}</Notice>}
    {['failed','unavailable'].includes(row.notification_status)&&<Notice>Der Mail-Hinweis konnte nicht zugestellt werden. Die Anfrage ist hier verfügbar.</Notice>}
    {['uncertain','executing'].includes(row.status)&&<Notice type="error">Der Start wurde bereits versucht. Vor einem weiteren Antrag den Zustand in Semaphore prüfen; diese Freigabe wird nicht erneut ausgeführt.</Notice>}
    {[action.error,start.error,resolve.error].filter(Boolean).map((error,index)=><Notice key={index} type="error">{error?.message}</Notice>)}
    {row.can_decide&&<Field label="Kommentar zur Entscheidung (optional)"><textarea rows={2} maxLength={2000} value={note} onChange={event=>setNote(event.target.value)}/></Field>}
    {row.can_resolve&&<label className="toggle-row"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/><span>Ich habe als Systemadmin den tatsächlichen Taskzustand in Semaphore geprüft. Anfrage schließen, ohne erneut zu starten.</span></label>}
    <div className="button-row">{row.can_decide&&<><Button disabled={busy} onClick={()=>action.mutate({route:'decision',body:{decision:'approved',note}})}>Genehmigen</Button>
      <Button variant="danger" disabled={busy} onClick={()=>action.mutate({route:'decision',body:{decision:'rejected',note}})}>Ablehnen</Button></>}
      {row.can_start&&<Button disabled={busy} loading={start.isPending} onClick={()=>start.mutate()}>Genehmigten Task einmalig starten</Button>}
      {row.can_cancel&&<Button variant="secondary" disabled={busy} onClick={()=>action.mutate({route:'cancel'})}>Anfrage zurückziehen</Button>}
      {row.can_resolve&&<Button variant="secondary" disabled={busy||!confirmed} onClick={()=>resolve.mutate()}>Geprüfte Anfrage schließen</Button>}
      {row.run_id&&<Link className="button button-secondary" to={`/portal/runs/${row.run_id}`}>Task-Ausführung öffnen</Link>}</div>
  </Card>
}
