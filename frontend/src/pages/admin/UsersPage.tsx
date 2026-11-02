import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Plus, Search, ShieldCheck, Tags, UserRound, Users } from 'lucide-react'
import { api } from '../../api'
import { Badge, Button, Card, Empty, Field, Loading, Modal, Notice, PageHeader, formatDate } from '../../components/ui'
import type { User } from '../../types'
import { ProfileTags } from '../../components/ProfileFields'
import { PersonAvatar } from '../../components/PersonAvatar'

type Color = NonNullable<User['color']>
type Group = { id:string; name:string; description:string; user_ids:string[]; color?:Color; tags?:string[]; is_team?:boolean; responsibilities?:string[]; responsibility_notes?:string }
const colors:Record<Color,string>={slate:'Grau',blue:'Blau',violet:'Violett',green:'Grün',amber:'Bernstein',rose:'Rosa'}
const roles:Record<string,string>={system_admin:'Systemadmin',tenant_admin:'Tenant-Admin',operator:'Operator',viewer:'Viewer'}
const roleNotes:Record<string,string>={system_admin:'Verwaltet das gesamte Portal.',tenant_admin:'Zusätzliche Tenant- und Task-Freigaben bestimmen den Zugriff.',operator:'Start und Abbruch benötigen passende Task-Freigaben.',viewer:'Lesender Zugriff auf freigegebene Bereiche.'}
const usernamePattern=/^[a-z0-9][a-z0-9._-]{1,63}$/i
const usernameHelp='2–64 Zeichen: Buchstaben (a–z), Ziffern, Punkt, Bindestrich oder Unterstrich. Beginn mit Buchstabe oder Ziffer. Groß-/Kleinschreibung spielt keine Rolle.'

function AccountTag({text,color='slate'}:{text:string;color?:Color}){
  return <span className="account-tag" data-color={color}><span aria-hidden="true"/>{text}</span>
}
function AccountTags({item}:{item:{color?:Color;tags?:string[]}}){return <div className="badge-row">{item.tags?.map(tag=><AccountTag key={tag} text={tag} color={item.color}/>)}</div>}
function RoleTags({user}:{user:User}){return <div className="badge-row">{user.roles.map(role=><Badge key={role} tone={role==='system_admin'?'info':role==='operator'?'success':'neutral'}>{roles[role]||role}</Badge>)}</div>}

