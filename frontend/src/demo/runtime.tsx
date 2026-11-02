import { createContext, useContext, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, demoDocument } from '../api'
import { Button, Loading, Notice } from '../components/ui'

export type Runtime={mode:'production'|'demo';demo_available:boolean;return_url:string|null;ephemeral:boolean}
const RuntimeContext=createContext<Runtime>({mode:'production',demo_available:true,return_url:null,ephemeral:false})
export function useRuntime(){return useContext(RuntimeContext)}

export function RuntimeProvider({children}:{children:ReactNode}){
  const query=useQuery({queryKey:['runtime-config'],queryFn:async()=>{
    const value=await api<Runtime>('/demo/config')
    if(!value||!['demo','production'].includes(value.mode))throw new Error('Ungültiger Anwendungsmodus.')
    if((value.mode==='demo')!==demoDocument)throw new Error('Frontend und API verwenden unterschiedliche Betriebsmodi.')
    return value
  },staleTime:Infinity,retry:false})
  if(query.isLoading)return <div className="app-loading"><Loading label="Anwendung wird vorbereitet …"/></div>
  if(!query.data)return <div className="fatal"><Notice type="error">Der Anwendungsmodus konnte nicht geladen werden. Frontend und Backend müssen gemeinsam aktualisiert sein.</Notice><Button onClick={()=>void query.refetch()}>Erneut versuchen</Button></div>
  return <RuntimeContext.Provider value={query.data}>{children}</RuntimeContext.Provider>
}
