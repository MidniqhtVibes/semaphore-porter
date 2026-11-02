import { useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, ChevronLeft, ChevronRight, Mail, MapPin, Pencil, Phone, Search, Users } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Badge, Button, Card, Empty, Field, Loading, Modal, Notice, PageHeader } from '../components/ui'
import { PersonAvatar } from '../components/PersonAvatar'
import { ProfileTags, profileColors } from '../components/ProfileFields'
import type { PersonProfile, TeamProfile } from '../types'

function useProfileBase(){return useLocation().pathname.startsWith('/admin')?'/admin':'/portal'}
type Directory={items:PersonProfile[];total:number;offset:number;limit:number}
const labels=(values:string[])=>values.length?<div className="badge-row">{values.map(value=><span className="account-tag" key={value}>{value}</span>)}</div>:<p className="subtle">Noch nicht angegeben.</p>

function PeoplePagination({offset,limit,total,loading,onChange}:{offset:number;limit:number;total:number;loading:boolean;onChange:(offset:number)=>void}){
  const pages=Math.max(1,Math.ceil(total/limit)),page=Math.floor(offset/limit)+1
  return <div className="people-pagination">
    <span className="people-pagination-summary">{total===0?'0 Personen':total===1?'1 Person':`${offset+1}–${Math.min(offset+limit,total)} von ${total} Personen`}</span>
    {(pages>1||offset>0)&&<nav className="people-pagination-controls" aria-label="Personenseiten">
      <Button variant="secondary" disabled={loading||offset===0} onClick={()=>onChange(Math.max(0,offset-limit))}><ChevronLeft size={16} aria-hidden="true"/>Zurück</Button>
      <span className="people-pagination-page" aria-live="polite">Seite {page} von {pages}</span>
      <Button variant="secondary" disabled={loading||offset+limit>=total} onClick={()=>onChange(offset+limit)}>Weiter<ChevronRight size={16} aria-hidden="true"/></Button>
    </nav>}
  </div>
}

