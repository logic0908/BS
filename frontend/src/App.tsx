import { useState, Component } from 'react'
import type { ReactNode } from 'react'
import axios from 'axios'
import { Music, Loader2, Download, Music4, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react'

import { AppStatus } from './types';
import type { AudioFile, ProcessingResult } from './types';
import FileUpload from './components/FileUpload';
import WaveformPlayer from './components/WaveformPlayer';
import StyleControls from './components/StyleControls';

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-red-50 p-4" translate="no">
          <div className="bg-white p-8 rounded-xl shadow-lg border border-red-200 max-w-lg w-full">
            <h2 className="text-xl font-bold text-red-700 mb-4">页面渲染出错了</h2>
            <pre className="text-sm bg-gray-100 p-4 rounded overflow-auto whitespace-pre-wrap">
              {this.state.error?.message}
            </pre>
            <button 
              onClick={() => window.location.reload()}
              className="mt-6 w-full py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              刷新页面
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function App() {
  const [text, setText] = useState("")
  const [styleStrength, setStyleStrength] = useState(0.65)
  const [phSeq, setPhSeq] = useState("")
  const [noteSeq, setNoteSeq] = useState("")
  const [noteDurSeq, setNoteDurSeq] = useState("")
  const [noteTypeSeq, setNoteTypeSeq] = useState("")
  const [isVocalOnly, setIsVocalOnly] = useState(false)
  const [lyricsHint, setLyricsHint] = useState("")
  const [qualityWarning, setQualityWarning] = useState<string | null>(null)
  // App states
  const [status, setStatus] = useState<AppStatus>(AppStatus.IDLE)
  const [inputAudio, setInputAudio] = useState<AudioFile | null>(null)
  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [taskStatusMsg, setTaskStatusMsg] = useState<string | null>(null)

  const handleFileSelect = async (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      setErrorMsg("解析音频文件大小不能超过 10MB")
      return
    }

    try {
      setStatus(AppStatus.UPLOADING)
      setErrorMsg(null)
      setTaskStatusMsg("正在解析四维音频特征…")
      
      const fileUrl = window.URL.createObjectURL(file)
      setInputAudio({
        file,
        url: fileUrl,
        name: file.name,
        duration: 0
      })

      const formData = new FormData()
      formData.append('audio', file)
      formData.append('prompt_text', text)
      formData.append('is_vocal_only', String(isVocalOnly))
      formData.append('lyrics', lyricsHint)

      const resp = await axios.post('/api/v1/extract_features', formData)
      const data = resp.data
      
      if (data.ph) setPhSeq(data.ph)
      if (data.note) setNoteSeq(data.note)
      if (data.note_dur) setNoteDurSeq(data.note_dur)
      if (data.note_type) setNoteTypeSeq(data.note_type)
      if (data.quality_ok === false) {
        const reason = typeof data.quality_reason === 'string' ? data.quality_reason.trim() : ""
        setQualityWarning(
          reason
            ? `当前提取的四维特征可信度较低，转换结果可能不稳定。原因：${reason}。建议：提供更准确歌词、缩短片段、或使用更干净的人声音频。`
            : "当前提取的四维特征可信度较低，转换结果可能不稳定。建议：提供更准确歌词、缩短片段、或使用更干净的人声音频。"
        )
      } else {
        setQualityWarning(null)
      }
      
      setTaskStatusMsg("解析完成，特征序列已自动回填。")
      setStatus(AppStatus.READY_TO_CONVERT)
    } catch (err: unknown) {
      console.error('Extract features error:', err)
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail
        if (detail && typeof detail === 'object') {
          const message = (detail as { message?: string }).message
          setErrorMsg(message || "音频解析失败，请检查后端服务")
        } else {
          setErrorMsg(typeof detail === 'string' ? detail : "音频解析失败，请检查后端服务")
        }
      } else {
        setErrorMsg("解析异常，请稍后重试。")
      }
      setQualityWarning(null)
      setTaskStatusMsg(null)
      setStatus(AppStatus.ERROR)
    }
  }

  const pollTask = async (taskId: string) => {
    for (let i = 0; i < 180; i += 1) {
      try {
        const statusResp = await axios.get(`/api/v1/tasks/${taskId}`)
        const data = statusResp.data || {}
        const currentStatus = data.status
        const message = data.message
        const backendError = data.error
        
        setTaskStatusMsg((prev) => {
          const newText = typeof message === 'string' ? message : (typeof currentStatus === 'string' ? currentStatus : "正在处理...")
          return newText === prev ? prev : newText
        })

        if (currentStatus === 'completed') {
          const resultBlob = await axios.get(`/api/v1/tasks/${taskId}/result`, { responseType: 'blob' })
          return resultBlob.data
        }
        if (currentStatus === 'failed') {
          const errStr = typeof backendError === 'string' ? backendError : JSON.stringify(backendError || "后端处理失败")
          throw new Error(errStr)
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
    throw new Error('任务超时，请重试')
  }

  const handleConvert = async () => {
    if (!inputAudio?.file) {
      setErrorMsg("请先上传参考音频")
      return
    }
    
    setStatus(AppStatus.CONVERTING)
    setErrorMsg(null)
    setTaskStatusMsg("任务初始化...")

    const formData = new FormData()
    formData.append('text', text)
    formData.append('style_strength', styleStrength.toString())
    formData.append('ph_seq', phSeq)
    formData.append('note_seq', noteSeq)
    formData.append('note_dur_seq', noteDurSeq)
    formData.append('note_type_seq', noteTypeSeq)
    formData.append('is_vocal_only', String(isVocalOnly))
    formData.append('ref_audio', inputAudio.file)

    try {
      setTaskStatusMsg("任务创建中...")
      const taskResp = await axios.post('/api/v1/tasks', formData)
      const taskId = taskResp.data?.task_id
      if (!taskId) throw new Error('任务创建失败，后端未返回 ID')
      
      setTaskStatusMsg("正在排队中")
      const blob = await pollTask(taskId)
      
      if (!(blob instanceof Blob)) {
        throw new Error('生成的音频数据格式错误')
      }

      const url = window.URL.createObjectURL(blob)
      setResult({
        originalUrl: inputAudio.url!,
        convertedUrl: url
      })
      setTaskStatusMsg("转换完成！")
      setStatus(AppStatus.COMPLETED)
    } catch (err: unknown) {
      console.error('Submission error:', err)
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail as any
        const errorMessage = typeof detail === 'string' 
          ? detail 
          : (typeof detail === 'object' ? (detail.message || JSON.stringify(detail)) : (err.message || "请求失败"))
        setErrorMsg(errorMessage)
      } else {
        setErrorMsg(err instanceof Error ? err.message : "未知错误，请检查后端服务")
      }
      setStatus(AppStatus.ERROR)
    }
  }

  const resetApp = () => {
    setStatus(AppStatus.IDLE)
    setInputAudio(null)
    setResult(null)
    setText('')
    setPhSeq('')
    setNoteSeq('')
    setNoteDurSeq('')
    setNoteTypeSeq('')
    setIsVocalOnly(false)
    setLyricsHint('')
    setQualityWarning(null)
    setErrorMsg(null)
    setTaskStatusMsg(null)
  }

  const renderStatusIndicator = () => {
    switch(status) {
      case AppStatus.UPLOADING:
        return <span className="text-yellow-400 flex items-center gap-2"><div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"/> 解析特征中...</span>
      case AppStatus.CONVERTING:
        return <span className="text-secondary flex items-center gap-2"><div className="w-2 h-2 bg-secondary rounded-full animate-pulse"/> 转换风格中...</span>
      case AppStatus.COMPLETED:
        return <span className="text-green-400 flex items-center gap-2"><CheckCircle2 className="w-4 h-4"/> 完成</span>
      default:
        return null;
    }
  };

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-dark text-slate-200 selection:bg-primary/30" translate="no">
        {/* Header */}
        <header className="border-b border-slate-800 bg-surface/50 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-primary to-secondary rounded-lg flex items-center justify-center shadow-lg shadow-primary/20">
                <Music className="text-white w-6 h-6" />
              </div>
              <div>
                <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                  StyleSinger
                </h1>
                <p className="text-xs text-slate-500 font-medium tracking-wide">基于文本提示控制的歌声风格转换系统</p>
              </div>
            </div>
            <div className="text-sm font-medium">
               {renderStatusIndicator()}
            </div>
          </div>
        </header>

        <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">
          {/* Intro / Hero */}
          {status === AppStatus.IDLE && (
            <div className="text-center py-10 space-y-4">
              <h2 className="text-3xl md:text-4xl font-bold text-white">
                使用 <span className="text-primary">文本提示词</span> 控制歌声风格
              </h2>
              <p className="text-slate-400 max-w-2xl mx-auto text-lg">
                上传一段干声，输入描述你想要风格的提示词（如：“忧伤的爵士女声，带一点气声”），AI 将为你提取四维声学特征，并打破原音频语速束缚，实现深度风格控制。
              </p>
            </div>
          )}

          {/* ERROR STATE */}
          {status === AppStatus.ERROR && (
             <div className="bg-red-500/10 border border-red-500/50 text-red-200 p-4 rounded-xl flex items-center gap-3">
               <AlertCircle className="w-6 h-6" />
               <p>{errorMsg || "发生未知错误"}</p>
               <button onClick={resetApp} className="ml-auto underline text-sm hover:text-white">重试</button>
             </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* LEFT COLUMN: Input & Upload & Features */}
            <div className="lg:col-span-7 space-y-6">
              {/* Step 1: Upload */}
              <div className={`transition-all duration-500 ${status !== AppStatus.IDLE && status !== AppStatus.UPLOADING ? 'opacity-100' : ''}`}>
                <div className="flex items-center gap-3 mb-4">
                   <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sm font-bold text-slate-400">1</div>
                   <h3 className="text-lg font-semibold text-white">上传音频并解析特征</h3>
                </div>
                
                {inputAudio ? (
                   <div className="space-y-4">
                      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 flex items-center justify-between">
                         <div className="flex items-center gap-3">
                           <Music4 className="text-primary w-5 h-5" />
                           <span className="text-sm text-slate-300 truncate max-w-[200px]">{inputAudio.name}</span>
                           <span className="text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">特征已解析</span>
                         </div>
                         <button onClick={resetApp} className="text-xs text-slate-500 hover:text-white transition-colors" disabled={status === AppStatus.CONVERTING}>
                           更换文件
                         </button>
                      </div>
                      <WaveformPlayer audioUrl={inputAudio.url} waveColor="#6366f1" progressColor="#a5b4fc" />
                      
                      {/* 四维特征展示区 */}
                      <div className="bg-surface/50 rounded-xl p-4 border border-slate-700/50 mt-4 space-y-3">
                        <div className="flex items-center justify-between mb-2">
                           <h4 className="text-sm font-medium text-slate-300">乐谱特征序列 (四维张量)</h4>
                           {taskStatusMsg && <span className="text-xs text-primary">{taskStatusMsg}</span>}
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">音素序列 (ph)</label>
                          <textarea value={phSeq} onChange={(e) => setPhSeq(e.target.value)} disabled={status === AppStatus.CONVERTING} className="w-full bg-slate-900/50 border border-slate-700 rounded-lg p-2 text-slate-300 text-xs font-mono resize-y h-16 focus:ring-1 focus:ring-primary outline-none disabled:opacity-60" />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">音高序列 (note)</label>
                          <textarea value={noteSeq} onChange={(e) => setNoteSeq(e.target.value)} disabled={status === AppStatus.CONVERTING} className="w-full bg-slate-900/50 border border-slate-700 rounded-lg p-2 text-slate-300 text-xs font-mono resize-y h-12 focus:ring-1 focus:ring-primary outline-none disabled:opacity-60" />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">时值序列 (note_dur)</label>
                          <textarea value={noteDurSeq} onChange={(e) => setNoteDurSeq(e.target.value)} disabled={status === AppStatus.CONVERTING} className="w-full bg-slate-900/50 border border-slate-700 rounded-lg p-2 text-slate-300 text-xs font-mono resize-y h-12 focus:ring-1 focus:ring-primary outline-none disabled:opacity-60" />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">类型序列 (note_type)</label>
                          <textarea value={noteTypeSeq} onChange={(e) => setNoteTypeSeq(e.target.value)} disabled={status === AppStatus.CONVERTING} className="w-full bg-slate-900/50 border border-slate-700 rounded-lg p-2 text-slate-300 text-xs font-mono resize-y h-12 focus:ring-1 focus:ring-primary outline-none disabled:opacity-60" />
                        </div>
                        {qualityWarning && (
                          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                            {qualityWarning}
                          </div>
                        )}
                      </div>
                   </div>
                ) : (
                  <div className="space-y-4 relative">
                    {status === AppStatus.UPLOADING && (
                      <div className="absolute inset-0 z-20 bg-slate-900/80 backdrop-blur-sm rounded-2xl flex flex-col items-center justify-center border border-slate-700">
                        <Loader2 className="w-8 h-8 text-primary animate-spin mb-2" />
                        <span className="text-slate-200 font-medium text-sm">{taskStatusMsg || "正在提取特征..."}</span>
                      </div>
                    )}
                    <FileUpload 
                      onFileSelect={handleFileSelect} 
                      disabled={status === AppStatus.UPLOADING}
                    />
                    <label className="flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-800/40 px-4 py-3 text-sm text-slate-300">
                      <input
                        type="checkbox"
                        checked={isVocalOnly}
                        onChange={(e) => setIsVocalOnly(e.target.checked)}
                        className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-primary focus:ring-primary"
                      />
                      <span>输入已是纯人声/干声，跳过人声分离</span>
                    </label>
                    <textarea
                      value={lyricsHint}
                      onChange={(e) => setLyricsHint(e.target.value)}
                      placeholder="可选：输入歌词/文本，帮助做更准的对齐"
                      className="min-h-[88px] w-full rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-primary focus:outline-none"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT COLUMN: Style Controls & Output */}
            <div className="lg:col-span-5 space-y-6">
              {/* Step 2: Controls */}
              <div className={`transition-all duration-500 delay-100 ${status === AppStatus.IDLE ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
                 <div className="flex items-center gap-3 mb-4">
                   <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sm font-bold text-slate-400">2</div>
                   <h3 className="text-lg font-semibold text-white">风格控制</h3>
                 </div>
                 
                 <div className="bg-surface/50 rounded-2xl p-6 border border-slate-700 shadow-xl backdrop-blur-sm">
                   <StyleControls 
                     prompt={text}
                     setPrompt={setText}
                     intensity={styleStrength}
                     setIntensity={setStyleStrength}
                     onConvert={handleConvert}
                     isLoading={status === AppStatus.CONVERTING}
                     disabled={status === AppStatus.IDLE || status === AppStatus.UPLOADING || status === AppStatus.CONVERTING}
                   />
                   {status === AppStatus.CONVERTING && taskStatusMsg && (
                     <div className="mt-4 text-center text-sm text-secondary animate-pulse">
                       {taskStatusMsg}
                     </div>
                   )}
                 </div>
              </div>
            </div>
          </div>
          
          {/* Step 3: Result */}
          {status === AppStatus.COMPLETED && result && (
            <div className="animate-in fade-in slide-in-from-bottom-8 duration-700 pt-8 border-t border-slate-800">
               <div className="flex items-center gap-3 mb-6">
                 <div className="w-8 h-8 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center text-sm font-bold text-green-400">3</div>
                 <h3 className="text-xl font-semibold text-white">转换结果 (A/B 对比)</h3>
               </div>

               <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 {/* Original */}
                 <div className="bg-slate-800/40 rounded-xl p-5 border border-slate-700/50">
                    <div className="flex justify-between items-center mb-4">
                      <span className="text-sm font-medium text-slate-400 uppercase tracking-wider">原始音频</span>
                    </div>
                    <WaveformPlayer audioUrl={result.originalUrl} waveColor="#64748b" progressColor="#94a3b8" />
                 </div>
                 
                 {/* Converted */}
                 <div className="bg-gradient-to-br from-primary/10 to-secondary/10 rounded-xl p-5 border border-primary/30 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-primary/20 rounded-full blur-3xl -mr-10 -mt-10" />
                    <div className="flex justify-between items-center mb-4 relative z-10">
                      <span className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-secondary" />
                        目标风格
                      </span>
                      <a 
                        href={result.convertedUrl} 
                        download={`stylesinger_${inputAudio?.name || 'result.wav'}`}
                        className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shadow-lg shadow-primary/20"
                      >
                        <Download className="w-3.5 h-3.5" /> 下载音频
                      </a>
                    </div>
                    <div className="relative z-10">
                      <WaveformPlayer audioUrl={result.convertedUrl} waveColor="#ec4899" progressColor="#f472b6" />
                    </div>
                 </div>
               </div>
            </div>
          )}

        </main>
      </div>
    </ErrorBoundary>
  )
}

export default App
