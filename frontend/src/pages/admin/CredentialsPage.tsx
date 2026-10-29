import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Badge, Button, Card, Empty, Field, Loading, Modal, Notice, PageHeader } from '../../components/ui'
import type { SshProfile, SshStore, SshUse } from '../../credentials'

const initialStore={base_url:'',namespace:'',kv_mount:'kv',auth_mount:'semaphore-ansible'}
const initialProfile={name:'',purpose:'host' as 'host'|'git',login:'',vault_path:'automation-credentials/ssh/',vault_version:1,is_active:true}

export function CredentialsPage(){
  const qc=useQueryClient()
  const store=useQuery({queryKey:['ssh-store'],queryFn:()=>api<SshStore>('/admin/credentials/config')})
  const profiles=useQuery({queryKey:['ssh-profiles'],queryFn:()=>api<SshProfile[]>('/admin/credentials/profiles')})
  const uses=useQuery({queryKey:['ssh-uses'],queryFn:()=>api<SshUse[]>('/admin/credentials/uses')})
  const [form,setForm]=useState(initialStore),[roleId,setRoleId]=useState(''),[secretId,setSecretId]=useState('')
  const [editing,setEditing]=useState<SshProfile|null|undefined>(),[message,setMessage]=useState(''),[error,setError]=useState('')
  useEffect(()=>{if(store.data)setForm({base_url:store.data.base_url||'',namespace:store.data.namespace||'',kv_mount:store.data.kv_mount||'kv',auth_mount:store.data.auth_mount||'semaphore-ansible'})},[store.data])
  const refresh=()=>{void qc.invalidateQueries({queryKey:['ssh-profiles']});void qc.invalidateQueries({queryKey:['ssh-uses']})}
  const fail=(e:Error)=>{setError(e.message);setMessage('')}
  const save=useMutation({mutationFn:()=>api<SshStore>('/admin/credentials/config',{method:'PUT',body:JSON.stringify({...form,role_id:roleId||null,secret_id:secretId||null})}),onSuccess:data=>{qc.setQueryData(['ssh-store'],data);setRoleId('');setSecretId('');setError('');setMessage('Profil-Lesezugang gespeichert.');refresh()},onError:fail})
  const testStore=useMutation({mutationFn:()=>api<{message:string}>('/admin/credentials/test',{method:'POST'}),onSuccess:data=>{setMessage(data.message);setError('')},onError:fail})
  const test=useMutation({mutationFn:(id:string)=>api<SshProfile>(`/admin/credentials/profiles/${id}/test`,{method:'POST'}),onSuccess:()=>{setMessage('Vault-Version und SSH-Schlüssel geprüft. Der öffentliche Schlüssel wird angezeigt; die Freigabe auf dem Ziel bleibt separat.');setError('');refresh()},onError:fail})
  const sync=useMutation({mutationFn:({use,profile}:{use:SshUse;profile:SshProfile})=>api(`/admin/credentials/uses/${use.id}/sync`,{method:'POST',body:JSON.stringify({confirm:true,expected_version:use.vault_version,desired_version:profile.vault_version,profile_revision:profile.revision})}),onSuccess:()=>{setMessage('Schlüssel im ausgewählten Projekt aktualisiert. Zielzugriff anschließend mit einem geeigneten Semaphore-Prüftask kontrollieren.');setError('');refresh()},onError:e=>{fail(e);refresh()}})
  if(store.isLoading||profiles.isLoading||uses.isLoading)return <Loading/>
  return <><PageHeader title="Zugangsprofile" description="Zentrale SSH-Schlüssel aus Vault für neue Tenant-Projekte. Host- und Git-Zugänge werden getrennt zugeordnet."/>
    {(error||store.error||profiles.error||uses.error)&&<Notice type="error">{error||store.error?.message||profiles.error?.message||uses.error?.message}</Notice>}
    {message&&<Notice type="success">{message}</Notice>}
    <Card><h2>Vault-Lesezugang für SSH-Profile</h2><p>Eigene AppRole mit Leserechten auf freigegebene Pfade unter <code>automation-credentials/</code>. Die bestehende Tenant-Schreibrolle bleibt unverändert. Private Schlüssel werden ausschließlich aus Vault gelesen.</p>
      <form onSubmit={e=>{e.preventDefault();save.mutate()}}><div className="form-grid columns-2">
        <Field label="Vault-URL des Schlüsselspeichers"><input type="url" required value={form.base_url} onChange={e=>setForm(v=>({...v,base_url:e.target.value}))}/></Field>
        <Field label="Vault-Namespace (optional)"><input value={form.namespace} onChange={e=>setForm(v=>({...v,namespace:e.target.value}))}/></Field>
        <Field label="KV-v2-Mount für SSH-Profile"><input required value={form.kv_mount} onChange={e=>setForm(v=>({...v,kv_mount:e.target.value}))}/></Field>
        <Field label="AppRole-Auth-Mount"><input required value={form.auth_mount} onChange={e=>setForm(v=>({...v,auth_mount:e.target.value}))}/></Field>
        <Field label="Profil-Lesezugang: Role-ID" help={store.data?.role_id_present?'Hinterlegt; leer lassen zum Beibehalten.':'Noch nicht hinterlegt.'}><input type="password" autoComplete="new-password" value={roleId} onChange={e=>setRoleId(e.target.value)}/></Field>
        <Field label="Profil-Lesezugang: Secret-ID" help={store.data?.secret_id_present?'Hinterlegt; leer lassen zum Beibehalten.':'Noch nicht hinterlegt.'}><input type="password" autoComplete="new-password" value={secretId} onChange={e=>setSecretId(e.target.value)}/></Field>
      </div><div className="button-row"><Button type="submit" loading={save.isPending}>Lesezugang speichern</Button><Button type="button" variant="secondary" disabled={!store.data?.configured} loading={testStore.isPending} onClick={()=>testStore.mutate()}>Gespeicherten Lesezugang testen</Button></div></form>
    </Card>
    <Card><div className="card-heading"><h2>SSH-Profile</h2><Button disabled={!store.data?.configured} onClick={()=>setEditing(null)}>Profil hinzufügen</Button></div>
      <p>Ein Profil kann von mehreren Projekten verwendet werden. Vault-Versionen werden ausdrücklich gewählt. Neue öffentliche Schlüssel zuerst auf den vorgesehenen Servern beziehungsweise in GitLab freigeben.</p>
      <div className="choice-grid">{profiles.data?.map(profile=><div className="card" key={profile.id}><div className="card-heading"><h3>{profile.name}</h3><Badge tone={profile.is_active?'success':'warning'}>{profile.is_active?'Aktiv':'Gesperrt'}</Badge></div>
        <p>{profile.purpose==='host'?'Zielhost-SSH':'Git über SSH'} · Benutzer <code>{profile.login}</code> · Vault-Version {profile.vault_version}</p>
        <p><code>{profile.vault_path}</code></p><p>Freigegebene Ziele: {profile.allowed_targets.join(', ')}</p>
        {profile.fingerprint&&<p>Fingerprint: <code>{profile.fingerprint}</code></p>}
        {profile.public_key&&<Field label={`Öffentlicher Schlüssel: ${profile.name}`} help="Diesen öffentlichen Schlüssel auf dem Ziel freigeben. Der private Schlüssel wird nicht angezeigt."><textarea readOnly rows={3} value={profile.public_key}/></Field>}
        <div className="button-row"><Button variant="secondary" onClick={()=>setEditing(profile)}>Profil bearbeiten</Button><Button variant="secondary" loading={test.isPending&&test.variables===profile.id} onClick={()=>test.mutate(profile.id)}>Profil prüfen</Button></div>
      </div>)}</div>
      {!profiles.data?.length&&<p>Noch keine Profile angelegt. Schlüssel zuerst in Vault hinterlegen und anschließend dessen Pfad und Version zuordnen.</p>}
    </Card>
    <Card><h2>Projektverwendungen und Rotation</h2><p>Die Übernahme einer neuen Vault-Version erfolgt pro Projekt nach Bestätigung. Profiländerungen verteilen keine Schlüssel automatisch. Das Sperren eines Profils widerruft bereits verteilte SSH-Schlüssel auf Zielhosts nicht.</p>
      {uses.data?.length?<div className="table-wrap"><table><thead><tr><th>Profil / Projekt</th><th>Zuordnung</th><th>Version / Status</th><th>Aktion</th></tr></thead><tbody>{uses.data.map(use=>{
        const profile=profiles.data?.find(item=>item.id===use.profile_id)
        return <tr key={use.id}><td>{profile?.name||use.profile_id}<br/><Link to={`/admin/projekte/${use.semaphore_project_id}`}>Projekt #{use.semaphore_project_id}</Link></td>
          <td>{use.bindings.map(binding=><div key={`${binding.kind}:${binding.name}`}>{binding.name}: {binding.targets.join(', ')}</div>)}</td>
          <td>Installiert: {use.vault_version} · Profil: {profile?.vault_version}<br/>{use.status==='installed'?'Übertragen':use.status==='failed'?'Übertragung prüfen':'Ausstehend'}{use.last_error&&<p>{use.last_error}</p>}</td>
          <td><Button variant="secondary" disabled={!profile?.is_active||!profile.fingerprint||sync.isPending||use.status==='installed'&&use.vault_version===profile.vault_version} onClick={()=>{if(profile&&window.confirm(`${profile.name}: Vault-Version ${profile.vault_version} in Projekt #${use.semaphore_project_id} übernehmen? Der zugehörige öffentliche Schlüssel muss auf den Zielen bereits freigegeben sein.`))sync.mutate({use,profile})}}>Version übernehmen</Button></td>
        </tr>})}</tbody></table></div>:<Empty title="Noch keine Projektverwendungen" text="Im Tenant-Assistenten bei Inventories oder Repositories ein SSH-Profil auswählen."/>}
    </Card>
    {editing!==undefined&&<ProfileEditor profile={editing} onClose={()=>setEditing(undefined)} onSaved={()=>{setEditing(undefined);refresh();setMessage('Profil gespeichert. Vor der Verwendung prüfen.');setError('')}}/>}
  </>
}

