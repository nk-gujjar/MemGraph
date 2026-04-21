import React, { useState, useCallback, useEffect } from 'react'
import { Upload, FileText, X, CheckCircle2, Clock, Trash2, Loader, UploadCloud } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { useUpload } from '@/hooks/useUpload'
import { useAppStore } from '@/store/appStore'
import { api } from '@/lib/api'

export const FileUploader: React.FC = () => {
  const activeSessionId = useAppStore(state => state.activeSessionId)
  const uploadedFiles = useAppStore(state => state.uploadedFiles)
  const isStoreUploading = useAppStore(state => state.isUploading)
  const currentFiles = activeSessionId ? uploadedFiles[activeSessionId] || [] : []
  
  const { upload, isUploading: isApiUploading } = useUpload(activeSessionId || '')
  const [stagedFiles, setStagedFiles] = useState<File[]>([])
  const [descriptions, setDescriptions] = useState<Record<string, string>>({})

  const isUploading = isStoreUploading || isApiUploading

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setStagedFiles(prev => [...prev, ...acceptedFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: isUploading,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/markdown': ['.md']
    }
  })

  const removeStaged = (index: number) => {
    setStagedFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleDescChange = (name: string, val: string) => {
    setDescriptions(prev => ({ ...prev, [name]: val }))
  }

  const handleUpload = async () => {
    if (stagedFiles.length > 0) {
      const descList = stagedFiles.map(f => descriptions[f.name] || '')
      await upload(stagedFiles, descList)
      setStagedFiles([])
      setDescriptions({})
    }
  }

  // If session is totally empty, show a large welcome dropzone
  const isSessionEmpty = currentFiles.length === 0 && stagedFiles.length === 0

  return (
    <div className="w-full flex flex-col gap-6">
      {/* Dropzone Area */}
      <div 
        {...getRootProps()} 
        className={`border-2 border-dashed rounded-2xl p-8 bg-card/50 flex flex-col items-center justify-center transition-all cursor-pointer shadow-sm
          ${isDragActive ? 'border-primary bg-primary/10' : 'border-border hover:bg-muted/50'}
          ${isSessionEmpty ? 'py-20' : 'py-8'}`}
      >
        <input {...getInputProps()} />
        <div className="w-14 h-14 bg-primary/10 rounded-full flex items-center justify-center mb-4 transition-transform group-hover:scale-110">
           <UploadCloud className="w-7 h-7 text-primary" />
        </div>
        <h3 className="text-lg font-semibold mb-1">
          {isSessionEmpty ? "Upload your knowledge base" : "Add more documents"}
        </h3>
        <p className="text-sm text-muted-foreground text-center max-w-xs">
          Drag & drop PDF, DOCX, TXT, or MD files here to start indexing.
        </p>
      </div>

      {/* Staged Files for Upload */}
      {stagedFiles.length > 0 && (
        <div className="flex flex-col gap-3">
           <h4 className="text-xs font-bold uppercase tracking-widest text-primary flex items-center gap-2 px-1">
             <Upload className="w-3.5 h-3.5" /> Pending Upload ({stagedFiles.length})
           </h4>
           <div className="space-y-3">
              {stagedFiles.map((file, i) => (
                <div key={i} className="bg-background border border-primary/20 rounded-xl p-3 shadow-sm flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                     <div className="flex items-center gap-3 truncate">
                        <FileText className="w-4 h-4 text-primary" />
                        <span className="text-sm font-medium truncate">{file.name}</span>
                     </div>
                     <button onClick={() => removeStaged(i)} className="text-muted-foreground hover:text-destructive transition-colors p-1">
                        <X className="w-4 h-4" />
                     </button>
                  </div>
                  <input 
                     type="text" 
                     placeholder="What's inside? (e.g. 2024 Budget Summary)"
                     value={descriptions[file.name] || ''}
                     onChange={(e) => handleDescChange(file.name, e.target.value)}
                     className="text-xs bg-muted/30 border-none outline-none focus:ring-1 focus:ring-primary/30 rounded-lg p-2"
                  />
                </div>
              ))}
              <button 
                onClick={handleUpload}
                disabled={isUploading}
                className="w-full py-3 bg-primary text-primary-foreground rounded-xl font-bold shadow-lg hover:shadow-primary/20 transition-all active:scale-[0.98] disabled:opacity-50 mt-2 flex items-center justify-center gap-2"
              >
                {isUploading ? <Loader className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                {isUploading ? "Ingesting..." : "Start Ingestion"}
              </button>
           </div>
        </div>
      )}

      {/* Indexed Session Documents */}
      {currentFiles.length > 0 && (
        <div className="flex flex-col gap-3">
           <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2 px-1">
             <Clock className="w-3.5 h-3.5" /> Indexed Knowledge ({currentFiles.length})
           </h4>
           <div className="grid grid-cols-1 gap-2 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
             {currentFiles.map((f, i) => (
               <div key={i} className="flex items-center justify-between p-3 bg-muted/20 border border-border/50 rounded-xl group hover:bg-muted/40 transition-all">
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${f.status === 'completed' ? 'bg-success/10' : 'bg-primary/10'}`}>
                      {f.status === 'completed' ? (
                        <CheckCircle2 className="w-4 h-4 text-success" />
                      ) : (
                        <Loader className="w-4 h-4 text-primary animate-spin" />
                      )}
                    </div>
                    <div className="flex flex-col truncate">
                       <span className="text-sm font-medium truncate">{f.filename}</span>
                       <span className="text-[10px] text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                         {f.status === 'completed' ? (
                           <>
                             <span className="text-success/80 font-bold">Ready</span>
                             <span>•</span>
                             <span>{f.chunk_count} Chunks</span>
                             <span>•</span>
                             <span>{f.table_count} Tables</span>
                           </>
                         ) : (
                           <span className="animate-pulse">Vectorizing Content...</span>
                         )}
                       </span>
                    </div>
                  </div>
                  <button className="opacity-0 group-hover:opacity-100 p-2 hover:bg-destructive/10 hover:text-destructive rounded-lg transition-all text-muted-foreground">
                     <Trash2 size={14} />
                  </button>
               </div>
             ))}
           </div>
        </div>
      )}
    </div>
  )
}
