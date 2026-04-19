import React from 'react'
import { SessionSidebar } from '@/components/SessionSidebar'
import { ChatWindow } from '@/components/ChatWindow'

function App() {
  return (
    <div className="flex w-screen h-screen bg-background overflow-hidden text-foreground">
      <SessionSidebar />
      <ChatWindow />
    </div>
  )
}

export default App
