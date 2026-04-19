import React, { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { UploadCloud, File, Loader } from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import { useUpload } from '@/hooks/useUpload'

export const FileUploader: React.FC = () => {
  const { activeSessionId, uploadedFiles } = useAppStore()
  const { upload } = useUpload(activeSessionId)
  
  const files = activeSessionId ? uploadedFiles[activeSessionId] || [] : []

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        upload(acceptedFiles)
      }
    },
    [upload]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/markdown': ['.md']
    }
  })

  // Full page dropzone if no files
  if (files.length === 0) {
    return (
      <div 
        {...getRootProps()} 
        className={`h-full w-full border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-12 transition-colors cursor-pointer
          ${isDragActive ? 'border-primary bg-primary/10' : 'border-border hover:bg-muted/50'}`}
      >
        <input {...getInputProps()} />
        <UploadCloud className="w-16 h-16 text-muted-foreground mb-4" />
        <h3 className="text-xl font-semibold mb-2">Upload Knowledge Documents</h3>
        <p className="text-muted-foreground text-center max-w-md">
          Drag and drop PDF, DOCX, TXT, CSV, XLSX, or MD files here, or click to browse.
        </p>
      </div>
    )
  }

  // Mini uploader when we have files
  return (
    <div className="flex flex-col gap-4">
      <div 
        {...getRootProps()} 
        className={`p-4 border-2 border-dashed rounded-lg flex items-center justify-center cursor-pointer transition-colors
          ${isDragActive ? 'border-primary bg-primary/10' : 'border-border hover:bg-muted/50'}`}
      >
         <input {...getInputProps()} />
         <span className="text-sm text-muted-foreground flex items-center gap-2">
           <UploadCloud className="w-4 h-4" /> Add more documents
         </span>
      </div>

      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Indexed Documents</h4>
        {files.map(f => (
          <div key={f.filename} className="flex items-center justify-between p-3 rounded-md bg-muted/30 border border-border">
            <div className="flex items-center gap-3 overflow-hidden">
              <File className="w-5 h-5 text-primary flex-shrink-0" />
              <div className="truncate">
                <p className="text-sm font-medium truncate">{f.filename}</p>
                {f.status === 'completed' ? (
                  <p className="text-xs text-muted-foreground">{f.chunk_count} chunks • {f.table_count} tables</p>
                ) : (
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                     <Loader className="w-3 h-3 animate-spin" /> Processing...
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
