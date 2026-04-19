import { useEffect } from 'react'
import { api } from '@/lib/api'
import { useAppStore } from '@/store/appStore'

export const useUpload = (sessionId: string | null) => {
  const { setFiles, updateFileStatus } = useAppStore()

  useEffect(() => {
    if (!sessionId) return

    // SSE connection for upload progress
    const eventSource = new EventSource(`/api/sessions/${sessionId}/upload/progress`)

    eventSource.onmessage = (event) => {
      try {
        const dataStr = event.data.replace(/'/g, '"') // simple hack if python dict string uses single quotes
        // We should actually make sure the python backend returns proper JSON instead of str(dict)
        // But assuming valid JSON dict: { "filename": "status", ... }
        const progressData = JSON.parse(dataStr)
        
        Object.entries(progressData).forEach(([filename, status]) => {
          updateFileStatus(sessionId, filename, status as string)
        })
      } catch (e) {
        // parsing error
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
    }

    // Initial fetch of sources if we just loaded session
    api.getSources(sessionId).then(files => {
        setFiles(sessionId, files)
    }).catch(console.error)

    return () => {
      eventSource.close()
    }
  }, [sessionId, setFiles, updateFileStatus])

  const upload = async (files: File[]) => {
    if (!sessionId) return
    try {
      await api.uploadFiles(sessionId, files)
    } catch (e) {
      console.error(e)
    }
  }

  return { upload }
}
