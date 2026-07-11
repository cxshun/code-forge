export interface McpOut {
  id: number
  name: string
  type: 'stdio' | 'http'
  config: Record<string, unknown>
  owner_id: number
  visibility: 'private' | 'public'
  read_only: boolean
}

export interface McpCreateIn {
  name: string
  type: 'stdio' | 'http'
  config: Record<string, unknown>
  visibility?: 'private' | 'public'
  read_only?: boolean
}

export interface McpPatchIn {
  name?: string
  config?: Record<string, unknown>
  visibility?: 'private' | 'public'
  read_only?: boolean
}
