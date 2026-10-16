import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { LockKeyhole, UserRound } from 'lucide-react'
import { z } from 'zod'
import { useAuth } from '../auth'
import { ApiError } from '../api'
import { Button, Notice } from '../components/ui'
import { BrandMark } from '../components/BrandMark'
import { SiteFooter } from '../components/SiteFooter'

const schema = z.object({ identifier: z.string().trim().min(1, 'Benutzername oder E-Mail-Adresse fehlt.').max(320), password: z.string().min(1, 'Passwort fehlt.') })
type FormData = z.infer<typeof schema>

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({ resolver: zodResolver(schema) })
  const submit = async (values: FormData) => {
    setError('')
    try {
      const user = await login(values.identifier, values.password)
      navigate(user.roles.includes('system_admin') ? '/admin' : '/portal', { replace: true })
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Anmeldung nicht möglich.') }
  }
  return <div className="login-page">
    <section className="login-intro"><div className="brand brand-large"><BrandMark size={26}/><div><strong>Semaphore</strong><span>Tenant Portal</span></div></div><div className="login-copy"><h1>Deployments starten.<br/><em>Sicher getrennt.</em></h1><p>Eine zentrale Oberfläche für Mandanten, Anwendungen und freigegebene Semaphore-Tasks.</p></div></section>
    <section className="login-panel"><form className="login-card" onSubmit={handleSubmit(submit)}><div><h2>Willkommen zurück</h2><p>Melden Sie sich mit Ihrem lokalen Portalkonto an.</p></div>{error && <Notice type="error">{error}</Notice>}
      <label className="field"><span className="field-label">Benutzername oder E-Mail-Adresse</span><div className="input-icon"><UserRound size={17}/><input autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus {...register('identifier')} placeholder="benutzername oder name@unternehmen.de"/></div>{errors.identifier && <span className="field-error">{errors.identifier.message}</span>}</label>
      <label className="field"><span className="field-label">Passwort</span><div className="input-icon"><LockKeyhole size={17}/><input type="password" autoComplete="current-password" {...register('password')}/></div>{errors.password && <span className="field-error">{errors.password.message}</span>}</label>
      <Button type="submit" loading={isSubmitting}>Sicher anmelden</Button><p className="login-note">Bei wiederholten Fehlversuchen wird die Anmeldung vorübergehend begrenzt.</p>
    </form></section>
    <SiteFooter/>
  </div>
}

