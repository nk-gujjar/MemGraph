export interface Session {
  id: string
  created_at: string
  last_active: string
  message_count: number
  tokens_used: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  sources?: Source[]
}

export interface Source {
  filename: string
  page_number?: number | null
  chunk_index?: number
  table_index?: number
}

export interface UploadedFile {
  filename: string
  status: string
  chunk_count: number
  table_count: number
}
