import { Children, isValidElement, useState, type ReactNode } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Link } from 'react-router-dom'
import { Check, Copy } from 'lucide-react'
import type { HelpArticle } from '../help'

function textOf(children:ReactNode):string {
  return Children.toArray(children).map(child=>typeof child==='string'||typeof child==='number'?String(child):isValidElement<{children?:ReactNode}>(child)?textOf(child.props.children):'').join('')
}

function CodeBlock({children}:{children?:ReactNode}) {
  const [copied,setCopied]=useState(false),[error,setError]=useState(false)
  const copy=async()=>{try{await navigator.clipboard.writeText(textOf(children));setCopied(true);setError(false)}catch{setError(true)}}
  return <div className="help-code"><div className="help-code-header"><span>Beispiel</span><button type="button" onClick={()=>void copy()} aria-label="Codebeispiel kopieren">{copied?<Check size={14}/>:<Copy size={14}/>} {copied?'Kopiert':'Kopieren'}</button></div><pre tabIndex={0}>{children}</pre>{error&&<p role="status">Kopieren ist hier nicht verfügbar. Den Text bitte direkt markieren und kopieren.</p>}</div>
}

export function HelpMarkdown({article,base,allowed}:{article:HelpArticle;base:string;allowed:Set<string>}) {
  const link=(url:string)=>{
    if(/^#[a-z0-9-]+$/.test(url))return url
    const match=/^([a-z0-9]+(?:-[a-z0-9]+)*)(#[a-z0-9-]+)?$/.exec(url)
    if(match&&allowed.has(match[1]))return url
    if(/^https:\/\/[^\s]+$/i.test(url))return url
    return ''
  }
  const heading=(line:number|undefined)=>article.headings.find(item=>item.line===line)?.id
  return <div className="help-prose"><Markdown remarkPlugins={[remarkGfm]} skipHtml urlTransform={link}
    allowedElements={['p','h2','h3','h4','a','ol','ul','li','strong','em','blockquote','pre','code','table','thead','tbody','tr','th','td','hr','del','br']}
    components={{
      h2:({node,children})=><h2 id={heading(node?.position?.start.line)}>{children}</h2>,
      h3:({node,children})=><h3 id={heading(node?.position?.start.line)}>{children}</h3>,
      h4:({node,children})=><h4 id={heading(node?.position?.start.line)}>{children}</h4>,
      pre:({children})=><CodeBlock>{children}</CodeBlock>,
      table:({children})=><div className="help-table-wrap"><table>{children}</table></div>,
      a:({href,children})=>!href?<span>{children}</span>:href.startsWith('#')?<a href={href}>{children}</a>:href.startsWith('https://')?<a href={href} target="_blank" rel="noopener noreferrer">{children}</a>:<Link to={`${base}/${href}`}>{children}</Link>,
    }}>{article.body}</Markdown></div>
}
