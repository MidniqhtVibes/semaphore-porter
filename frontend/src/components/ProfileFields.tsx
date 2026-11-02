import { useId, useRef, useState } from 'react'
import { Button } from './ui'

export const profileColors={slate:'Grau',blue:'Blau',violet:'Violett',green:'Grün',amber:'Bernstein',rose:'Rosa'} as const

export function ProfileTags({label,values,onChange}:{label:string;values:string[];onChange:(values:string[])=>void}){
  const id=useId(),inputRef=useRef<HTMLInputElement>(null),[input,setInput]=useState(''),[error,setError]=useState('')
  const invalid=(message:string)=>{setError(message);inputRef.current?.setCustomValidity(message)}
  const add=()=>{
    const value=input.trim()
    if(!value||value.length>32||/[\x00-\x1f\x7f]/.test(value)){invalid('1–32 Zeichen ohne Steuerzeichen verwenden.');return}
    if(values.length>=20){invalid('Maximal 20 Einträge.');return}
    if(values.some(item=>item.toLocaleLowerCase('de')===value.toLocaleLowerCase('de'))){setInput('');setError('');inputRef.current?.setCustomValidity('');return}
    onChange([...values,value]);setInput('');setError('')
  }
  return <div className="field"><label className="field-label" htmlFor={id}>{label}</label><div className="account-tag-input"><input id={id} ref={inputRef} aria-invalid={Boolean(error)} maxLength={32} value={input} onChange={event=>{setInput(event.target.value);setError('');event.target.setCustomValidity('')}} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();add()}}} onBlur={()=>{if(input.trim())add()}}/><Button variant="secondary" type="button" disabled={!input.trim()||values.length>=20} onMouseDown={event=>event.preventDefault()} onClick={add}>Hinzufügen</Button></div><span className="field-help">Bis zu 20 Einträge; Enter oder „Hinzufügen“. Eingaben werden beim Verlassen des Felds übernommen.</span>{error&&<span className="field-error">{error}</span>}<div className="account-edit-tags">{values.map(value=><span className="account-tag" key={value}>{value}<button type="button" aria-label={`${label} entfernen: ${value}`} onClick={()=>onChange(values.filter(item=>item!==value))}>×</button></span>)}</div></div>
}