export function PeoplePage(){
  const base=useProfileBase(),[q,setQ]=useState(''),[team,setTeam]=useState(''),[offset,setOffset]=useState(0)
  const teams=useQuery({queryKey:['profile-teams'],queryFn:()=>api<TeamProfile[]>('/profiles/teams')})
  const people=useQuery({queryKey:['profile-directory',q,team,offset],queryFn:()=>api<Directory>(`/profiles?q=${encodeURIComponent(q)}&offset=${offset}&limit=24${team?`&team_id=${team}`:''}`),placeholderData:keepPreviousData})
  return <><PageHeader title="Personen & Teams" description="Profile, Kenntnisse und Zuständigkeiten aller aktiven Personen."/>
    <Card><div className="people-filters"><Field label="Personen oder Zuständigkeiten suchen"><div className="input-icon"><Search size={17}/><input type="search" maxLength={160} value={q} onChange={event=>{setQ(event.target.value);setOffset(0)}} placeholder="Name, Kenntnisse, Team, Aufgabenbereich …"/></div></Field><Field label="Nach Team filtern"><select value={team} onChange={event=>{setTeam(event.target.value);setOffset(0)}}><option value="">Alle Personen</option>{teams.data?.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></Field></div></Card>
    {(people.error||teams.error)&&<Notice type="error">{people.error?.message||teams.error?.message}</Notice>}
    {people.isLoading?<Loading/>:people.data?.items?.length?<><div className="people-grid" aria-busy={people.isFetching}>{people.data.items.map(person=><Link key={person.id} className="card person-card" to={`${base}/personen/${person.id}`}><PersonAvatar person={person} large/><div><h2>{person.display_name}</h2><p>{person.position||'Profil ansehen'}</p><span className="subtle">{person.teams.map(item=>item.name).join(' · ')||person.department}</span></div>{labels([...new Set([...person.team_responsibilities,...person.responsibilities])].slice(0,4))}</Link>)}</div><PeoplePagination offset={people.data.offset} limit={people.data.limit} total={people.data.total} loading={people.isFetching} onChange={setOffset}/></>:!people.error&&<Empty title="Keine passenden Profile" text="Suche oder Teamfilter anpassen."/>}
    <h2>Teams</h2><div className="people-grid">{teams.data?.map(item=><Link className="card team-card" key={item.id} to={`${base}/teams/${item.id}`}><Users size={24}/><h3>{item.name}</h3><p>{item.description||'Keine Beschreibung hinterlegt.'}</p><Badge>{item.member_count} Mitglieder</Badge>{labels(item.responsibilities)}</Link>)}</div>{teams.data?.length===0&&<p className="subtle">Noch keine Gruppe als Team markiert. Systemadmins können bestehende Gruppen unter Benutzer & Gruppen dafür freigeben.</p>}
  </>
}

export function TeamPage(){
  const {teamId}=useParams(),base=useProfileBase()
  const teams=useQuery({queryKey:['profile-teams'],queryFn:()=>api<TeamProfile[]>('/profiles/teams')})
  const [offset,setOffset]=useState(0)
  const people=useQuery({queryKey:['team-people',teamId,offset],queryFn:()=>api<Directory>(`/profiles?team_id=${teamId}&offset=${offset}&limit=60`),enabled:Boolean(teamId),placeholderData:keepPreviousData})
  const team=teams.data?.find(item=>item.id===teamId)
  if(teams.isLoading)return <Loading/>
  if(teams.error||people.error)return <Notice type="error">{teams.error?.message||people.error?.message}</Notice>
  if(!team)return <Empty title="Team nicht gefunden" text="Die Gruppe ist nicht als Team sichtbar."/>
  return <><PageHeader title={team.name} description={team.description} actions={<Link className="button button-secondary" to={`${base}/personen`}>Alle Personen & Teams</Link>}/><Card><h2>Gemeinsame Zuständigkeiten</h2>{labels(team.responsibilities)}<p className="profile-text">{team.responsibility_notes}</p></Card><h2>{team.member_count} {team.member_count===1?'Teammitglied':'Teammitglieder'}</h2>{people.isLoading?<Loading/>:<div className="people-grid" aria-busy={people.isFetching}>{people.data?.items.map(person=><Link className="card person-card" key={person.id} to={`${base}/personen/${person.id}`}><PersonAvatar person={person}/><div><h3>{person.display_name}</h3><p>{person.position||'Profil ansehen'}</p></div></Link>)}</div>}{people.data&&<PeoplePagination offset={people.data.offset} limit={people.data.limit} total={people.data.total} loading={people.isFetching} onChange={setOffset}/>}</>
}

export function PersonPage(){
  const {personId}=useParams(),base=useProfileBase()
  return <><PageHeader title="Personenprofil" actions={<Link className="button button-secondary" to={`${base}/personen`}>Alle Personen & Teams</Link>}/><ProfileView personId={personId!}/></>
}

export function OwnProfile(){
  const {user}=useAuth()
  return user&&!user.must_change_password?<ProfileView personId="me"/>:null
}

function ProfileView({personId}:{personId:string}){
  const auth=useAuth(),base=useProfileBase(),qc=useQueryClient(),[editing,setEditing]=useState(false),[organization,setOrganization]=useState(false),[imageError,setImageError]=useState(''),fileInput=useRef<HTMLInputElement>(null)
  const query=useQuery({queryKey:['person-profile',personId],queryFn:()=>api<PersonProfile>(`/profiles/${personId}`)})
  const invalidate=()=>{void qc.invalidateQueries({queryKey:['person-profile']});void qc.invalidateQueries({queryKey:['profile-directory']});void qc.invalidateQueries({queryKey:['team-people']});void qc.invalidateQueries({queryKey:['admin-users']})}
  const upload=useMutation({mutationFn:async(file:File)=>{
    if(file.size>5*1024*1024)throw new Error('Profilbilder dürfen höchstens 5 MB groß sein.')
    if(!['image/png','image/jpeg','image/webp','image/gif'].includes(file.type))throw new Error('PNG, JPEG, WebP oder GIF verwenden.')
    const data=new FormData();data.append('file',file)
    return api<{avatar_version:string}>('/profiles/me/avatar',{method:'POST',body:data})
  },onSuccess:value=>{setImageError('');auth.syncProfile({id:auth.user!.id,...value});invalidate()},onError:(error:Error)=>setImageError(error.message)})
  const remove=useMutation({mutationFn:()=>api('/profiles/me/avatar',{method:'DELETE'}),onSuccess:()=>{auth.syncProfile({id:auth.user!.id,avatar_version:null});setImageError('');invalidate()},onError:(error:Error)=>setImageError(error.message)})
  if(query.isLoading)return <Loading label="Profil wird geladen …"/>
  const person=query.data
  if(query.error||!person?.id||!Array.isArray(person.teams))return <Notice type="error">{query.error?.message||'Profil konnte nicht geladen werden.'}</Notice>
  const own=auth.user?.id===person.id,primary=person.teams.find(team=>team.id===person.primary_team_id)
  return <div className="person-profile">
    <Card className="person-profile-hero" data-color={person.profile_color}><div className="person-profile-heading"><PersonAvatar person={person} large/><div><h2>{person.display_name}</h2>{person.position&&<p><Briefcase size={16}/>{person.position}</p>}<span className="subtle">{[person.department,person.location].filter(Boolean).join(' · ')}</span>{!person.is_active&&<Badge tone="warning">Konto deaktiviert</Badge>}</div></div><div className="button-row">{own&&<Button variant="secondary" onClick={()=>setEditing(true)}><Pencil size={15}/>Persönliches Profil bearbeiten</Button>}{auth.isAdmin&&<Button variant="secondary" onClick={()=>setOrganization(true)}>Organisation bearbeiten</Button>}</div></Card>
    {imageError&&<Notice type="error">{imageError}</Notice>}
    {own&&<Card><div className="card-heading"><div><h3>Profilbild</h3><p>PNG, JPEG, WebP oder animiertes GIF. Bis 5 MB und 1024 × 1024 Pixel; Animationen bis 120 Bilder und 16 Megapixel insgesamt.</p></div><div className="button-row"><Button variant="secondary" disabled={remove.isPending} loading={upload.isPending} onClick={()=>fileInput.current?.click()}>Bild hochladen</Button><Button variant="ghost" disabled={!person.avatar_version||upload.isPending} loading={remove.isPending} onClick={()=>remove.mutate()}>Bild entfernen</Button></div></div><input className="visually-hidden" aria-label="Profilbild auswählen" ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={event=>{const file=event.target.files?.[0];event.target.value='';if(file)upload.mutate(file)}}/></Card>}
    <div className="person-profile-columns"><div className="person-profile-column"><Card><h3>Über mich</h3><p className="profile-text">{person.bio||'Noch keine Beschreibung hinterlegt.'}</p><h3>Kenntnisse & Schwerpunkte</h3>{labels(person.skills)}</Card><Card><h3>Persönliche Zuständigkeiten</h3>{labels(person.responsibilities)}<p className="profile-text">{person.responsibility_notes}</p></Card></div><div className="person-profile-column"><Card><h3>Teams</h3>{person.teams.length?person.teams.map(team=><div className="person-team" key={team.id}><Link to={`${base}/teams/${team.id}`}>{team.name}</Link>{team.id===primary?.id&&<Badge tone="info">Hauptteam</Badge>}{labels(team.responsibilities)}{team.responsibility_notes&&<p className="profile-text">{team.responsibility_notes}</p>}</div>):<p className="subtle">Noch keinem Team zugeordnet.</p>}</Card><Card><h3>Kontakt & Organisation</h3><dl className="detail-list"><div><dt><Mail size={15}/>Geschäftliche E-Mail</dt><dd>{person.email}</dd></div>{person.phone&&<div><dt><Phone size={15}/>Telefon / Durchwahl</dt><dd>{person.phone}</dd></div>}{person.location&&<div><dt><MapPin size={15}/>Standort</dt><dd>{person.location}</dd></div>}</dl><p className="account-note">Profile sind für alle angemeldeten Personen sichtbar. Teamzuordnungen und organisatorische Angaben werden administrativ gepflegt.</p></Card></div></div>
    {editing&&<PersonalEditor person={person} onClose={()=>setEditing(false)} onSaved={value=>{auth.syncProfile(value);setEditing(false);invalidate()}}/>}
    {organization&&<OrganizationEditor person={person} onClose={()=>setOrganization(false)} onSaved={()=>{setOrganization(false);invalidate()}}/>}
  </div>
}

function PersonalEditor({person,onClose,onSaved}:{person:PersonProfile;onClose:()=>void;onSaved:(person:PersonProfile)=>void}){
  const [draft,setDraft]=useState({display_name:person.display_name,bio:person.bio,skills:person.skills,responsibilities:person.responsibilities,responsibility_notes:person.responsibility_notes,phone:person.phone,profile_color:person.profile_color})
  const save=useMutation({mutationFn:()=>api<PersonProfile>('/profiles/me',{method:'PUT',body:JSON.stringify(draft)}),onSuccess:onSaved})
  return <Modal title="Persönliches Profil bearbeiten" onClose={onClose}><form onSubmit={event=>{event.preventDefault();save.mutate()}}>{save.error&&<Notice type="error">{save.error.message}</Notice>}<Notice>Diese Angaben sind für alle angemeldeten Personen sichtbar.</Notice><Field label="Anzeigename"><input required minLength={2} maxLength={160} value={draft.display_name} onChange={event=>setDraft({...draft,display_name:event.target.value})}/></Field><Field label="Über mich"><textarea rows={4} maxLength={2000} value={draft.bio} onChange={event=>setDraft({...draft,bio:event.target.value})}/></Field><ProfileTags label="Kenntnisse" values={draft.skills} onChange={skills=>setDraft(current=>({...current,skills}))}/><ProfileTags label="Persönliche Zuständigkeiten" values={draft.responsibilities} onChange={responsibilities=>setDraft(current=>({...current,responsibilities}))}/><Field label="Zuständigkeiten beschreiben"><textarea rows={3} maxLength={2000} value={draft.responsibility_notes} onChange={event=>setDraft({...draft,responsibility_notes:event.target.value})}/></Field><Field label="Telefon / Durchwahl"><input maxLength={80} value={draft.phone} onChange={event=>setDraft({...draft,phone:event.target.value})}/></Field><Field label="Persönliche Akzentfarbe"><select value={draft.profile_color} onChange={event=>setDraft({...draft,profile_color:event.target.value as PersonProfile['profile_color']})}>{Object.entries(profileColors).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></Field><div className="modal-actions"><Button variant="secondary" type="button" onClick={onClose}>Abbrechen</Button><Button type="submit" loading={save.isPending}>Profil speichern</Button></div></form></Modal>
}

function OrganizationEditor({person,onClose,onSaved}:{person:PersonProfile;onClose:()=>void;onSaved:()=>void}){
  const [draft,setDraft]=useState({position:person.position,department:person.department,location:person.location,primary_team_id:person.primary_team_id})
  const save=useMutation({mutationFn:()=>api(`/profiles/${person.id}/organization`,{method:'PUT',body:JSON.stringify(draft)}),onSuccess:onSaved})
  return <Modal title={`Organisation · ${person.display_name}`} onClose={onClose}><form onSubmit={event=>{event.preventDefault();save.mutate()}}>{save.error&&<Notice type="error">{save.error.message}</Notice>}{(['position','department','location'] as const).map((key,index)=><Field label={['Funktion / Position','Abteilung','Standort'][index]} key={key}><input maxLength={160} value={draft[key]} onChange={event=>setDraft({...draft,[key]:event.target.value})}/></Field>)}<Field label="Optionales Hauptteam"><select value={draft.primary_team_id||''} onChange={event=>setDraft({...draft,primary_team_id:event.target.value||null})}><option value="">Kein Hauptteam</option>{person.teams.map(team=><option key={team.id} value={team.id}>{team.name}</option>)}</select></Field><p className="account-note">Mehrere Teams sind möglich. Mitgliedschaften und die Team-Markierung werden unter Benutzer & Gruppen verwaltet; das Hauptteam vergibt keine Rechte.</p><div className="modal-actions"><Button variant="secondary" type="button" onClick={onClose}>Abbrechen</Button><Button type="submit" loading={save.isPending}>Organisation speichern</Button></div></form></Modal>
}
