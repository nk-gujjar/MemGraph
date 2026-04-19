import React from 'react'
import { Source } from '@/types'
import { FileText, TableProperties } from 'lucide-react'

interface SourceCitationsProps {
  sources: Source[]
}

export const SourceCitations: React.FC<SourceCitationsProps> = ({ sources }) => {
  if (!sources || sources.length === 0) return null

  // Deduplicate sources by filename and page/table
  const uniqueSources = sources.reduce((acc: Source[], cur) => {
    const key = `${cur.filename}-${cur.page_number || 'none'}-${cur.table_index !== undefined ? cur.table_index : 'text'}`
    const exists = acc.find(s => 
      `${s.filename}-${s.page_number || 'none'}-${s.table_index !== undefined ? s.table_index : 'text'}` === key
    )
    if (!exists) {
      acc.push(cur)
    }
    return acc
  }, [])

  return (
    <div className="flex flex-col gap-2 mt-4 px-12">
      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Sources</h4>
      <div className="flex flex-wrap gap-2">
        {uniqueSources.map((s, i) => (
          <div key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-muted border border-border text-xs transition-colors hover:bg-muted/80 cursor-default">
            {s.table_index !== undefined ? (
              <TableProperties size={12} className="text-primary" />
            ) : (
              <FileText size={12} className="text-primary" />
            )}
            <span className="font-medium text-foreground truncate max-w-[150px]" title={s.filename}>{s.filename}</span>
            {s.page_number && <span className="text-muted-foreground ml-1">p. {s.page_number}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
