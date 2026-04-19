import { useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/store/appStore'

export const useChat = (sessionId: string | null) => {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const { addMessage, appendToken, setSources, setIsStreaming } = useAppStore()

  useEffect(() => {
    if (!sessionId) return

    const connect = () => {
      // Relative path if served from same origin, or specify proxy host if dev
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`
      
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        setIsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'token') {
            appendToken(sessionId, data.content)
          } else if (data.type === 'source') {
            try {
              const src = JSON.parse(data.content)
              // We need to attach this to the last message, but for simplicity we'll handle this in store or UI
              // Here we just trigger an update
              // To update last message, let's grab last message ID
              const state = useAppStore.getState()
              const msgs = state.messages[sessionId] || []
              if (msgs.length > 0) {
                 useAppStore.getState().setSources(sessionId, msgs[msgs.length-1].id, src)
              }
            } catch (e) {}
          } else if (data.type === 'done') {
            setIsStreaming(false)
          } else if (data.type === 'error') {
            setIsStreaming(false)
            addMessage(sessionId, { id: Date.now().toString(), role: 'assistant', content: `Error: ${data.content}` })
          }
        } catch (e) {
          console.error('WebSocket message parsing error', e)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        setIsStreaming(false)
        // Automatic reconnect logic could go here
        setTimeout(connect, 3000)
      }

      wsRef.current = ws
    }

    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [sessionId, addMessage, appendToken, setSources, setIsStreaming])

  const sendMessage = (query: string) => {
    if (!sessionId || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    
    // Add user message to UI
    addMessage(sessionId, { id: Date.now().toString(), role: 'user', content: query })
    
    // Add empty assistant message to append to
    addMessage(sessionId, { id: (Date.now() + 1).toString(), role: 'assistant', content: '' })
    
    setIsStreaming(true)
    
    wsRef.current.send(JSON.stringify({ query }))
  }

  return { sendMessage, isConnected }
}
