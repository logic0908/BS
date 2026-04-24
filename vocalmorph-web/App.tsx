import React, { useState } from 'react';
import { AppStatus, AudioFile, ProcessingResult } from './types';
import { uploadAudioService, convertAudioService } from './services/mockApi';
import FileUpload from './components/FileUpload';
import AudioRecorder from './components/AudioRecorder';
import WaveformPlayer from './components/WaveformPlayer';
import StyleControls from './components/StyleControls';
import { Mic2, Music4, ArrowRight, Download, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';

const App: React.FC = () => {
  // State Management
  const [status, setStatus] = useState<AppStatus>(AppStatus.IDLE);
  const [inputAudio, setInputAudio] = useState<AudioFile | null>(null);
  const [prompt, setPrompt] = useState('');
  const [intensity, setIntensity] = useState(0.7);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  
  // Stores the ID returned from backend after separation
  const [audioId, setAudioId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Handlers
  const handleFileSelect = async (file: File) => {
    try {
      setStatus(AppStatus.UPLOADING);
      setErrorMsg(null);
      // Calls the upload service (Real API with fallback)
      const { audioId, vocalsUrl } = await uploadAudioService(file);
      
      setInputAudio({
        file,
        url: vocalsUrl,
        name: file.name,
        duration: 0 
      });
      setAudioId(audioId);
      setStatus(AppStatus.READY_TO_CONVERT);
    } catch (err) {
      console.error(err);
      setStatus(AppStatus.ERROR);
      setErrorMsg("Failed to upload audio file. Check your connection.");
    }
  };

  const handleConvert = async () => {
    if (!audioId || !inputAudio) return;

    try {
      setStatus(AppStatus.CONVERTING);
      setErrorMsg(null);
      
      // Calls the convert service
      // We pass inputAudio.url! as the 4th argument so the mock fallback can use it
      const { resultUrl } = await convertAudioService(
        audioId, 
        prompt, 
        intensity, 
        inputAudio.url!
      );
      
      setResult({
        originalUrl: inputAudio.url!,
        convertedUrl: resultUrl
      });
      setStatus(AppStatus.COMPLETED);
    } catch (err) {
      console.error(err);
      setStatus(AppStatus.ERROR);
      setErrorMsg("Conversion failed. Please try a different style or audio.");
    }
  };

  const resetApp = () => {
    setStatus(AppStatus.IDLE);
    setInputAudio(null);
    setResult(null);
    setPrompt('');
    setAudioId(null);
    setErrorMsg(null);
  };

  // Status Badge Helper
  const renderStatusIndicator = () => {
    switch(status) {
      case AppStatus.UPLOADING:
        return <span className="text-yellow-400 flex items-center gap-2"><div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"/> Separating Vocals...</span>
      case AppStatus.CONVERTING:
        return <span className="text-secondary flex items-center gap-2"><div className="w-2 h-2 bg-secondary rounded-full animate-pulse"/> Transforming Style...</span>
      case AppStatus.COMPLETED:
        return <span className="text-green-400 flex items-center gap-2"><CheckCircle2 className="w-4 h-4"/> Done</span>
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-dark text-slate-200 selection:bg-primary/30">
      
      {/* Header */}
      <header className="border-b border-slate-800 bg-surface/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-primary to-secondary rounded-lg flex items-center justify-center shadow-lg shadow-primary/20">
              <Mic2 className="text-white w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                VocalMorph
              </h1>
              <p className="text-xs text-slate-500 font-medium tracking-wide">AI STYLE TRANSFER SYSTEM</p>
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
              Transform your voice with <span className="text-primary">Text Prompts</span>
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto text-lg">
              Upload a dry vocal track, describe the style you want (e.g., "Lazy jazz singer"), 
              and let our AI rewrite the timbre while keeping the melody.
            </p>
          </div>
        )}

        {/* ERROR STATE */}
        {status === AppStatus.ERROR && (
           <div className="bg-red-500/10 border border-red-500/50 text-red-200 p-4 rounded-xl flex items-center gap-3">
             <AlertCircle className="w-6 h-6" />
             <p>{errorMsg || "An unexpected error occurred."}</p>
             <button onClick={resetApp} className="ml-auto underline text-sm hover:text-white">Try Again</button>
           </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* LEFT COLUMN: Input & Upload */}
          <div className="lg:col-span-7 space-y-6">
            
            {/* Step 1: Upload */}
            <div className={`transition-all duration-500 ${status !== AppStatus.IDLE && status !== AppStatus.UPLOADING ? 'opacity-100' : ''}`}>
              <div className="flex items-center gap-3 mb-4">
                 <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sm font-bold text-slate-400">1</div>
                 <h3 className="text-lg font-semibold text-white">Source Audio</h3>
              </div>
              
              {inputAudio ? (
                 <div className="space-y-4">
                    <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 flex items-center justify-between">
                       <div className="flex items-center gap-3">
                         <Music4 className="text-primary w-5 h-5" />
                         <span className="text-sm text-slate-300 truncate max-w-[200px]">{inputAudio.name}</span>
                         <span className="text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">Vocals Extracted</span>
                       </div>
                       <button onClick={resetApp} className="text-xs text-slate-500 hover:text-white transition-colors">
                         Change File
                       </button>
                    </div>
                    <WaveformPlayer audioUrl={inputAudio.url} waveColor="#6366f1" progressColor="#a5b4fc" />
                 </div>
              ) : (
                <div className="space-y-4">
                  <FileUpload 
                    onFileSelect={handleFileSelect} 
                    disabled={status === AppStatus.UPLOADING}
                  />
                  
                  <div className="flex items-center gap-4 px-2">
                    <div className="h-px bg-slate-800 flex-1" />
                    <span className="text-xs text-slate-600 font-medium uppercase tracking-wider">Or</span>
                    <div className="h-px bg-slate-800 flex-1" />
                  </div>

                  <AudioRecorder 
                    onRecordingComplete={handleFileSelect}
                    disabled={status === AppStatus.UPLOADING}
                  />
                </div>
              )}
            </div>

            {/* Step 3: Result (Only shown when completed) */}
            {status === AppStatus.COMPLETED && result && (
               <div className="animate-in fade-in slide-in-from-bottom-8 duration-700">
                  <div className="flex items-center gap-3 mb-4 pt-6 border-t border-slate-800">
                    <div className="w-8 h-8 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center text-sm font-bold text-green-400">3</div>
                    <h3 className="text-lg font-semibold text-white">Transformation Result</h3>
                  </div>

                  <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-6 border border-slate-700 shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                      <Music4 className="w-40 h-40" />
                    </div>

                    <div className="space-y-6 relative z-10">
                       <div className="flex justify-between items-end">
                          <div>
                            <p className="text-sm text-slate-400 mb-1">Style applied:</p>
                            <p className="text-xl text-white font-medium italic">"{prompt}"</p>
                          </div>
                          <a 
                            href={result.convertedUrl} 
                            download={`converted-${inputAudio?.name}`}
                            className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition-colors"
                          >
                            <Download className="w-4 h-4" /> Download
                          </a>
                       </div>
                       
                       <div className="space-y-2">
                         <div className="flex justify-between text-xs uppercase tracking-wider text-slate-500 font-semibold">
                            <span>Converted Audio</span>
                         </div>
                         <WaveformPlayer 
                            audioUrl={result.convertedUrl} 
                            waveColor="#ec4899" 
                            progressColor="#fbcfe8" 
                          />
                       </div>

                       <div className="flex justify-center pt-2">
                          <button 
                            onClick={resetApp}
                            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm"
                          >
                            <RefreshCw className="w-4 h-4" /> Convert Another
                          </button>
                       </div>
                    </div>
                  </div>
               </div>
            )}

          </div>

          {/* RIGHT COLUMN: Controls */}
          <div className="lg:col-span-5">
            <div className={`bg-surface border border-slate-700 rounded-2xl p-6 sticky top-24 transition-opacity duration-300 ${status === AppStatus.IDLE || !inputAudio ? 'opacity-50 pointer-events-none grayscale' : 'opacity-100'}`}>
               <div className="flex items-center gap-3 mb-6">
                 <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sm font-bold text-slate-400">2</div>
                 <h3 className="text-lg font-semibold text-white">Style Configuration</h3>
              </div>

              <StyleControls 
                prompt={prompt}
                setPrompt={setPrompt}
                intensity={intensity}
                setIntensity={setIntensity}
                onConvert={handleConvert}
                isLoading={status === AppStatus.CONVERTING}
                disabled={status !== AppStatus.READY_TO_CONVERT && status !== AppStatus.COMPLETED}
              />

              {/* Process Visualizer (Desktop only decoration) */}
              {status === AppStatus.CONVERTING && (
                <div className="mt-8 pt-8 border-t border-slate-700/50">
                   <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
                      <span>Input</span>
                      <ArrowRight className="w-4 h-4 animate-pulse text-slate-600" />
                      <span>Encoder</span>
                      <ArrowRight className="w-4 h-4 animate-pulse text-slate-600" />
                      <span>Adapter</span>
                      <ArrowRight className="w-4 h-4 animate-pulse text-slate-600" />
                      <span>Decoder</span>
                   </div>
                   <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-primary to-secondary w-full animate-progress-indeterminate origin-left"></div>
                   </div>
                   <p className="text-center text-xs text-slate-500 mt-2">Injecting style vector into So-VITS-SVC flow...</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;