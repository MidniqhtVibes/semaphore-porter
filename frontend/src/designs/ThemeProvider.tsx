import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'
import { BUILTIN_THEMES, FONT_STACKS, parseThemeFile, resolveCustomTheme, type Theme, type ThemeFile } from './themes'
import { applyWebsiteSymbol } from './websiteSymbols'

export const THEME_STORAGE_KEY='semaphore-porter.designs.v1'
type ThemeState={selected:string;custom:ThemeFile[]}
type ThemeContextValue={themes:Theme[];active:Theme;storageWarning:string;select:(id:string)=>void;importTheme:(value:unknown)=>Theme;remove:(id:string)=>void}
const ThemeContext=createContext<ThemeContextValue|null>(null)
const initial:ThemeState={selected:'github-dark',custom:[]}

function readState(): ThemeState {
  try{
    const stored=JSON.parse(localStorage.getItem(THEME_STORAGE_KEY)||'null')
    if(!stored||!Array.isArray(stored.custom))return initial
    const custom:ThemeFile[]=[]
    for(const value of stored.custom.slice(0,20)){
      try{const parsed=parseThemeFile(value);if(!custom.some(theme=>theme.id===parsed.id))custom.push(parsed)}catch{/* Ignore invalid stored packages. */}
    }
    const selected=String(stored.selected)
    return {custom,selected:BUILTIN_THEMES.some(theme=>theme.id===selected)||custom.some(theme=>`custom:${theme.id}`===selected)?selected:'github-dark'}
  }catch{return initial}
}
export function applyTheme(theme: Theme){
  const root=document.documentElement
  for(const [key,value] of Object.entries(theme.colors))root.style.setProperty(`--${key}`,value)
  root.style.setProperty('--font-family',FONT_STACKS[theme.font])
  root.style.setProperty('--radius',`${theme.radius}px`)
  root.style.colorScheme=theme.mode
  root.dataset.theme=theme.id
  root.dataset.themeMode=theme.mode
  root.dataset.themeFont=theme.font
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme.colors.header)
  document.querySelector('meta[name="color-scheme"]')?.setAttribute('content',theme.mode)
}
export function ThemeProvider({children}:{children:ReactNode}){
  const [state,setState]=useState(readState), [storageWarning,setStorageWarning]=useState('')
  const themes=useMemo(()=>[...BUILTIN_THEMES,...state.custom.map(resolveCustomTheme)],[state.custom])
  const active=themes.find(theme=>theme.id===state.selected)||BUILTIN_THEMES[0]
  useLayoutEffect(()=>applyTheme(active),[active])
  useLayoutEffect(()=>applyWebsiteSymbol(),[])
  useEffect(()=>{
    const update=(event:StorageEvent)=>{if(event.key===THEME_STORAGE_KEY||event.key===null)setState(readState())}
    window.addEventListener('storage',update)
    return ()=>window.removeEventListener('storage',update)
  },[])
  const save=(next:ThemeState)=>{
    setState(next)
    try{localStorage.setItem(THEME_STORAGE_KEY,JSON.stringify(next));setStorageWarning('')}
    catch{setStorageWarning('Der Browser kann das Design nicht dauerhaft speichern. Die Auswahl gilt für diese Sitzung.')}
  }
  const select=(id:string)=>{if(themes.some(theme=>theme.id===id))save({...state,selected:id})}
  const importTheme=(value:unknown)=>{
    const definition=parseThemeFile(value), theme=resolveCustomTheme(definition)
    if(state.custom.length>=20&&!state.custom.some(item=>item.id===definition.id))throw new Error('Maximal 20 eigene Designs sind möglich. Bitte zuerst ein Design entfernen.')
    save({...state,selected:theme.id,custom:[...state.custom.filter(item=>item.id!==definition.id),definition]})
    return theme
  }
  const remove=(id:string)=>save({...state,selected:state.selected===id?'github-dark':state.selected,custom:state.custom.filter(theme=>`custom:${theme.id}`!==id)})
  return <ThemeContext.Provider value={{themes,active,storageWarning,select,importTheme,remove}}>{children}</ThemeContext.Provider>
}
export function useTheme(){
  const value=useContext(ThemeContext)
  if(!value)throw new Error('ThemeProvider fehlt.')
  return value
}
