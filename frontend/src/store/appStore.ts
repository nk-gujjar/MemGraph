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
  updateSessionStats: (sessionId: string, tokens: { total: number, input: number, output: number }) => void
  patchFile: (sessionId: string, filename: string, patch: Partial<UploadedFile>) => void
  setMessages: (sessionId: string, messages: Message[]) => void
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

  setFiles: (sessionId, files) => set((state) => {
    const existing = state.uploadedFiles[sessionId] || []
    // Merge new files into existing, replacing by filename if exists
    const fileMap = new Map(existing.map(f => [f.filename, f]));
    files.forEach(f => fileMap.set(f.filename, f));
    
    return {
      uploadedFiles: { 
        ...state.uploadedFiles, 
        [sessionId]: Array.from(fileMap.values()) 
      }
    }
  }),

  updateFileStatus: (sessionId, filename, status) => set((state) => {
    const files = state.uploadedFiles[sessionId] || []
    return {
      uploadedFiles: {
        ...state.uploadedFiles,
        [sessionId]: files.map(f => f.filename === filename ? { ...f, status } : f)
      }
    }
  }),

  // New robust update that handles metadata
  patchFile: (sessionId, filename, patch) => set((state) => {
    const files = state.uploadedFiles[sessionId] || []
    return {
      uploadedFiles: {
        ...state.uploadedFiles,
        [sessionId]: files.map(f => f.filename === filename ? { ...f, ...patch } : f)
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

  setMessages: (sessionId, messages) => set((state) => {
    // Safety merge: Only overwrite if we aren't streaming, or if the incoming list is meaningful
    const currentMsgs = state.messages[sessionId] || []
    
    // If we're streaming, we ALREADY have the latest messages via appendToken
    // Blindly taking DB state here might roll back the last few tokens.
    if (state.isStreaming) {
       return state;
    }
    
    // If the list is empty and we have data, double check it's not a race
    if (messages.length === 0 && currentMsgs.length > 0) {
        return state;
    }

    return {
      messages: {
        ...state.messages,
        [sessionId]: messages
      }
    }
  }),

  appendToken: (sessionId, token) => set((state) => {
    const msgs = state.messages[sessionId] || []
    
    // Find last assistant message to append to
    const lastAssistantIdx = [...msgs].reverse().findIndex(m => m.role === 'assistant')
    
    if (lastAssistantIdx === -1) {
      // If no assistant message exists yet, create one (this handles extreme race conditions)
      const newMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: token
      }
      return {
        messages: {
          ...state.messages,
          [sessionId]: [...msgs, newMessage]
        }
      }
    }

    const actualIdx = msgs.length - 1 - lastAssistantIdx
    const updatedMsgs = [...msgs]
    updatedMsgs[actualIdx] = {
      ...updatedMsgs[actualIdx],
      content: updatedMsgs[actualIdx].content + token
    }
    
    return {
      messages: {
        ...state.messages,
        [sessionId]: updatedMsgs
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
  
  setIsUploading: (status: boolean) => set({ isUploading: status }),

  updateSessionStats: (sessionId, tokens) => set((state) => ({
    sessions: state.sessions.map(s => s.id === sessionId ? {
      ...s,
      tokens_used: tokens.total,
      input_tokens: tokens.input,
      output_tokens: tokens.output
    } : s)
  }))
}))
