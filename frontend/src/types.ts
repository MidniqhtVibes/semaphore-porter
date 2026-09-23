export type User = {
  id: string
  email: string
  display_name: string
  is_active: boolean
  must_change_password: boolean
  roles: string[]
  last_login_at?: string | null
  created_at?: string
}

export type Tenant = {
  id: string
  tenant_slug: string
  display_name: string
  description: string
  application_id?: string | null
  status: 'draft' | 'active' | 'inactive' | 'deleted'
  configuration_complete?: boolean
  semaphore_project?: { id: number; name: string; last_verified_at?: string | null; last_error?: string | null } | null
  task_templates?: TaskTemplate[]
  memberships?: Array<Record<string, unknown>>
}

export type TaskTemplate = {
  id: string
  semaphore_template_id?: number
  name: string
  description: string
  app: string
  is_enabled?: boolean
  has_policy?: boolean
  can_start?: boolean
  can_stop?: boolean
  survey_schema?: Array<Record<string, unknown>>
}

export type TaskRun = {
  id: string
  tenant_id: string
  tenant: string
  task_template_id: string
  task_template: string
  started_by: string
  status: string
  semaphore_task_id: number
  started_at: string
  finished_at?: string | null
  duration_seconds?: number | null
}

export type ApiErrorBody = { detail?: string | { message?: string; fields?: Record<string, string> } }

