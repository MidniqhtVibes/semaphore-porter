import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Users } from 'lucide-react'
import { api } from '../../api'
import { Badge, Button, Card, Field, Loading, Modal, Notice, PageHeader, formatDate } from '../../components/ui'
import type { User } from '../../types'

type Group = { id: string; name: string; description: string; user_ids: string[] }

export function UsersPage() {
  const qc=useQueryClient(), [newUser,setNewUser]=useState(false), [newGroup,setNewGroup]=useState(false),[editingGroup,setEditingGroup]=useState<Group|null>(null)
  const users=useQuery({queryKey:['admin-users'],queryFn:()=>api<User[]>('/admin/users')})
  const groups=useQuery({queryKey:['admin-groups'],queryFn:()=>api<Group[]>('/admin/groups')})
  if(users.isLoading||groups.isLoading)return <Loading/>
  const refresh=()=>{void qc.invalidateQueries({queryKey:['admin-users']});void qc.invalidateQueries({queryKey:['admin-groups']})}
  return <><PageHeader title="Benutzer & Gruppen" description="Lokale Konten, Rollen und gruppenbasierte Freigaben." actions={<><Button variant="secondary" onClick={()=>setNewGroup(true)}><Users size={16}/>Gruppe</Button><Button onClick={()=>setNewUser(true)}><Plus size={16}/>Benutzer</Button></>}/>
    <div className="tabs"><span className="active">Benutzer <Badge>{users.data?.length||0}</Badge></span><span>Gruppen <Badge>{groups.data?.length||0}</Badge></span></div>
    <Card><div className="table-wrap"><table><thead><tr><th>Benutzer</th><th>Benutzername</th><th>Rollen</th><th>Status</th><th>Letzte Anmeldung</th></tr></thead><tbody>{users.data?.map(user=><UserRow key={user.id} user={user} onSaved={refresh}/>)}</tbody></table></div></Card>
    <div className="section-heading"><h2>Benutzergruppen</h2><p>Gruppen können Tenant- und Task-Rechte erhalten.</p></div><div className="cards-grid">{groups.data?.map(group=><Card key={group.id}><div className="card-heading"><div className="name-cell"><div className="square-icon"><Users size={17}/></div><div><strong>{group.name}</strong><span>{group.description||'Keine Beschreibung'}</span></div></div><Badge>{group.user_ids.length} Mitglieder</Badge></div></Card>)}</div>
    <Card><h2>Gruppenmitgliedschaften</h2>{groups.data?.map(group=><div className="button-row" key={group.id}><span>{group.name} · {group.user_ids.length} Mitglieder</span><Button variant="secondary" onClick={()=>setEditingGroup(group)}>Mitglieder bearbeiten</Button></div>)}</Card>
    {editingGroup&&<GroupMembers group={editingGroup} users={users.data||[]} onClose={()=>setEditingGroup(null)} onSaved={()=>{setEditingGroup(null);refresh()}}/>}
    {newUser&&<NewUserModal onClose={()=>setNewUser(false)} onSaved={()=>{setNewUser(false);refresh()}}/>}{newGroup&&<NewGroupModal onClose={()=>setNewGroup(false)} onSaved={()=>{setNewGroup(false);refresh()}}/>}
  </>
}

function GroupMembers({group,users,onClose,onSaved}:{group:Group;users:User[];onClose:()=>void;onSaved:()=>void}){
  const [ids,setIds]=useState(group.user_ids)
  const mutation=useMutation({mutationFn:()=>api(`/admin/groups/${group.id}/members`,{method:'PUT',body:JSON.stringify({user_ids:ids})}),onSuccess:onSaved})
  return <Modal title={`Mitglieder · ${group.name}`} onClose={onClose}>{mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}<div className="check-grid">{users.map(user=><label key={user.id}><input type="checkbox" checked={ids.includes(user.id)} onChange={e=>setIds(current=>e.target.checked?[...current,user.id]:current.filter(id=>id!==user.id))}/>{user.display_name}</label>)}</div><Button loading={mutation.isPending} onClick={()=>mutation.mutate()}>Mitglieder speichern</Button></Modal>
}

