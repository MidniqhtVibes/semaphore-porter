import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Button, Card, Field, Loading, Notice, PageHeader } from '../../components/ui'
import type { VaultCatalog, VaultConfig } from '../../vault'

const credentialLabels:Record<string,string> = {
  writer_role_id:'Schreibzugang: Role-ID',writer_secret_id:'Schreibzugang: Secret-ID',
  reader_role_id:'Semaphore-Lesezugang: Role-ID',reader_secret_id:'Semaphore-Lesezugang: Secret-ID',
}
const defaults={enabled:false,base_url:'',namespace:'',kv_mount:'kv',tenant_root:'semaphore/tenants',writer_auth_mount:'approle',reader_auth_mount:'semaphore-ansible'}

export function VaultPage(){
  const qc=useQueryClient()
  const query=useQuery({queryKey:['vault-config'],queryFn:()=>api<VaultConfig>('/admin/vault')})
  const catalog=useQuery({queryKey:['vault-catalog'],queryFn:()=>api<VaultCatalog>('/admin/vault/catalog')})
  const [form,setForm]=useState(defaults),[credentials,setCredentials]=useState<Record<string,string>>({})
  const [registry,setRegistry]=useState<Record<string,string>>({}),[message,setMessage]=useState(''),[error,setError]=useState('')
  useEffect(()=>{if(query.data)setForm({...defaults,...Object.fromEntries(Object.keys(defaults).filter(k=>k in query.data!).map(k=>[k,query.data![k as keyof VaultConfig]]))})},[query.data])
  const save=useMutation({mutationFn:()=>api<VaultConfig>('/admin/vault',{method:'PUT',body:JSON.stringify({...form,...credentials,registry_passwords:registry})}),
    onSuccess:()=>{setCredentials({});setRegistry({});setError('');setMessage('Vault-Konfiguration gespeichert.');void qc.invalidateQueries({queryKey:['vault-config']})},onError:(e:Error)=>{setError(e.message);setMessage('')}})
  const test=useMutation({mutationFn:()=>api<{message:string}>('/admin/vault/test',{method:'POST'}),onSuccess:data=>{setMessage(data.message);setError('')},onError:(e:Error)=>{setError(e.message);setMessage('')}})
  if(query.isLoading||catalog.isLoading)return <Loading/>
  const labels:Record<keyof Omit<typeof defaults,'enabled'>,string>={base_url:'Vault Server-URL',namespace:'Vault Namespace (optional)',kv_mount:'KV-v2-Mount',tenant_root:'Tenantwurzel',writer_auth_mount:'Auth-Mount des Schreibzugangs',reader_auth_mount:'Auth-Mount des Semaphore-Lesezugangs'}
  return <><PageHeader title="Vault" description="Zentrale Zugänge und Registry-Passwörter für neue Tenant-Projekte."/>
    {(error||query.error||catalog.error)&&<Notice type="error">{error||query.error?.message||catalog.error?.message}</Notice>}
    {message&&<Notice type="success">{message}</Notice>}
    <Card><h2>Verbindung und Pfade</h2><div className="form-grid columns-2">
      {(Object.entries(labels) as Array<[keyof typeof labels,string]>).map(([key,label])=><Field key={key} label={label}><input value={form[key]} onChange={e=>setForm(v=>({...v,[key]:e.target.value}))}/></Field>)}
    </div><label className="toggle-row"><input type="checkbox" checked={form.enabled} onChange={e=>setForm(v=>({...v,enabled:e.target.checked}))}/><span>Vault-Anlage im Tenant-Assistenten anbieten</span></label></Card>
    <Card><h2>AppRole-Zugänge</h2><p>Den vorhandenen Semaphore-Lesezugang einmalig hinterlegen. Neue Tenants erhalten diesen Zugang als geschützte Variablen. Die Schreib-AppRole dient ausschließlich dem Porter.</p><div className="form-grid columns-2">
      {Object.entries(credentialLabels).map(([key,label])=><Field key={key} label={label} help={query.data?.credentials_present?.[key]?'Hinterlegt; ein leeres Feld behält den bisherigen Wert.':'Noch nicht hinterlegt.'}><input type="password" autoComplete="new-password" value={credentials[key]||''} onChange={e=>setCredentials(v=>({...v,[key]:e.target.value}))}/></Field>)}
    </div></Card>
    <Card><h2>Registry-Zugang pro Anwendung</h2><p>Gültiges Passwort oder Token eintragen. Host, Benutzer und Image-Angaben bleiben in den Projektvariablen.</p><div className="form-grid columns-2">
      {Object.entries(catalog.data?.applications||{}).map(([id,app])=><Field key={id} label={`${app.display_name}: Registry-Passwort`} help={query.data?.registry_configured?.[id]?'Hinterlegt; leer lassen zum Beibehalten.':'Noch nicht hinterlegt.'}><input type="password" autoComplete="new-password" value={registry[id]||''} onChange={e=>setRegistry(v=>({...v,[id]:e.target.value}))}/></Field>)}
    </div></Card>
    <div className="button-row"><Button loading={save.isPending} onClick={()=>save.mutate()}>Konfiguration speichern</Button><Button variant="secondary" loading={test.isPending} disabled={!query.data?.configured} onClick={()=>test.mutate()}>Gespeicherten Schreibzugang testen</Button><Link to="/admin/tenant-erstellen">Tenant erstellen</Link></div>
    <Card><h2>Unterstützte Anwendungen</h2><p>Der Katalog folgt den freigegebenen Kombinationen des Deployment-Stacks.</p><ul>{Object.entries(catalog.data?.applications||{}).map(([id,app])=><li key={id}>{app.display_name}: {Object.keys(app.database_types).join(', ')}</li>)}</ul><small>Stack-Revision: {catalog.data?.source_revision}</small></Card>
  </>
}
