import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import { Layout } from './components/Layout'
import { Loading, Notice } from './components/ui'
import { LoginPage } from './pages/LoginPage'
import { AdminDashboardPage } from './pages/admin/DashboardPage'
import { ApplicationsPage, PresetsPage, ProjectTemplatesPage } from './pages/admin/CatalogPages'
import { AuditPage, AdminTasksPage, PermissionsPage } from './pages/admin/OpsPages'
import { SemaphorePage } from './pages/admin/SemaphorePage'
import { TenantDetailPage, TenantsPage } from './pages/admin/TenantsPage'
import { TenantWizardPage } from './pages/admin/TenantWizardPage'
import { UsersPage } from './pages/admin/UsersPage'
import {
  AccountPage, MyProjectsPage, PortalDashboardPage, ProjectDetailPage, RunDetailPage,
  RunsPage, TaskStartPage,
} from './pages/portal/PortalPages'

class ErrorBoundary extends Component<{children:ReactNode},{error:string}> {
  state={error:''}
  static getDerivedStateFromError(error:Error){return{error:error.message||'Unbekannter Anwendungsfehler'}}
  componentDidCatch(error:Error,info:ErrorInfo){console.error(error,info)}
  render(){return this.state.error?<div className="fatal"><Notice type="error"><strong>Die Ansicht konnte nicht geladen werden.</strong><br/>{this.state.error}</Notice><button className="button button-secondary" onClick={()=>window.location.reload()}>Neu laden</button></div>:this.props.children}
}

function Protected({admin=false}:{admin?:boolean}){
  const {user,loading,isAdmin}=useAuth(),location=useLocation()
  if(loading)return <div className="app-loading"><Loading label="Portal wird geladen …"/></div>
  if(!user)return <Navigate to="/login" replace state={{from:location}}/>
  if(admin&&!isAdmin)return <Navigate to="/portal" replace/>
  if(user.must_change_password&&location.pathname!=='/portal/konto')return <Navigate to="/portal/konto" replace/>
  return <Outlet/>
}
function AdminShell(){return <Layout mode="admin"><ErrorBoundary><Outlet/></ErrorBoundary></Layout>}
function PortalShell(){return <Layout mode="portal"><ErrorBoundary><Outlet/></ErrorBoundary></Layout>}
function LoginRoute(){const {user,loading,isAdmin}=useAuth();if(loading)return <div className="app-loading"><Loading/></div>;return user?<Navigate to={isAdmin?'/admin':'/portal'} replace/>:<LoginPage/>}

export function App(){return <Routes>
  <Route path="/login" element={<LoginRoute/>}/>
  <Route element={<Protected admin/>}><Route path="/admin" element={<AdminShell/>}>
    <Route index element={<AdminDashboardPage/>}/><Route path="tenants" element={<TenantsPage/>}/><Route path="tenants/:tenantId" element={<TenantDetailPage/>}/><Route path="tenant-erstellen" element={<TenantWizardPage/>}/><Route path="anwendungen" element={<ApplicationsPage/>}/><Route path="vorlagen" element={<ProjectTemplatesPage/>}/><Route path="presets" element={<PresetsPage/>}/><Route path="benutzer" element={<UsersPage/>}/><Route path="berechtigungen" element={<PermissionsPage/>}/><Route path="tasks" element={<AdminTasksPage/>}/><Route path="audit" element={<AuditPage/>}/><Route path="semaphore" element={<SemaphorePage/>}/>
  </Route></Route>
  <Route element={<Protected/>}><Route path="/portal" element={<PortalShell/>}>
    <Route index element={<PortalDashboardPage/>}/><Route path="projekte" element={<MyProjectsPage/>}/><Route path="projekte/:tenantId" element={<ProjectDetailPage/>}/><Route path="projekte/:tenantId/tasks/:taskId" element={<TaskStartPage/>}/><Route path="laufende-tasks" element={<RunsPage runningOnly/>}/><Route path="historie" element={<RunsPage/>}/><Route path="runs/:runId" element={<RunDetailPage/>}/><Route path="konto" element={<AccountPage/>}/>
  </Route></Route>
  <Route path="*" element={<Navigate to="/portal" replace/>}/>
  </Routes>}