export function UsersPage(){
  const qc=useQueryClient()
  const [mode,setMode]=useState<'users'|'groups'>('users'),[search,setSearch]=useState(''),[status,setStatus]=useState(''),[role,setRole]=useState(''),[tag,setTag]=useState('')
  const [userId,setUserId]=useState(''),[groupId,setGroupId]=useState(''),[newUser,setNewUser]=useState(false),[newGroup,setNewGroup]=useState(false)
  const [members,setMembers]=useState<Group|null>(null),[labelTarget,setLabelTarget]=useState<{kind:'users'|'groups';item:User|Group}|null>(null)
  const users=useQuery({queryKey:['admin-users'],queryFn:()=>api<User[]>('/admin/users')})
  const groups=useQuery({queryKey:['admin-groups'],queryFn:()=>api<Group[]>('/admin/groups')})
  const refresh=()=>{for(const key of ['admin-users','admin-groups','person-profile','profile-directory','profile-teams','team-people'])void qc.invalidateQueries({queryKey:[key]})}
  const switchMode=(next:'users'|'groups')=>{setMode(next);setSearch('');setTag('')}
  const openUser=(id:string)=>{switchMode('users');setStatus('');setRole('');setUserId(id)}
  const openGroup=(id:string)=>{switchMode('groups');setGroupId(id)}
  if(users.isLoading||groups.isLoading)return <Loading/>
  if(users.isError||groups.isError)return <><PageHeader title="Benutzer & Gruppen"/><Notice type="error">Benutzerverwaltung konnte nicht geladen werden: {users.error?.message||groups.error?.message}</Notice><Button variant="secondary" onClick={refresh}>Erneut laden</Button></>
  const allUsers=users.data||[],allGroups=groups.data||[],needle=search.trim().toLocaleLowerCase('de')
  const availableTags=[...new Set((mode==='users'?allUsers:allGroups).flatMap(item=>item.tags||[]))].sort((a,b)=>a.localeCompare(b,'de'))
  const activeTag=availableTags.includes(tag)?tag:''
  const matches=(values:Array<string|undefined>)=>values.filter(Boolean).join(' ').toLocaleLowerCase('de').includes(needle)
  const visibleUsers=allUsers.filter(item=>matches([item.display_name,item.username||'',item.email,...(item.tags||[])])&&(!status||(status==='active'?item.is_active:!item.is_active))&&(!role||item.roles.includes(role))&&(!activeTag||item.tags?.includes(activeTag)))
  const visibleGroups=allGroups.filter(item=>matches([item.name,item.description,...(item.tags||[])])&&(!activeTag||item.tags?.includes(activeTag)))
  const selectedUser=visibleUsers.find(item=>item.id===userId)||visibleUsers[0],selectedGroup=visibleGroups.find(item=>item.id===groupId)||visibleGroups[0]
  return <>
    <PageHeader title="Benutzer & Gruppen" description="Konten, Mitgliedschaften und Kennzeichnungen an einem Ort." actions={<><Button variant="secondary" onClick={()=>setNewGroup(true)}><Users size={16}/>Gruppe erstellen</Button><Button onClick={()=>setNewUser(true)}><Plus size={16}/>Benutzer erstellen</Button></>}/>
    <div className="account-summary" aria-label="Übersicht">
      <Card><UserRound size={19}/><div><strong>{allUsers.length}</strong><span>Benutzerkonten</span></div></Card>
      <Card><ShieldCheck size={19}/><div><strong>{allUsers.filter(item=>item.is_active).length}</strong><span>Aktive Konten</span></div></Card>
      <Card><Users size={19}/><div><strong>{allGroups.length}</strong><span>Benutzergruppen</span></div></Card>
    </div>
    <div className="account-workspace">
      <Card className="account-directory">
        <div className="account-switch" aria-label="Verwaltungsbereich">
          <button type="button" aria-pressed={mode==='users'} onClick={()=>switchMode('users')}><UserRound size={16}/>Benutzer</button>
          <button type="button" aria-pressed={mode==='groups'} onClick={()=>switchMode('groups')}><Users size={16}/>Gruppen</button>
        </div>
        <Field label={mode==='users'?'Benutzer suchen':'Gruppen suchen'}><div className="input-icon"><Search size={16}/><input value={search} onChange={event=>setSearch(event.target.value)} placeholder={mode==='users'?'Name, E-Mail, Benutzername, Tag …':'Name, Beschreibung, Tag …'}/></div></Field>
        {mode==='users'&&<div className="account-filters"><Field label="Status filtern"><select value={status} onChange={event=>setStatus(event.target.value)}><option value="">Jeder Status</option><option value="active">Aktiv</option><option value="inactive">Deaktiviert</option></select></Field><Field label="Rolle filtern"><select value={role} onChange={event=>setRole(event.target.value)}><option value="">Alle Rollen</option>{Object.entries(roles).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Field></div>}
        <Field label="Nach Tag filtern"><select value={activeTag} onChange={event=>setTag(event.target.value)}><option value="">Alle Tags</option>{availableTags.map(value=><option key={value}>{value}</option>)}</select></Field>
        <div className="section-heading"><h2>{mode==='users'?'Konten':'Gruppen'}</h2><span>{mode==='users'?visibleUsers.length:visibleGroups.length} Treffer</span></div>
        <div className="account-list" aria-label={mode==='users'?'Benutzerauswahl':'Gruppenauswahl'}>
          {mode==='users'?visibleUsers.map(item=><button key={item.id} type="button" className="account-choice" aria-label={`Benutzer auswählen: ${item.display_name}`} aria-pressed={item.id===selectedUser?.id} onClick={()=>setUserId(item.id)}>
            <span className="account-avatar" data-color={item.color||'slate'}>{item.display_name.slice(0,2).toUpperCase()}</span><span className="account-choice-copy"><strong>{item.display_name}</strong><span>{item.email}</span><span className="account-mini-tags">{item.tags?.slice(0,2).map(value=><AccountTag key={value} text={value} color={item.color}/>)}</span></span><span className={`account-state ${item.is_active?'is-active':''}`} aria-label={item.is_active?'Aktiv':'Deaktiviert'}/>
          </button>):visibleGroups.map(item=><button key={item.id} type="button" className="account-choice" aria-label={`Gruppe auswählen: ${item.name}`} aria-pressed={item.id===selectedGroup?.id} onClick={()=>setGroupId(item.id)}><span className="account-avatar" data-color={item.color||'slate'}><Users size={18}/></span><span className="account-choice-copy"><strong>{item.name}</strong><span>{item.user_ids.length} Mitglieder</span><span className="account-mini-tags">{item.tags?.slice(0,2).map(value=><AccountTag key={value} text={value} color={item.color}/>)}</span></span></button>)}
        </div>
      </Card>
      <div className="account-detail" aria-label={mode==='users'?'Benutzerdetails':'Gruppendetails'}>
        {mode==='users'?(selectedUser?<UserPane key={selectedUser.id} user={selectedUser} groups={allGroups.filter(item=>item.user_ids.includes(selectedUser.id))} onSaved={refresh} onLabels={()=>setLabelTarget({kind:'users',item:selectedUser})} onGroup={openGroup}/>:<Empty title="Keine passenden Benutzer" text="Suchbegriff oder Filter anpassen oder einen neuen Benutzer erstellen."/>):(selectedGroup?<GroupPane group={selectedGroup} users={allUsers} onMembers={()=>setMembers(selectedGroup)} onLabels={()=>setLabelTarget({kind:'groups',item:selectedGroup})} onUser={openUser}/>:<Empty title="Keine passenden Gruppen" text="Suchbegriff oder Filter anpassen oder eine neue Gruppe erstellen."/>)}
      </div>
    </div>
    {newUser&&<NewUserModal onClose={()=>setNewUser(false)} onSaved={()=>{setNewUser(false);refresh()}}/>}
    {newGroup&&<NewGroupModal onClose={()=>setNewGroup(false)} onSaved={()=>{setNewGroup(false);refresh()}}/>}
    {members&&<GroupMembers group={members} users={allUsers} onClose={()=>setMembers(null)} onSaved={()=>{setMembers(null);refresh()}}/>}
    {labelTarget&&<LabelsModal kind={labelTarget.kind} item={labelTarget.item} onClose={()=>setLabelTarget(null)} onSaved={()=>{setLabelTarget(null);refresh()}}/>}
  </>
}

function UserPane({user,groups,onSaved,onLabels,onGroup}:{user:User;groups:Group[];onSaved:()=>void;onLabels:()=>void;onGroup:(id:string)=>void}){
  const [usernameOpen,setUsernameOpen]=useState(false),[passwordOpen,setPasswordOpen]=useState(false)
  const toggle=useMutation({mutationFn:()=>api(`/admin/users/${user.id}`,{method:'PATCH',body:JSON.stringify({is_active:!user.is_active})}),onSuccess:onSaved})
  const reset=useMutation({mutationFn:(password:string)=>api(`/admin/users/${user.id}/reset-password`,{method:'POST',body:JSON.stringify({password,must_change_password:true})}),onSuccess:()=>{setPasswordOpen(false);onSaved()}})
  return <>
    <Card className="account-profile"><div className="account-profile-heading"><PersonAvatar person={user} large/><div><h2>{user.display_name}</h2><p>{user.email}</p><div className="badge-row"><Badge tone={user.is_active?'success':'danger'}>{user.is_active?'Aktiv':'Deaktiviert'}</Badge>{user.must_change_password&&<Badge tone="warning">Passwortwechsel erforderlich</Badge>}</div></div></div><Link className="button button-secondary" to={`/admin/personen/${user.id}`}>Personenprofil öffnen</Link><div className="account-label-row"><AccountTags item={user}/><Button variant="ghost" onClick={onLabels}><Tags size={15}/>Farben &amp; Tags bearbeiten</Button></div></Card>
    {toggle.error&&<Notice type="error">{toggle.error.message}</Notice>}
    <div className="account-pane-grid"><Card><h3>Kontodaten</h3><dl className="detail-list"><div><dt>Benutzername</dt><dd>{user.username||'Nicht vergeben'}</dd></div><div><dt>Letzte Anmeldung</dt><dd>{formatDate(user.last_login_at)}</dd></div><div><dt>Erstellt</dt><dd>{formatDate(user.created_at)}</dd></div></dl><Button variant="secondary" aria-label={`Benutzername ändern · ${user.display_name}`} onClick={()=>setUsernameOpen(true)}>Benutzername ändern</Button></Card>
      <Card><h3>Rollen &amp; Zugriff</h3><RoleTags user={user}/>{user.roles.map(role=><p className="account-note" key={role}>{roleNotes[role]||role}</p>)}<p className="account-note">Farben und Tags sind Kennzeichnungen. Tenant- und Task-Freigaben werden unter Berechtigungen verwaltet.</p></Card></div>
    <Card><div className="card-heading"><div><h3>Gruppenmitgliedschaften</h3><p>{groups.length} zugeordnete Gruppen</p></div><Users size={18}/></div>{groups.length?<div className="account-members">{groups.map(group=><button className="account-member" key={group.id} onClick={()=>onGroup(group.id)}><AccountTag text={group.name} color={group.color}/><span>{group.description||'Gruppe öffnen'}</span></button>)}</div>:<p className="account-note">Noch keiner Gruppe zugeordnet. Mitglieder lassen sich im Bereich Gruppen hinzufügen.</p>}</Card>
    <Card><h3>Kontosicherheit</h3><p className="account-note">Ein temporäres Passwort muss bei der nächsten Anmeldung geändert werden.</p><div className="button-row"><Button variant="secondary" onClick={()=>{reset.reset();setPasswordOpen(true)}}><KeyRound size={15}/>Passwort zurücksetzen</Button><Button variant={user.is_active?'danger':'secondary'} loading={toggle.isPending} onClick={()=>{if(!user.is_active||window.confirm(`Konto ${user.display_name} deaktivieren?`))toggle.mutate()}}>{user.is_active?'Konto deaktivieren':'Konto aktivieren'}</Button></div></Card>
    {usernameOpen&&<UsernameModal user={user} onClose={()=>setUsernameOpen(false)} onSaved={()=>{setUsernameOpen(false);onSaved()}}/>}
    {passwordOpen&&<PasswordModal name={user.display_name} error={reset.error?.message||''} onClose={()=>setPasswordOpen(false)} onSave={password=>reset.mutate(password)} loading={reset.isPending}/>}
  </>
}

function GroupPane({group,users,onMembers,onLabels,onUser}:{group:Group;users:User[];onMembers:()=>void;onLabels:()=>void;onUser:(id:string)=>void}){
  const [teamOpen,setTeamOpen]=useState(false),qc=useQueryClient()
  const members=users.filter(user=>group.user_ids.includes(user.id))
  return <><Card className="account-profile"><div className="account-profile-heading"><span className="account-avatar large" data-color={group.color||'slate'}><Users size={24}/></span><div><h2>{group.name}</h2><p>{group.description||'Keine Beschreibung hinterlegt.'}</p><Badge>{group.user_ids.length} Mitglieder</Badge></div></div><div className="account-label-row"><AccountTags item={group}/><Button variant="ghost" onClick={onLabels}><Tags size={15}/>Farben &amp; Tags bearbeiten</Button></div></Card>
    <Card><div className="card-heading"><div><h3>Mitglieder</h3><p>Konten und deren aktueller Status</p></div><Button variant="secondary" onClick={onMembers}>Mitglieder bearbeiten</Button></div>{members.length?<div className="account-members">{members.map(user=><button key={user.id} className="account-member" onClick={()=>onUser(user.id)}><span><strong>{user.display_name}</strong><span className="subtle">{user.email}</span></span><Badge tone={user.is_active?'success':'danger'}>{user.is_active?'Aktiv':'Deaktiviert'}</Badge></button>)}</div>:<p className="account-note">Diese Gruppe hat noch keine Mitglieder.</p>}</Card>
    <Card><div className="card-heading"><div><h3>Team & Zuständigkeiten</h3><p>{group.is_team?'Als Team im Personenverzeichnis sichtbar.':'Diese Gruppe wird bisher nur zur Verwaltung verwendet.'}</p></div><Button variant="secondary" onClick={()=>setTeamOpen(true)}>Team-Einstellungen bearbeiten</Button></div><div className="badge-row">{group.responsibilities?.map(value=><Badge key={value}>{value}</Badge>)}</div><p className="profile-text">{group.responsibility_notes}</p>{group.is_team&&<Link className="button button-secondary" to={`/admin/teams/${group.id}`}>Teamprofil ansehen</Link>}</Card>
    <Card><h3>Gruppenfreigaben</h3><p className="account-note">Tenant-Zuordnungen und Task-Rechte können dieser Gruppe gezielt zugewiesen werden. Eine Mitgliedschaft allein erlaubt noch keinen Taskstart. Farben und Tags vergeben keine Berechtigungen.</p></Card>
    {teamOpen&&<TeamSettings group={group} onClose={()=>setTeamOpen(false)} onSaved={()=>{setTeamOpen(false);for(const key of ['admin-groups','profile-teams','person-profile','profile-directory','team-people'])void qc.invalidateQueries({queryKey:[key]})}}/>}</>
}

function TeamSettings({group,onClose,onSaved}:{group:Group;onClose:()=>void;onSaved:()=>void}){
  const [draft,setDraft]=useState({name:group.name,description:group.description,is_team:group.is_team||false,responsibilities:group.responsibilities||[],responsibility_notes:group.responsibility_notes||''})
  const save=useMutation({mutationFn:()=>api(`/admin/groups/${group.id}`,{method:'PATCH',body:JSON.stringify(draft)}),onSuccess:onSaved})
  return <Modal title={`Team-Einstellungen · ${group.name}`} onClose={onClose}><form onSubmit={event=>{event.preventDefault();save.mutate()}}>{save.error&&<Notice type="error">{save.error.message}</Notice>}<Field label="Gruppenname"><input required minLength={2} maxLength={120} value={draft.name} onChange={event=>setDraft({...draft,name:event.target.value})}/></Field><Field label="Beschreibung"><textarea maxLength={500} rows={3} value={draft.description} onChange={event=>setDraft({...draft,description:event.target.value})}/></Field><label className="checkbox-row"><input type="checkbox" checked={draft.is_team} onChange={event=>setDraft({...draft,is_team:event.target.checked})}/>Als Team für alle angemeldeten Personen anzeigen</label><ProfileTags label="Gemeinsame Zuständigkeiten" values={draft.responsibilities} onChange={responsibilities=>setDraft(current=>({...current,responsibilities}))}/><Field label="Team-Zuständigkeiten beschreiben"><textarea maxLength={2000} rows={3} value={draft.responsibility_notes} onChange={event=>setDraft({...draft,responsibility_notes:event.target.value})}/></Field><Notice>Teamkennzeichnung und Zuständigkeiten vergeben keine Rechte. Bestehende Mitgliedschaften und Zugriffsfreigaben bleiben erhalten. Beim Abschalten entfallen Hauptteam-Markierungen für diese Gruppe.</Notice><div className="modal-actions"><Button variant="secondary" type="button" onClick={onClose}>Abbrechen</Button><Button type="submit" loading={save.isPending}>Team-Einstellungen speichern</Button></div></form></Modal>
}

function LabelsModal({kind,item,onClose,onSaved}:{kind:'users'|'groups';item:User|Group;onClose:()=>void;onSaved:()=>void}){
  const tagInputId=useId()
  const [color,setColor]=useState<Color>(item.color||'slate'),[tags,setTags]=useState(item.tags||[]),[input,setInput]=useState(''),[error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>api(`/admin/${kind}/${item.id}`,{method:'PATCH',body:JSON.stringify({color,tags})}),onSuccess:onSaved})
  const add=()=>{const value=input.trim();if(!value||value.length>32||/[\x00-\x1f\x7f]/.test(value)){setError('Ein Tag benötigt 1–32 Zeichen ohne Steuerzeichen.');return}if(tags.some(tag=>tag.toLocaleLowerCase('de')===value.toLocaleLowerCase('de'))){setError('Dieser Tag ist bereits vorhanden.');return}if(tags.length>=10){setError('Maximal zehn Tags pro Eintrag.');return}setTags(current=>[...current,value]);setInput('');setError('')}
  return <Modal title={`Farben & Tags · ${'display_name' in item?item.display_name:item.name}`} onClose={onClose}>
    {mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}{error&&<Notice type="error">{error}</Notice>}
    <fieldset className="account-colors"><legend>Farbe</legend>{Object.entries(colors).map(([value,label])=><label key={value} data-color={value}><input type="radio" name="account-color" value={value} checked={color===value} onChange={()=>setColor(value as Color)}/><span className="account-color-dot"/>{label}</label>)}</fieldset>
    <div className="field"><label className="field-label" htmlFor={tagInputId}>Neuer Tag</label><div className="account-tag-input"><input id={tagInputId} aria-describedby={`${tagInputId}-help`} maxLength={32} value={input} onChange={event=>setInput(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();add()}}}/><Button variant="secondary" disabled={!input.trim()||tags.length>=10} onClick={add}>Hinzufügen</Button></div><span className="field-help" id={`${tagInputId}-help`}>Bis zu zehn Tags mit jeweils 32 Zeichen. Zum Beispiel Team, Standort oder Zuständigkeit.</span></div>
    <div className="account-edit-tags" aria-label="Zugeordnete Tags">{tags.map(tag=><span key={tag} className="account-tag" data-color={color}><span aria-hidden="true"/>{tag}<button aria-label={`Tag entfernen: ${tag}`} onClick={()=>setTags(current=>current.filter(value=>value!==tag))}>×</button></span>)}{!tags.length&&<p className="account-note">Noch keine Tags zugeordnet.</p>}</div>
    <p className="account-note">Kennzeichnungen werden gemeinsam gespeichert und verändern keine Zugriffsrechte.</p>
    <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} disabled={Boolean(input.trim())} onClick={()=>mutation.mutate()}>Kennzeichnung speichern</Button></div>{input.trim()&&<p className="account-note">Den eingegebenen Tag zuerst hinzufügen oder das Eingabefeld leeren.</p>}
  </Modal>
}

