import React, { useState } from 'react';
import { Wand2, Sliders, Sparkles, Loader2 } from 'lucide-react';
import { GoogleGenAI } from "@google/genai";
import { STYLE_PRESETS } from '../types';

interface StyleControlsProps {
  prompt: string;
  setPrompt: (val: string) => void;
  intensity: number;
  setIntensity: (val: number) => void;
  onConvert: () => void;
  isLoading: boolean;
  disabled: boolean;
}

const StyleControls: React.FC<StyleControlsProps> = ({
  prompt,
  setPrompt,
  intensity,
  setIntensity,
  onConvert,
  isLoading,
  disabled
}) => {
  const [isRefining, setIsRefining] = useState(false);

  const handleAiRefine = async () => {
    if (!prompt.trim() || !process.env.API_KEY) return;
    
    setIsRefining(true);
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
      
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: `You are an expert AI music producer. Rewrite the following vocal style description to be highly detailed, descriptive, and optimized for an AI Singing Voice Conversion model. Focus on timbre, emotion, breathiness, and articulation. Keep it under 30 words.
        
        Input: "${prompt}"
        Output:`
      });

      if (response.text) {
        setPrompt(response.text.trim());
      }
    } catch (error) {
      console.error("Failed to refine prompt with Gemini:", error);
    } finally {
      setIsRefining(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Prompt Section */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
            <Wand2 className="w-4 h-4 text-secondary" />
            Style Description
          </label>
          {process.env.API_KEY && (
            <button
              onClick={handleAiRefine}
              disabled={disabled || !prompt.trim() || isRefining}
              className="text-xs flex items-center gap-1.5 text-primary hover:text-primary/80 disabled:opacity-50 transition-colors"
            >
              {isRefining ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              AI Refine
            </button>
          )}
        </div>
        
        <div className="relative">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={disabled}
            placeholder="Describe the desired voice style (e.g., 'A clear, melancholic female jazz singer')..."
            className="w-full bg-slate-900/50 border border-slate-700 rounded-xl p-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all resize-none h-24"
          />
        </div>

        {/* Quick Tags */}
        <div className="flex flex-wrap gap-2">
          {STYLE_PRESETS.map((preset) => (
            <button
              key={preset}
              onClick={() => setPrompt(preset)}
              disabled={disabled}
              className="text-xs px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 hover:border-slate-500 hover:bg-slate-700 text-slate-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      {/* Intensity Section */}
      <div className="space-y-3">
        <div className="flex justify-between items-center text-sm">
          <label className="flex items-center gap-2 font-medium text-slate-300">
            <Sliders className="w-4 h-4 text-blue-400" />
            Transfer Intensity
          </label>
          <span className="text-primary font-mono bg-primary/10 px-2 py-0.5 rounded text-xs">
            {Math.round(intensity * 100)}%
          </span>
        </div>
        
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={intensity}
          onChange={(e) => setIntensity(parseFloat(e.target.value))}
          disabled={disabled}
          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-primary"
        />
        <div className="flex justify-between text-xs text-slate-500 px-1">
          <span>Subtle</span>
          <span>Balanced</span>
          <span>Strong</span>
        </div>
      </div>

      {/* Action Button */}
      <button
        onClick={onConvert}
        disabled={disabled || !prompt.trim() || isLoading}
        className={`w-full py-4 rounded-xl font-bold text-lg shadow-lg transition-all transform active:scale-[0.98] ${
          disabled || !prompt.trim()
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed shadow-none'
            : 'bg-gradient-to-r from-primary to-secondary hover:from-primary/90 hover:to-secondary/90 text-white shadow-primary/25'
        }`}
      >
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Processing...
          </span>
        ) : (
          "Start Conversion"
        )}
      </button>
    </div>
  );
};

export default StyleControls;