import { useEffect } from 'react'
import { api } from '@/lib/api'
import { useAppStore } from '@/store/appStore'

export const useUpload = (sessionId: string | null) => {
  const { setFiles, updateFileStatus, setIsUploading } = useAppStore()

  useEffect(() => {
    if (!sessionId) return

    // SSE connection for upload progress
    const eventSource = new EventSource(`/api/sessions/${sessionId}/upload/progress`)

    eventSource.onmessage = (event) => {
      try {
        const progressData = JSON.parse(event.data)
        
        Object.entries(progressData).forEach(([filename, status]) => {
          updateFileStatus(sessionId, filename, status as string)
        })
      } catch (e) {
        console.error('Failed to parse SSE data:', e)
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

  const upload = async (files: File[], descriptions?: string[]) => {
    if (!sessionId) return
    setIsUploading(true)
    try {
      const response = await api.uploadFiles(sessionId, files, descriptions)
      // Immediately update local state with returned files so UI transitions
      setFiles(sessionId, response.files)
    } catch (e) {
      console.error(e)
    } finally {
      setIsUploading(false)
    }
  }

  return { upload }
}