function GroupMembers({group,users,onClose,onSaved}:{group:Group;users:User[];onClose:()=>void;onSaved:()=>void}){
  const [ids,setIds]=useState(group.user_ids),[search,setSearch]=useState('')
  const mutation=useMutation({mutationFn:()=>api(`/admin/groups/${group.id}/members`,{method:'PUT',body:JSON.stringify({user_ids:ids})}),onSuccess:onSaved})
  const needle=search.trim().toLowerCase(),visible=users.filter(user=>`${user.display_name} ${user.email} ${user.username||''}`.toLowerCase().includes(needle))
  return <Modal title={`Mitglieder · ${group.name}`} onClose={onClose}>{mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}<Field label="Mitglieder suchen"><input value={search} onChange={event=>setSearch(event.target.value)}/></Field><p className="account-note">{ids.length} ausgewählt. Die Suche verändert die Auswahl nicht.</p><div className="account-member-picker">{visible.map(user=><label key={user.id}><input type="checkbox" disabled={mutation.isPending} checked={ids.includes(user.id)} onChange={event=>setIds(current=>event.target.checked?[...current,user.id]:current.filter(id=>id!==user.id))}/><span><strong>{user.display_name}</strong><span className="subtle">{user.email}{!user.is_active?' · Deaktiviert':''}</span></span></label>)}{!visible.length&&<p>Keine passenden Benutzer.</p>}</div><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>mutation.mutate()}>Mitglieder speichern</Button></div></Modal>
}

