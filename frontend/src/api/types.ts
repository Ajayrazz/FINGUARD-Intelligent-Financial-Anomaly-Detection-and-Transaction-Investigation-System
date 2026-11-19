export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface User {
  id: number
  email: string
  full_name: string
  role: string
  role_label: string
  is_active: boolean
  last_login: string | null
  created_at: string
}

export interface Me extends User {
  permissions: string[]
}

export interface Role {
  id: number
  name: string
  label: string
  description: string
  is_system: boolean
  permissions: string[]
}

export interface PermissionInfo {
  codename: string
  description: string
}

export interface AuditLogEntry {
  id: number
  created_at: string
  actor: number | null
  actor_email: string
  action: string
  resource_type: string
  resource_id: string
  ip_address: string | null
  request_id: string
  changes: Record<string, unknown>
}
