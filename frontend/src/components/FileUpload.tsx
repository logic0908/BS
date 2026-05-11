import React, { useCallback } from 'react'
import { FileAudio, UploadCloud } from 'lucide-react'

interface FileUploadProps {
  onFileSelect: (file: File) => void
  disabled?: boolean
}

const FileUpload: React.FC<FileUploadProps> = ({ onFileSelect, disabled = false }) => {
  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (disabled) return
      if (event.dataTransfer.files && event.dataTransfer.files[0]) {
        validateAndPass(event.dataTransfer.files[0])
      }
    },
    [disabled],
  )

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
  }

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      validateAndPass(event.target.files[0])
    }
  }

  const validateAndPass = (file: File) => {
    if (file.type.startsWith('audio/') || file.name.endsWith('.wav') || file.name.endsWith('.mp3')) {
      onFileSelect(file)
    } else {
      alert('请上传有效的音频文件（.mp3 或 .wav）。')
    }
  }

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      className={`upload-dropzone ${disabled ? 'is-disabled' : ''}`}
    >
      <input
        type="file"
        accept=".mp3,.wav"
        onChange={handleInputChange}
        disabled={disabled}
        className="upload-dropzone-input"
      />

      <div className="upload-dropzone-icon">
        {disabled ? <FileAudio className="icon-28" /> : <UploadCloud className="icon-28" />}
      </div>
      <div className="upload-dropzone-title">点击或拖拽上传音频</div>
      <div className="upload-dropzone-text">支持 wav/mp3，建议上传 10–30 秒人声片段</div>
    </div>
  )
}

export default FileUpload
