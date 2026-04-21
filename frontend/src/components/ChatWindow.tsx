import React, { useState, useEffect, useRef } from 'react'
import { Send, Sparkles, Loader } from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import { useChat } from '@/hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { SourceCitations } from './SourceCitations'
import { FileUploader } from './FileUploader'

export const ChatWindow: React.FC = () => {
  const activeSessionId = useAppStore(state => state.activeSessionId)
  const messages = useAppStore(state => state.messages)
  const isStreaming = useAppStore(state => state.isStreaming)
  const uploadedFiles = useAppStore(state => state.uploadedFiles)
  const isUploading = useAppStore(state => state.isUploading)
  
  const { sendMessage, isConnected } = useChat(activeSessionId)
  
  const [input, setInput] = useState('')
  const msgs = activeSessionId ? messages[activeSessionId] || [] : []
  const files = activeSessionId ? uploadedFiles[activeSessionId] || [] : []
  
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  if (!activeSessionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background/50 h-full p-8 text-center">
         <Sparkles className="w-16 h-16 text-muted-foreground/30 mb-6" />
         <h1 className="text-3xl font-bold tracking-tight text-foreground/80 mb-2">Welcome to MemGraph</h1>
         <p className="text-muted-foreground max-w-lg mb-8">
           Select or create a new session to begin interacting with your knowledge base.
         </p>
      </div>
    )
  }

  // If session is active but no files and no messages, show uploader heavily
  // If session is active but no files and no messages, show uploader heavily
  // FIX: If we are streaming, we are NOT in an empty state even if msgs.length is 0
  const showEmptyState = msgs.length === 0 && files.length === 0 && !isUploading && !isStreaming
  const isAnyFileProcessing = files.some(f => f.status === 'processing')
  const isAtLeastOneFileReady = files.some(f => f.status === 'completed')
  const isAtLeastOneFilePresent = files.length > 0

  const handleSend = () => {
    if (input.trim() && !isStreaming) {
      sendMessage(input.trim())
      setInput('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSuggestion = (q: string) => {
    if (!isStreaming) {
      sendMessage(q)
    }
  }

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      <div className="flex-1 flex flex-col bg-background relative relative">
        
        {/* Offline indicator */}
        {!isConnected && (
           <div className="absolute top-0 inset-x-0 bg-destructive text-destructive-foreground text-xs font-semibold py-1 px-4 text-center z-10 shadow-sm">
             Connecting to chat server...
           </div>
        )}

        {/* Message Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 custom-scrollbar scroll-smooth flex flex-col">
          {showEmptyState ? (
            <div className="flex-1 flex items-center justify-center w-full max-w-2xl mx-auto">
               <FileUploader />
            </div>
          ) : (
            <div className="max-w-3xl mx-auto w-full pb-8">
              {msgs.length === 0 ? (
                 <div className="py-20 text-center flex flex-col items-center">
                    {(isAnyFileProcessing && !isAtLeastOneFileReady) ? (
                        <>
                          <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6 animate-pulse">
                             <Loader className="w-8 h-8 text-primary animate-spin" />
                          </div>
                          <h3 className="text-xl font-semibold mb-2">Processing Documents...</h3>
                          <p className="text-muted-foreground mb-8">We're indexing your knowledge base. This will only take a moment.</p>
                        </>
                    ) : (
                        <>
                          <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mb-6">
                             <Sparkles className="w-8 h-8 text-primary" />
                          </div>
                          <h3 className="text-xl font-semibold mb-2">Upload complete!</h3>
                          <p className="text-muted-foreground mb-8">Your documents are ready. You can now ask questions about them.</p>
                        </>
                    )}
                    
                    <div className="flex flex-wrap items-center justify-center gap-3">
                       {["Summarize this document", "What are the key tables?", "What are the main findings?"].map(s => (
                         <button 
                           key={s} 
                           onClick={() => handleSuggestion(s)}
                           className="text-sm px-4 py-2 rounded-full border border-primary/20 bg-primary/5 text-primary hover:bg-primary hover:text-primary-foreground transition-colors custom-focus"
                         >
                           {s}
                         </button>
                       ))}
                    </div>
                 </div>
              ) : (
                msgs.map((m, i) => (
                  <div key={m.id}>
                    <MessageBubble message={m} />
                    {/* Render Sources for assistant responses if they exist */}
                    {m.role === 'assistant' && m.sources && m.sources.length > 0 && (
                      <SourceCitations sources={m.sources} />
                    )}
                  </div>
                ))
              )}
              {/* Always show loader if streaming and last message is potentially incomplete */}
              {isStreaming && (
                 <div className="flex gap-1 ml-14 mb-4 items-center h-8">
                    <div className="flex gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-bounce"></div>
                    </div>
                    <span className="text-[10px] text-muted-foreground ml-2 animate-pulse">Generating response...</span>
                 </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-4 sm:p-6 bg-background/80 backdrop-blur-sm border-t border-border">
          <div className="max-w-3xl mx-auto relative flex items-end shadow-sm border border-border/60 bg-card rounded-2xl overflow-hidden focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/40 transition-all">
            <textarea 
               value={input}
               onChange={(e) => setInput(e.target.value)}
               onKeyDown={handleKeyDown}
               placeholder="Chat with MemGraph... (Press Enter to send)"
               className="w-full max-h-32 min-h-[56px] py-4 pl-4 pr-14 bg-transparent outline-none resize-none disabled:opacity-50 CustomScrollbar"
               disabled={isStreaming || !isConnected || !activeSessionId}
               rows={1}
            />
            <button 
               onClick={handleSend}
               disabled={isStreaming || !input.trim() || !isConnected || !activeSessionId}
               className="absolute right-2 bottom-2 p-2 rounded-xl bg-primary text-primary-foreground disabled:opacity-50 disabled:bg-muted disabled:text-muted-foreground transition-all hover:scale-105 active:scale-95"
            >
              <Send size={18} />
            </button>
          </div>
          <div className="max-w-3xl mx-auto text-center mt-2">
            <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-widest opacity-60">Powered by Cohere command-r-plus</span>
          </div>
        </div>

      </div>
      
      {/* Right panel logic if needed, currently embedded locally inside Message Area or can be a right sidebar */}
      {(!showEmptyState || isUploading) && (
        <div className="hidden lg:block w-[300px] border-l border-border bg-muted/10 p-4 overflow-y-auto">
          <FileUploader />
        </div>
      )}
    </div>
  )
}
