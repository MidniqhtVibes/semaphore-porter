import { Link } from 'react-router-dom'
import { useTheme } from '../designs/ThemeProvider'
import { DEFAULT_LEGAL } from '../designs/themes'

export function SiteFooter() {
  const {active}=useTheme()
  const legal={...DEFAULT_LEGAL,...active.legal}
  return <footer className="site-footer">
    {legal.footer&&<span>{legal.footer}</span>}
    {(legal.imprint.trim()||legal.privacy.trim())&&<nav aria-label="Rechtliche Informationen">
      {legal.imprint.trim()&&<Link to="/impressum">Impressum</Link>}
      {legal.privacy.trim()&&<Link to="/datenschutz">Datenschutz</Link>}
    </nav>}
  </footer>
}
