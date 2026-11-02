import { useEffect, useState } from 'react'
import { apiUrl } from '../api'

export function PersonAvatar({person,large=false}:{person:{id:string;display_name:string;profile_color?:string;avatar_version?:string|null};large?:boolean}){
  const [failed,setFailed]=useState(false)
  useEffect(()=>setFailed(false),[person.id,person.avatar_version])
  const initials=person.display_name.trim().split(/\s+/).map(word=>word[0]).filter(Boolean).slice(0,2).join('').toUpperCase()
  return <span className={`person-avatar${large?' person-avatar-large':''}`} data-color={person.profile_color||'slate'} aria-hidden="true">
    {person.avatar_version&&!failed?<img src={apiUrl(`/profiles/${person.id}/avatar?v=${encodeURIComponent(person.avatar_version)}`)} alt="" loading="lazy" decoding="async" onError={()=>setFailed(true)}/>:<span>{initials||'?'}</span>}
  </span>
}
