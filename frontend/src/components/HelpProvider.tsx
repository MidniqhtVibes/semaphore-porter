import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation } from 'react-router-dom'
import { ArrowUpRight, BookOpen, CircleHelp, X } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { errorHelpContext, helpBase, helpContextForPath, type HelpContextInfo } from '../help'
import type { NavigationMode } from './navigation'
import { Button, Loading, Notice } from './ui'
import '../help.css'

type HelpState={open:(context:string)=>void;setPageContext:(context:string|null)=>void;current:string;mode:NavigationMode}
const Help=createContext<HelpState|null>(null)

export function HelpProvider({mode,children}:{mode:NavigationMode;children:ReactNode}) {
  const location=useLocation(),[active,setActive]=useState<string|null>(null),[pageContext,setPageContext]=useState<string|null>(null)
  const opener=useRef<HTMLElement|null>(null)
  const open=useCallback((context:string)=>{opener.current=document.activeElement instanceof HTMLElement?document.activeElement:null;setActive(context)},[])
  const close=useCallback(()=>setActive(null),[])
  const value=useMemo(()=>({open,setPageContext,current:pageContext||helpContextForPath(location.pathname),mode}),[open,pageContext,location.pathname,mode])
  return <Help.Provider value={value}>{children}{active&&createPortal(<HelpPanel context={active} mode={mode} onClose={close} opener={opener.current}/>,document.body)}</Help.Provider>
}

export function usePageHelp(context:string) {
  const help=useContext(Help),setContext=help?.setPageContext
  useEffect(()=>{setContext?.(context);return()=>setContext?.(null)},[context,setContext])
}

export function HelpButton({context,label='Hilfe zu diesem Bereich öffnen',global=false}:{context?:string;label?:string;global?:boolean}) {
  const help=useContext(Help)
  if(!help)return null
  return <button type="button" className={`help-trigger${global?' help-trigger-global':''}`} aria-label={label} title={label} onClick={()=>help.open(context||help.current)}><CircleHelp size={global?19:17} aria-hidden="true"/></button>
}

export function ErrorHelp({message}:{message:string}) {
  const help=useContext(Help)
  return help?<ActiveErrorHelp message={message} help={help}/>:null
}

function ActiveErrorHelp({message,help}:{message:string;help:HelpState}) {
  const {isAdmin}=useAuth()
  const context=errorHelpContext(message,isAdmin)
  if(!context)return null
  return <button type="button" className="help-error-link" onClick={()=>help.open(context)}><CircleHelp size={15} aria-hidden="true"/>Passende Anleitung öffnen</button>
}

function HelpPanel({context,mode,onClose,opener}:{context:string;mode:NavigationMode;onClose:()=>void;opener:HTMLElement|null}) {
  const {user,isAdmin}=useAuth(),titleId=useId(),dialog=useRef<HTMLDialogElement>(null)
  const query=useQuery({queryKey:['help-context',user?.id,isAdmin,context],queryFn:()=>api<HelpContextInfo>(`/help/contexts/${encodeURIComponent(context)}`,{cache:'no-store'}),staleTime:0,gcTime:0,retry:false})
  useEffect(()=>{
    const element=dialog.current
    if(element?.showModal)element.showModal()
    else element?.setAttribute('open','')
    return()=>{element?.close?.();if(opener?.isConnected)opener.focus()}
  },[opener])
  const info=query.data
  return <dialog ref={dialog} className="help-panel" aria-labelledby={titleId} onCancel={event=>{event.preventDefault();onClose()}}>
    <header className="help-panel-header"><span className="help-eyebrow"><BookOpen size={16}/>HILFE ZU DIESEM BEREICH</span><Button variant="ghost" aria-label="Hilfe schließen" onClick={onClose} autoFocus><X size={19}/></Button></header>
    <div className="help-panel-content"><h2 id={titleId}>{info?.title||'Kontextbezogene Hilfe'}</h2>
      {query.isLoading&&<Loading label="Anleitung wird geladen …"/>}
      {query.isError&&<Notice type="error">{query.error.message}</Notice>}
      {info&&<><p className="help-panel-summary">{info.summary}</p><ol className="help-quick-steps">{info.steps.map((step,index)=><li key={index}>{step}</li>)}</ol>
        <Link className="button button-primary help-full-article" target="_blank" rel="noopener noreferrer" to={`${helpBase(mode)}/${info.article_id}${info.anchor?'#'+info.anchor:''}`}>Vollständige Anleitung öffnen<ArrowUpRight size={17}/></Link>
        <p className="help-panel-note">Öffnet in einem neuen Tab. Ihre Angaben auf dieser Seite bleiben erhalten.</p></>}
      <Link className="help-overview-link" to={helpBase(mode)} target="_blank" rel="noopener noreferrer">Zur Dokumentationsübersicht<ArrowUpRight size={14}/></Link>
    </div>
  </dialog>
}
