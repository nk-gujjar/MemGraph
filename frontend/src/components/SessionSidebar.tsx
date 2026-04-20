import React, { useEffect } from 'react'
import { PlusCircle, Search, MessageSquare, Trash2 } from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import { api } from '@/lib/api'

export const SessionSidebar: React.FC = () => {
export const SessionSidebar: React.FC = () => {
  const sessions = useAppStore(state => state.sessions)
  const activeSessionId = useAppStore(state => state.activeSessionId)
  const setSessions = useAppStore(state => state.setSessions)
  const setActiveSession = useAppStore(state => state.setActiveSession)
  const addSession = useAppStore(state => state.addSession)
  const removeSession = useAppStore(state => state.removeSession)

  useEffect(() => {
    // Initial load of sessions
    api.listSessions().then(setSessions).catch(console.error)
  }, [setSessions])

  useEffect(() => {
    // Load files for active session
    if (activeSessionId) {
       api.getSources(activeSessionId)
         .then(files => useAppStore.getState().setFiles(activeSessionId, files))
         .catch(console.error)
    }
  }, [activeSessionId])

  const handleNewSession = async () => {
    try {
      const res = await api.createSession()
      const newSess = {
        id: res.session_id,
        created_at: new Date().toISOString(),
        last_active: new Date().toISOString(),
        message_count: 0,
        tokens_used: 0
      }
      addSession(newSess)
      setActiveSession(newSess.id)
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.deleteSession(id)
      removeSession(id)
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="w-[260px] h-full bg-muted/20 border-r border-border flex flex-col">
      <div className="p-4 flex items-center justify-between border-b border-border">
        <h2 className="font-bold text-lg tracking-tight flex items-center gap-2">
          <Search className="w-5 h-5 text-primary" /> MemGraph
        </h2>
      </div>

      <div className="p-3">
        <button 
          onClick={handleNewSession}
          className="w-full flex items-center justify-center gap-2 p-2.5 bg-primary text-primary-foreground rounded-md text-sm font-medium transition-transform hover:scale-[1.02] active:scale-[0.98]"
        >
          <PlusCircle className="w-4 h-4" /> New Session
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 ml-1">Recent</h3>
        {sessions.map(s => (
          <div 
            key={s.id} 
            onClick={() => setActiveSession(s.id)}
            className={`group relative flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors
              ${activeSessionId === s.id ? 'bg-muted border border-border/50' : 'hover:bg-muted/40 border border-transparent'}
            `}
          >
            <MessageSquare className={`w-4 h-4 flex-shrink-0 ${activeSessionId === s.id ? 'text-primary' : 'text-muted-foreground'}`} />
            <div className="flex-1 overflow-hidden">
              <p className="text-sm font-medium truncate text-foreground">
                 {s.id.split('-')[0]}
              </p>
              <p className="text-xs text-muted-foreground truncate flex flex-col gap-0.5 w-full mt-1">
                 <span className="flex justify-between w-full">
                    <span>{new Date(s.last_active).toLocaleDateString()}</span>
                    <span>{s.message_count} msgs</span>
                 </span>
                 <span className="flex justify-between w-full font-mono opacity-80 scale-[0.9] origin-left">
                    <span>Tokens: {s.tokens_used}</span>
                    <span className="text-[10px] bg-muted px-1 rounded">I:{s.input_tokens} O:{s.output_tokens}</span>
                 </span>
              </p>
            </div>
            
            <button 
              onClick={(e) => handleDelete(s.id, e)}
              className="absolute right-2 p-1.5 rounded-md text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity hover:bg-destructive hover:text-destructive-foreground hover:border-transparent cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
