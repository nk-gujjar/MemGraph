import { Session, UploadedFile } from '@/types'

export const api = {
  createSession: async (): Promise<{ session_id: string }> => {
    const res = await fetch('/api/sessions', { method: 'POST' })
    if (!res.ok) throw new Error('Failed to create session')
    return res.json()
  },

  listSessions: async (): Promise<Session[]> => {
    const res = await fetch('/api/sessions')
    if (!res.ok) throw new Error('Failed to list sessions')
    return res.json()
  },

  deleteSession: async (sessionId: string): Promise<void> => {
    const res = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('Failed to delete session')
  },

  uploadFiles: async (sessionId: string, files: File[], descriptions?: string[]): Promise<{ files: UploadedFile[] }> => {
    const formData = new FormData()
    files.forEach(f => formData.append('files', f))
    if (descriptions) {
      descriptions.forEach(d => formData.append('descriptions', d))
    }
    
    const res = await fetch(`/api/sessions/${sessionId}/upload`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) throw new Error('Failed to upload files')
    return res.json()
  },
  
  getSources: async (sessionId: string): Promise<UploadedFile[]> => {
    const res = await fetch(`/api/sessions/${sessionId}/sources`)
    if (!res.ok) throw new Error('Failed to get sources')
    return res.json()
  }
}