function UsernameModal({user,onClose,onSaved}:{user:User;onClose:()=>void;onSaved:()=>void}){
  const [username,setUsername]=useState(user.username||'')
  const mutation=useMutation({mutationFn:()=>api(`/admin/users/${user.id}`,{method:'PATCH',body:JSON.stringify({username:username.trim()})}),onSuccess:onSaved})
  return <Modal title={`Benutzername ändern · ${user.display_name}`} onClose={onClose}>{mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}<Field label="Benutzername" help={usernameHelp}><input autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={64} value={username} onChange={event=>setUsername(event.target.value)}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} disabled={!usernamePattern.test(username.trim())} onClick={()=>mutation.mutate()}>Benutzername speichern</Button></div></Modal>
}

function NewUserModal({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}){
  const [email,setEmail]=useState(''),[username,setUsername]=useState(''),[name,setName]=useState(''),[password,setPassword]=useState(''),[role,setRole]=useState('viewer')
  const mutation=useMutation({mutationFn:()=>api('/admin/users',{method:'POST',body:JSON.stringify({email,username:username.trim()||undefined,display_name:name,password,role_codes:[role],must_change_password:true})}),onSuccess:onSaved})
  return <Modal title="Benutzer erstellen" onClose={onClose}>{mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}<div className="form-grid columns-2"><Field label="Anzeigename"><input maxLength={160} value={name} onChange={event=>setName(event.target.value)}/></Field><Field label="E-Mail-Adresse"><input type="email" value={email} onChange={event=>setEmail(event.target.value)}/></Field><Field label="Benutzername (optional)" help={`Leer lassen: automatisch aus der E-Mail-Adresse vergeben. ${usernameHelp}`}><input autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={64} value={username} onChange={event=>setUsername(event.target.value)}/></Field><Field label="Initiales Passwort" help="Mindestens 12 Zeichen; Änderung beim ersten Login erforderlich."><input type="password" autoComplete="new-password" value={password} onChange={event=>setPassword(event.target.value)}/></Field><Field label="Portalrolle"><select value={role} onChange={event=>setRole(event.target.value)}>{Object.entries(roles).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Field></div><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>mutation.mutate()} disabled={!email||name.trim().length<2||password.length<12||Boolean(username.trim()&&!usernamePattern.test(username.trim()))}>Erstellen</Button></div></Modal>
}

