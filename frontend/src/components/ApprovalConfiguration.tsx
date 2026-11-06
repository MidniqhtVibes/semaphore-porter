import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import type { ApprovalClass, ApprovalConfig, Tenant, User } from '../types'
import { Button, Card, Field, Notice } from './ui'

export const classLabels: Record<ApprovalClass,string> = {low:'Niedrig',medium:'Mittel',high:'Hoch'}
export const defaultApprovalConfig: ApprovalConfig = {enabled:false,approver_id:null,threshold:'high',notify_by_email:false}

export function ClassificationSelect({label,value,onChange}: {label:string;value:ApprovalClass|'';onChange:(value:ApprovalClass)=>void}) {
  return <Field label={label}><select value={value} onChange={event=>onChange(event.target.value as ApprovalClass)}>
    <option value="" disabled>Bitte einstufen …</option>
    {Object.entries(classLabels).map(([id,name])=><option key={id} value={id}>{name}</option>)}
  </select></Field>
}

export function ApprovalFields({value,onChange,users}: {value:ApprovalConfig;onChange:(value:ApprovalConfig)=>void;users:User[]}) {
  const settings=useQuery({queryKey:['approval-settings'],queryFn:()=>api<{notifications_available:boolean}>('/admin/approval-settings')})
  const available=settings.data?.notifications_available
  return <div className="approval-configuration"><label className="toggle-row"><input type="checkbox" checked={value.enabled}
    onChange={event=>onChange({...value,enabled:event.target.checked})}/><span><strong>Genehmigung für Taskstarts aktivieren</strong><small>Einmalige Freigabe durch einen zugeordneten Vorgesetzten, sobald Kosten oder Aufwand die Grenze erreichen.</small></span></label>
    {value.enabled&&<><div className="form-grid columns-2"><Field label="Vorgesetzter / Genehmiger"><select value={value.approver_id||''}
      onChange={event=>onChange({...value,approver_id:event.target.value||null})}><option value="">Bitte wählen …</option>
      {users.filter(user=>user.is_active).map(user=><option key={user.id} value={user.id}>{user.display_name} · {user.email}</option>)}
    </select></Field><ClassificationSelect label="Genehmigung erforderlich ab" value={value.threshold} onChange={threshold=>onChange({...value,threshold})}/></div>
    <p className="muted">Kosten und Aufwand werden pro Task administrativ eingestuft. Selbstfreigaben sind gesperrt. Nach Zustimmung startet der Antragsteller die unveränderte Anfrage einmalig selbst. Anfragen gelten 24 Stunden.</p>
    <label className="toggle-row"><input type="checkbox" checked={value.notify_by_email} disabled={!available&&!value.notify_by_email}
      onChange={event=>onChange({...value,notify_by_email:event.target.checked})}/><span>Zusätzlich per Mail benachrichtigen<small>{available?'Mail enthält einen Link; die Entscheidung erfolgt angemeldet in Semaporter.':'Optionaler SMTP-Versand ist im Backend noch nicht eingerichtet. Freigaben funktionieren direkt in Semaporter.'}</small></span></label></>}
  </div>
}

export function TenantApprovalSettings({tenant,users}: {tenant:Tenant;users:User[]}) {
  const qc=useQueryClient(),[value,setValue]=useState<ApprovalConfig>({...defaultApprovalConfig,...tenant.approval_config})
  const save=useMutation({mutationFn:()=>api<ApprovalConfig>(`/admin/tenants/${tenant.id}/approval-config`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)}),
    onSuccess:config=>{setValue(config);void qc.invalidateQueries({queryKey:['admin-tenant',tenant.id]})}})
  return <Card><h2>Genehmigungsworkflow</h2><ApprovalFields value={value} onChange={setValue} users={users}/>
    {save.error&&<Notice type="error">{save.error.message}</Notice>}{save.isSuccess&&<Notice type="success">Genehmigungsregeln gespeichert. Frühere Anfragen müssen bei geänderter Konfiguration neu beantragt werden.</Notice>}
    <Button variant="secondary" loading={save.isPending} disabled={value.enabled&&!value.approver_id} onClick={()=>save.mutate()}>Genehmigungsregeln speichern</Button></Card>
}
