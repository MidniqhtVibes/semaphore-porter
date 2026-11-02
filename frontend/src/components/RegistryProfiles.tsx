import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Button, Field, Loading, Modal, Notice } from './ui'
import type { RegistryBinding, RegistryProfile } from '../registries'
import type { VaultCatalog, VaultConfig } from '../vault'

export function RegistryProfileForm({profile,application,onClose,onSaved,variableHints=[]}:{profile?:RegistryProfile;application?:string;onClose:()=>void;onSaved:(value:RegistryProfile)=>void;variableHints?:string[]}){
  const catalog=useQuery({queryKey:['vault-catalog'],queryFn:()=>api<VaultCatalog>('/admin/vault/catalog')})
  const vault=useQuery({queryKey:['vault-config'],queryFn:()=>api<VaultConfig>('/admin/vault')})
  const hintId=useId()
  const [form,setForm]=useState({name:profile?.name||'',application_id:profile?.application_id||application||'',host:profile?.host||'',username:profile?.username||'',
    host_variable:profile?.host_variable||catalog.data?.applications[application||'']?.registry?.host_variable||'',
    username_variable:profile?.username_variable||catalog.data?.applications[application||'']?.registry?.username_variable||'',
    source:profile?.source||'stored' as 'stored'|'vault'|'legacy',password:'',vault_path:profile?.vault_path||'',vault_version:profile?.vault_version||1,vault_field:profile?.vault_field||'registry_password',is_active:profile?.is_active??true})
  const mutation=useMutation({mutationFn:()=>api<RegistryProfile>(`/admin/registries/profiles${profile?`/${profile.id}`:''}`,{method:profile?'PUT':'POST',body:JSON.stringify({...form,
    password:form.source==='stored'&&form.password?form.password:null,vault_path:form.source==='vault'?form.vault_path:null,vault_version:form.source==='vault'?form.vault_version:null,vault_field:form.source==='vault'?form.vault_field:null,revision:profile?.revision})}),onSuccess:onSaved})
  const chooseApp=(application_id:string)=>{
    const contract=catalog.data?.applications[application_id]?.registry
    setForm(value=>({...value,application_id,host_variable:contract?.host_variable||'',username_variable:contract?.username_variable||'',password:''}))
  }
  const available=Object.entries(catalog.data?.applications||{}).filter(([,app])=>app.fields?.some(field=>field.source==='registry'))
  return <Modal title={profile?'Registry-Profil bearbeiten':'Registry-Zugang anlegen'} onClose={onClose}><form onSubmit={event=>{event.preventDefault();mutation.mutate()}}>
    {mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}{catalog.error&&<Notice type="error">{catalog.error.message}</Notice>}
    <Notice>Dieses Profil wird sofort gespeichert. Neue Tenant-Secrets werden erst mit „Projekt verbindlich erstellen“ in Vault angelegt. Es wird kein Registry-Dienst, Benutzer oder Token beim Registry-Anbieter erzeugt.</Notice>
    <div className="form-grid columns-2"><Field label="Profilname"><input required minLength={2} maxLength={160} value={form.name} onChange={event=>setForm({...form,name:event.target.value})}/></Field>
    <Field label="Anwendung"><select required disabled={Boolean(application)} value={form.application_id} onChange={event=>chooseApp(event.target.value)}><option value="">Bitte wählen</option>{available.map(([id,app])=><option value={id} key={id}>{app.display_name}</option>)}</select></Field>
    <Field label="Registry-Host mit optionalem Port" help="Ohne https:// und Repository-Pfad; muss zur festen Registry der Anwendung passen."><input required maxLength={255} value={form.host} placeholder="registry.example.internal:5000" onChange={event=>setForm({...form,host:event.target.value})}/></Field>
    <Field label="Registry-Benutzer"><input required maxLength={255} autoComplete="off" value={form.username} onChange={event=>setForm({...form,username:event.target.value})}/></Field></div>
    <Field label="Quelle des Registry-Zugangs"><select value={form.source} onChange={event=>setForm({...form,source:event.target.value as typeof form.source,password:''})}><option value="stored">Passwort/Token verschlüsselt in Semaporter</option><option value="vault">Bestehende Vault-Version referenzieren</option>{vault.data?.registry_configured?.[form.application_id]&&<option value="legacy">Bisherigen Zugang aus den Vault-Einstellungen übernehmen</option>}</select></Field>
    {form.source==='stored'&&<Field label="Registry-Passwort / Pull-Token" help={profile?.password_present?'Leer erhält den gespeicherten Wert nur bei gleicher Anwendung, Host und Benutzer.':'Bestehenden gültigen Zugang eintragen; Semaporter kann ihn nicht beim Anbieter generieren.'}><input type="password" required={!profile?.password_present} autoComplete="new-password" value={form.password} maxLength={4096} onChange={event=>setForm({...form,password:event.target.value})}/></Field>}
    {form.source==='vault'&&<><Notice>Der separate Registry-Vault-Leser muss unter Registry-Zugänge konfiguriert sein. In diesem Profil bleibt nur die Referenz gespeichert.</Notice><div className="form-grid columns-2"><Field label="Vault-Secret-Pfad" help="Relativ zum KV-v2-Mount des Registry-Lesezugangs, ohne /data/."><input required maxLength={500} value={form.vault_path} onChange={event=>setForm({...form,vault_path:event.target.value})}/></Field><Field label="Vault-Version"><input required type="number" min={1} step={1} value={form.vault_version} onChange={event=>setForm({...form,vault_version:Number(event.target.value)})}/></Field><Field label="Vault-Feld für Passwort / Token"><input required maxLength={100} value={form.vault_field} onChange={event=>setForm({...form,vault_field:event.target.value})}/></Field></div></>}
    <fieldset className="registry-mapping"><legend>Zuordnung zur Anwendung</legend><p className="account-note">Namen der öffentlichen Host- und Benutzer-Variablen aus dem Stack/der Projektvorlage übernehmen. Ein neuer Katalog füllt diese aus; ältere Vorlagen benötigen die explizite Zuordnung.</p><datalist id={hintId}>{variableHints.filter(value=>value.toLowerCase().includes('registry')).map(value=><option value={value} key={value}/>)}</datalist><div className="form-grid columns-2"><Field label="Projektvariable für Registry-Host"><input required list={hintId} maxLength={160} value={form.host_variable} placeholder="z. B. anwendung_registry_host" onChange={event=>setForm({...form,host_variable:event.target.value})}/></Field><Field label="Projektvariable für Registry-Benutzer"><input required list={hintId} maxLength={160} value={form.username_variable} placeholder="z. B. anwendung_registry_username" onChange={event=>setForm({...form,username_variable:event.target.value})}/></Field></div></fieldset>
    <label className="toggle-row"><input type="checkbox" checked={form.is_active} onChange={event=>setForm({...form,is_active:event.target.checked})}/><span>Für neue Zuordnungen freigeben</span></label>
    <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Abbrechen</Button><Button type="submit" loading={mutation.isPending}>{profile?'Profil speichern':application?'Profil anlegen & verwenden':'Profil anlegen'}</Button></div>
  </form></Modal>
}

