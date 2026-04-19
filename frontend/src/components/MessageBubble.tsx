import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message } from '@/types'
import { Bot, User } from 'lucide-react'

interface MessageBubbleProps {
  message: Message
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user'

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className={`flex max-w-[85%] gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        
        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center 
          ${isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground border border-border'}`}>
          {isUser ? <User size={16} /> : <Bot size={16} />}
        </div>
        
        <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
          <div className={`px-5 py-3 rounded-2xl ${
            isUser ? 'bg-primary text-primary-foreground rounded-tr-sm' : 'bg-muted/50 border border-border rounded-tl-sm text-foreground'
          }`}>
            <div className="prose prose-sm dark:prose-invert max-w-none break-words">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          </div>
          
          {message.intent && !isUser && (
            <span className="text-[10px] px-2 py-0.5 mt-1 rounded-full bg-secondary text-secondary-foreground border border-border inline-block capitalize">
              Intent: {message.intent}
            </span>
          )}
        </div>
        
      </div>
    </div>
  )
}