function NewGroupModal({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}){
  const [name,setName]=useState(''),[description,setDescription]=useState('')
  const mutation=useMutation({mutationFn:()=>api('/admin/groups',{method:'POST',body:JSON.stringify({name,description})}),onSuccess:onSaved})
  return <Modal title="Gruppe erstellen" onClose={onClose}>{mutation.error&&<Notice type="error">{mutation.error.message}</Notice>}<Field label="Gruppenname"><input maxLength={120} value={name} onChange={event=>setName(event.target.value)}/></Field><Field label="Beschreibung"><textarea maxLength={500} value={description} onChange={event=>setDescription(event.target.value)}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>mutation.mutate()} disabled={name.trim().length<2}>Erstellen</Button></div></Modal>
}

function PasswordModal({name,error,onClose,onSave,loading}:{name:string;error:string;onClose:()=>void;onSave:(value:string)=>void;loading:boolean}){
  const [password,setPassword]=useState('')
  return <Modal title={`Passwort zurücksetzen · ${name}`} onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<Field label="Neues temporäres Passwort"><input type="password" autoComplete="new-password" value={password} onChange={event=>setPassword(event.target.value)}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={loading} disabled={password.length<12} onClick={()=>onSave(password)}>Zurücksetzen</Button></div></Modal>
}
