import { useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { DesignCreator } from '../designs/DesignCreator'
import { useTheme } from '../designs/ThemeProvider'
import { BUILTIN_THEMES, DEFAULT_THEME, createDraft, type Theme } from '../designs/themes'
import { Notice } from '../components/ui'

function StudioSession({source,edit,back}:{source:Theme;edit:boolean;back:string}) {
  const [initial]=useState(()=>edit&&source.definition?structuredClone(source.definition):createDraft(source))
  const {importTheme}=useTheme()
  const navigate=useNavigate()
  return <DesignCreator initial={initial} initialMode={back.startsWith('/admin')?'admin':'portal'} onClose={()=>navigate(back)} onSave={value=>{
    const saved=importTheme(value)
    navigate(back,{state:{designMessage:`${saved.name} wurde gespeichert und aktiviert.`}})
  }}/>
}

export default function DesignStudioPage() {
  const {themes}=useTheme()
  const [params]=useSearchParams()
  const location=useLocation()
  const back=location.pathname.startsWith('/admin')?'/admin/designs':'/portal/designs'
  const id=params.get('design')||params.get('vorlage')
  const source=id?[...themes,...BUILTIN_THEMES].find(theme=>theme.id===id):DEFAULT_THEME
  if(!source)return <main className="studio-missing"><Notice type="error">Dieses Design ist in diesem Browser nicht mehr verfügbar.</Notice><Link className="button button-secondary" to={back}>Zurück zu Designs</Link></main>
  return <StudioSession key={`${back}:${id||'new'}`} source={source} edit={params.has('design')} back={back}/>
}