export function RegistryProfilesWizard({applications,bindings,onChange,legacy,templateId,overrides}:{applications:string[];bindings:RegistryBinding;onChange:(value:RegistryBinding)=>void;legacy?:Record<string,boolean>;templateId:string;overrides?:{environments:Array<Record<string,unknown>>}}){
  const qc=useQueryClient(),[newFor,setNewFor]=useState('')
  const profiles=useQuery({queryKey:['registry-profiles'],queryFn:()=>api<RegistryProfile[]>('/admin/registries/profiles')})
  const catalog=useQuery({queryKey:['vault-catalog'],queryFn:()=>api<VaultCatalog>('/admin/vault/catalog')})
  const resources=useQuery({queryKey:['registry-template',templateId],queryFn:()=>api<{environments:Array<Record<string,unknown>>}>(`/admin/project-templates/${templateId}/resources`),enabled:Boolean(templateId)})
  const needed=applications.filter(id=>catalog.data?.applications[id]?.fields?.some(field=>field.source==='registry'))
  const groups=overrides?.environments||resources.data?.environments||[]
  const hints=[...new Set(groups.flatMap(group=>['json','env'].flatMap(key=>{try{const value=typeof group[key]==='string'?JSON.parse(group[key]):group[key];return value&&typeof value==='object'&&!Array.isArray(value)?Object.keys(value):[]}catch{return[]}})))]
  return <section className="registry-wizard" aria-label="Registry-Zugänge für neue Tenants"><h3>Registry-Zugänge je Anwendung</h3><p>Bestehendes Profil auswählen oder einen neuen Zugang anlegen. Host, Benutzer und Passwort werden bei bestätigter Tenant-Erstellung in dessen Vault-Objekt gespeichert.</p>
    {(profiles.error||catalog.error||resources.error)&&<Notice type="error">{profiles.error?.message||catalog.error?.message||resources.error?.message}</Notice>}
    {profiles.isLoading||catalog.isLoading?<Loading/>:needed.map(id=><div className="registry-choice" key={id}><Field label={`${catalog.data?.applications[id]?.display_name||id}: Registry-Zugang`}><select value={bindings[id]||(legacy?.[id]?'legacy':'')} onChange={event=>{const next={...bindings};if(event.target.value)next[id]=event.target.value;else delete next[id];onChange(next)}}><option value="">Bitte Profil wählen oder neuen Zugang anlegen</option>{legacy?.[id]&&<option value="legacy">Bisheriger Zugang aus Vault-Einstellungen</option>}{profiles.data?.filter(profile=>profile.application_id===id&&(profile.is_active||bindings[id]===profile.id)).map(profile=><option key={profile.id} value={profile.id} disabled={!profile.is_active}>{profile.name} · {profile.host} · {profile.username}{!profile.is_active?' · gesperrt':''}</option>)}</select></Field><Button variant="secondary" onClick={()=>setNewFor(id)}>Neuen Zugang anlegen</Button></div>)}
    {catalog.data&&needed.length===0&&<p className="subtle">Für die Auswahl ist kein Registry-Secret im Katalog vorgesehen.</p>}
    <Link to="/admin/registries">Registry-Profile und Vault-Lesezugang verwalten</Link>
    {newFor&&<RegistryProfileForm application={newFor} variableHints={hints} onClose={()=>setNewFor('')} onSaved={profile=>{onChange({...bindings,[newFor]:profile.id});setNewFor('');void qc.invalidateQueries({queryKey:['registry-profiles']})}}/>}
  </section>
}
