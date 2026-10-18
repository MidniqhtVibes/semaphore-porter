import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useTheme } from '../designs/ThemeProvider'
import { DEFAULT_COPY } from '../designs/themes'
import { BrandMark } from '../components/BrandMark'
import { LegalContent, type LegalPageId } from '../components/LegalContent'
import { SiteFooter } from '../components/SiteFooter'

export function LegalPage({page}:{page:LegalPageId}) {
  const {active}=useTheme()
  const copy={...DEFAULT_COPY,...active.copy}
  const text=active.legal?.[page]||''
  return <div className="legal-page">
    <header><Link to="/" className="brand"><BrandMark/><div><strong>{copy.title}</strong><span>{copy.subtitle}</span></div></Link>
      <Link to="/" className="button button-secondary"><ArrowLeft size={16}/>Zum Portal</Link>
    </header>
    <main>{text.trim()?<LegalContent page={page} text={text} heading="h1"/>:<article className="legal-content"><h1>{page==='imprint'?'Impressum':'Datenschutz'}</h1><p>Für dieses Design ist noch kein Text hinterlegt.</p></article>}</main>
    <SiteFooter/>
  </div>
}
