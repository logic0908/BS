import React, { useCallback } from 'react'
import { FileAudio, UploadCloud } from 'lucide-react'

interface FileUploadProps {
  onFileSelect: (file: File) => void
  onError?: (message: string) => void
  disabled?: boolean
}

const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.flac', '.m4a']

function isAudioFile(file: File): boolean {
  if (file.type.startsWith('audio/')) {
    return true
  }
  const lower = file.name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))
}

const FileUpload: React.FC<FileUploadProps> = ({ onFileSelect, onError, disabled = false }) => {
  const validateAndPass = useCallback(
    (file: File) => {
      if (isAudioFile(file)) {
        onFileSelect(file)
        return
      }
      onError?.('请上传有效音频文件：.wav / .mp3 / .flac / .m4a')
    },
    [onError, onFileSelect],
  )

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (disabled) return
      const file = event.dataTransfer.files?.[0]
      if (file) {
        validateAndPass(file)
      }
    },
    [disabled, validateAndPass],
  )

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
  }

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      validateAndPass(file)
    }
  }

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      className={`upload-dropzone ${disabled ? 'is-disabled' : ''}`}
      aria-disabled={disabled}
    >
      <input
        type="file"
        accept=".wav,.mp3,.flac,.m4a,audio/*"
        onChange={handleInputChange}
        disabled={disabled}
        className="upload-dropzone-input"
        aria-label="选择上传音频文件"
      />

      <div className="upload-dropzone-icon">
        {disabled ? <FileAudio className="icon-28" /> : <UploadCloud className="icon-28" />}
      </div>
      <div className="upload-dropzone-title">点击或拖拽上传音频</div>
      <div className="upload-dropzone-text">支持 wav / mp3 / flac / m4a，建议上传 10-30 秒干声片段</div>
    </div>
  )
}

export default FileUpload