function ProfileEditor({profile,onClose,onSaved}:{profile:SshProfile|null;onClose:()=>void;onSaved:()=>void}){
  const [form,setForm]=useState(profile?{name:profile.name,purpose:profile.purpose,login:profile.login,vault_path:profile.vault_path,vault_version:profile.vault_version,is_active:profile.is_active}:initialProfile)
  const [targets,setTargets]=useState(profile?.allowed_targets.join('\n')||'')
  const save=useMutation({mutationFn:()=>api(`/admin/credentials/profiles${profile?`/${profile.id}`:''}`,{method:profile?'PUT':'POST',body:JSON.stringify({...form,allowed_targets:targets.split(/\r?\n/).map(v=>v.trim()).filter(Boolean),revision:profile?.revision})}),onSuccess:onSaved})
  return <Modal title={profile?'Zugangsprofil bearbeiten':'Zugangsprofil anlegen'} onClose={onClose}><form onSubmit={e=>{e.preventDefault();save.mutate()}}>
    {save.error&&<Notice type="error">{save.error.message}</Notice>}<div className="form-grid columns-2">
      <Field label="Profilname"><input required minLength={2} maxLength={160} value={form.name} onChange={e=>setForm(v=>({...v,name:e.target.value}))}/></Field>
      <Field label="Verwendungszweck"><select value={form.purpose} onChange={e=>setForm(v=>({...v,purpose:e.target.value as 'host'|'git'}))}><option value="host">SSH zum Zielhost</option><option value="git">Git-Repository über SSH</option></select></Field>
      <Field label="SSH-Benutzer"><input required value={form.login} onChange={e=>setForm(v=>({...v,login:e.target.value}))}/></Field>
      <Field label="Vault-Version"><input type="number" min={1} required value={form.vault_version} onChange={e=>setForm(v=>({...v,vault_version:Number(e.target.value)}))}/></Field>
    </div><Field label="Logischer Vault-Pfad" help="Unter automation-credentials/; ohne KV-Mount und ohne data/. Das Objekt enthält private_key und optional passphrase."><input required value={form.vault_path} onChange={e=>setForm(v=>({...v,vault_path:e.target.value}))}/></Field>
    <Field label="Freigegebene Ziele" help={form.purpose==='host'?'Ein konkreter DNS-Name oder eine IP je Zeile. Verwendet das Inventory ansible_host, dessen Wert eintragen.':'Eine vollständige SSH-Repository-URL je Zeile, z. B. git@git.example:gruppe/projekt.git.'}><textarea required rows={4} value={targets} onChange={e=>setTargets(e.target.value)}/></Field>
    <label className="toggle-row"><input type="checkbox" checked={form.is_active} onChange={e=>setForm(v=>({...v,is_active:e.target.checked}))}/><span>Profil für neue Zuordnungen und Aktualisierungen aktivieren</span></label>
    <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Abbrechen</Button><Button type="submit" loading={save.isPending}>Profil speichern</Button></div>
  </form></Modal>
}
