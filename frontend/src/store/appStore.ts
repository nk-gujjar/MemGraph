import { create } from 'zustand'
import { Session, Message, UploadedFile } from '@/types'

interface AppState {
  sessions: Session[]
  activeSessionId: string | null
  messages: Record<string, Message[]>
  uploadedFiles: Record<string, UploadedFile[]>
  isStreaming: boolean
  isUploading: boolean
  setSessions: (sessions: Session[]) => void
  addSession: (session: Session) => void
  removeSession: (id: string) => void
  setActiveSession: (id: string | null) => void
  setFiles: (sessionId: string, files: UploadedFile[]) => void
  updateFileStatus: (sessionId: string, filename: string, status: string) => void
  addMessage: (sessionId: string, message: Message) => void
  appendToken: (sessionId: string, token: string) => void
  setSources: (sessionId: string, messageId: string, sources: any[]) => void
  setIsStreaming: (status: boolean) => void
  setIsUploading: (status: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  sessions: [],
  activeSessionId: null,
  messages: {},
  uploadedFiles: {},
  isStreaming: false,
  isUploading: false,

  setSessions: (sessions) => set({ sessions }),
  
  addSession: (session) => set((state) => ({
    sessions: [session, ...state.sessions]
  })),

  removeSession: (id) => set((state) => ({
    sessions: state.sessions.filter(s => s.id !== id),
    activeSessionId: state.activeSessionId === id ? null : state.activeSessionId
  })),

  setActiveSession: (id) => set({ activeSessionId: id }),

  setFiles: (sessionId, files) => set((state) => ({
    uploadedFiles: { ...state.uploadedFiles, [sessionId]: files }
  })),

  updateFileStatus: (sessionId, filename, status) => set((state) => {
    const files = state.uploadedFiles[sessionId] || []
    return {
      uploadedFiles: {
        ...state.uploadedFiles,
        [sessionId]: files.map(f => f.filename === filename ? { ...f, status } : f)
      }
    }
  }),

  addMessage: (sessionId, message) => set((state) => {
    const msgs = state.messages[sessionId] || []
    return {
      messages: {
        ...state.messages,
        [sessionId]: [...msgs, message]
      }
    }
  }),

  appendToken: (sessionId, token) => set((state) => {
    const msgs = state.messages[sessionId] || []
    if (msgs.length === 0) return state
    const lastMsg = msgs[msgs.length - 1]
    if (lastMsg.role !== 'assistant') return state
    
    return {
      messages: {
        ...state.messages,
        [sessionId]: [
          ...msgs.slice(0, -1),
          { ...lastMsg, content: lastMsg.content + token }
        ]
      }
    }
  }),

  setSources: (sessionId, messageId, sources) => set((state) => {
    const msgs = state.messages[sessionId] || []
    return {
      messages: {
        ...state.messages,
        [sessionId]: msgs.map(m => m.id === messageId ? { ...m, sources } : m)
      }
    }
  }),

  setIsStreaming: (status) => set({ isStreaming: status }),
  
  setIsUploading: (status) => set({ isUploading: status })
}))