function UserRow({user,onSaved}:{user:User;onSaved:()=>void}){
  const [open,setOpen]=useState(false),[editingUsername,setEditingUsername]=useState(false),[error,setError]=useState('')
  const toggle=useMutation({mutationFn:()=>api(`/admin/users/${user.id}`,{method:'PATCH',body:JSON.stringify({is_active:!user.is_active}),headers:{'Content-Type':'application/json'}}),onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  const reset=useMutation({mutationFn:(password:string)=>api(`/admin/users/${user.id}/reset-password`,{method:'POST',body:JSON.stringify({password,must_change_password:true}),headers:{'Content-Type':'application/json'}}),onSuccess:()=>setOpen(false),onError:(e:Error)=>setError(e.message)})
  return <tr><td><div className="name-cell"><div className="avatar small">{user.display_name.slice(0,2).toUpperCase()}</div><div><strong>{user.display_name}</strong><span>{user.email}</span></div></div></td><td>{user.username||'Nicht vergeben'} <button className="text-button" aria-label={`Benutzername ändern · ${user.display_name}`} onClick={()=>setEditingUsername(true)}>Ändern</button>{editingUsername&&<UsernameModal user={user} onClose={()=>setEditingUsername(false)} onSaved={()=>{setEditingUsername(false);onSaved()}}/>}</td><td><div className="badge-row">{user.roles.map(role=><Badge key={role} tone={role==='system_admin'?'info':'neutral'}>{role}</Badge>)}</div></td><td><button className="status-button" onClick={()=>toggle.mutate()}>{user.is_active?<Badge tone="success">Aktiv</Badge>:<Badge tone="danger">Deaktiviert</Badge>}</button></td><td>{formatDate(user.last_login_at)} <button className="text-button" onClick={()=>setOpen(true)}>Passwort</button>{open&&<PasswordModal name={user.display_name} error={error} onClose={()=>setOpen(false)} onSave={value=>reset.mutate(value)} loading={reset.isPending}/>}</td></tr>
}

const usernamePattern=/^[a-z0-9][a-z0-9._-]{1,63}$/i
const usernameHelp='2–64 Zeichen: Buchstaben (a–z), Ziffern, Punkt, Bindestrich oder Unterstrich. Beginn mit Buchstabe oder Ziffer. Groß-/Kleinschreibung spielt keine Rolle.'

function UsernameModal({user,onClose,onSaved}:{user:User;onClose:()=>void;onSaved:()=>void}){
  const [username,setUsername]=useState(user.username||'')
  const mutation=useMutation({mutationFn:()=>api(`/admin/users/${user.id}`,{method:'PATCH',body:JSON.stringify({username:username.trim()})}),onSuccess:onSaved})
  return <Modal title={`Benutzername ändern · ${user.display_name}`} onClose={onClose}>{mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}<Field label="Benutzername" help={usernameHelp}><input autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={64} value={username} onChange={e=>setUsername(e.target.value)}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} disabled={!usernamePattern.test(username.trim())} onClick={()=>mutation.mutate()}>Benutzername speichern</Button></div></Modal>
}

function NewUserModal({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}){
  const [email,setEmail]=useState(''),[username,setUsername]=useState(''),[name,setName]=useState(''),[password,setPassword]=useState(''),[role,setRole]=useState('viewer'),[error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>api('/admin/users',{method:'POST',body:JSON.stringify({email,username:username.trim()||undefined,display_name:name,password,role_codes:[role],must_change_password:true}),headers:{'Content-Type':'application/json'}}),onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  return <Modal title="Benutzer erstellen" onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<div className="form-grid columns-2"><Field label="Anzeigename"><input value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="E-Mail-Adresse"><input type="email" value={email} onChange={e=>setEmail(e.target.value)}/></Field><Field label="Benutzername (optional)" help={`Leer lassen: automatisch aus der E-Mail-Adresse vergeben. ${usernameHelp}`}><input autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={64} value={username} onChange={e=>setUsername(e.target.value)}/></Field><Field label="Initiales Passwort" help="Mindestens 12 Zeichen; Änderung beim ersten Login erforderlich."><input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></Field><Field label="Portalrolle"><select value={role} onChange={e=>setRole(e.target.value)}><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="tenant_admin">Tenant Admin</option><option value="system_admin">System Admin</option></select></Field></div><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>mutation.mutate()} disabled={!email||!name||password.length<12||Boolean(username.trim()&&!usernamePattern.test(username.trim()))}>Erstellen</Button></div></Modal>
}

function NewGroupModal({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}){
  const [name,setName]=useState(''),[description,setDescription]=useState(''),[error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>api('/admin/groups',{method:'POST',body:JSON.stringify({name,description}),headers:{'Content-Type':'application/json'}}),onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  return <Modal title="Gruppe erstellen" onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<Field label="Gruppenname"><input value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Beschreibung"><textarea value={description} onChange={e=>setDescription(e.target.value)}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>mutation.mutate()} disabled={name.length<2}>Erstellen</Button></div></Modal>
}

function PasswordModal({name,error,onClose,onSave,loading}:{name:string;error:string;onClose:()=>void;onSave:(value:string)=>void;loading:boolean}){
  const [password,setPassword]=useState('')
  return <Modal title={`Passwort zurücksetzen · ${name}`} onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<Field label="Neues temporäres Passwort"><input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={loading} disabled={password.length<12} onClick={()=>onSave(password)}>Zurücksetzen</Button></div></Modal>
}

