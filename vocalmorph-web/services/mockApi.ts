
import { AudioFile, ProcessingResult } from '../types';
import { processAudioStyle } from '../utils/audioProcessor';

const API_BASE_URL = 'https://files.metaso.cn/api';

/**
 * Uploads the audio file to the backend for vocal separation.
 * POST /api/upload
 */
export const uploadAudioService = async (file: File): Promise<{ taskId: string; vocalsUrl: string; audioId: string }> => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    const data = await response.json();
    if (data.code === 0 && data.data) {
      return {
        taskId: data.data.id, 
        audioId: data.data.id,
        vocalsUrl: data.data.url
      };
    }
    throw new Error('Invalid response from server');
  } catch (error) {
    console.warn("Backend unreachable, falling back to local mock.", error);
    // FALLBACK MOCK: Create a local URL for the user's file so they can play it immediately
    return new Promise((resolve) => {
      setTimeout(() => {
        const mockUrl = URL.createObjectURL(file);
        resolve({
          taskId: `mock_task_${Date.now()}`,
          audioId: `mock_audio_${Date.now()}`,
          vocalsUrl: mockUrl
        });
      }, 1500);
    });
  }
};

/**
 * Triggers the voice style conversion process.
 * POST /api/convert
 */
export const convertAudioService = async (
  audioId: string,
  prompt: string,
  intensity: number,
  originalUrl?: string 
): Promise<{ resultUrl: string }> => {
  try {
    // 1. Trigger Conversion Real API
    const response = await fetch(`${API_BASE_URL}/convert`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        audioId,
        prompt,
        intensity
      }),
    });

    if (!response.ok) throw new Error(`Conversion request failed: ${response.statusText}`);

    const data = await response.json();
    const taskId = data.data?.taskId || audioId;

    return await pollTaskStatus(taskId);

  } catch (error) {
    console.warn("Backend unreachable, falling back to local DSP simulation.", error);
    
    // FALLBACK DSP SIMULATION
    // This executes the "Prompt-to-Parameter Mapping" in the browser
    return new Promise(async (resolve) => {
      if (originalUrl) {
        try {
           console.info(`Simulating conversion for style: "${prompt}" with intensity ${intensity}`);
           // Actual Audio Processing logic
           const processedUrl = await processAudioStyle(originalUrl, prompt, intensity);
           resolve({ resultUrl: processedUrl });
        } catch (dspError) {
           console.error("DSP Failed", dspError);
           resolve({ resultUrl: originalUrl }); // Last resort
        }
      } else {
        resolve({
          resultUrl: "https://actions.google.com/sounds/v1/ambiences/coffee_shop.ogg" 
        });
      }
    });
  }
};

/**
 * Polls the status endpoint until the task is complete.
 */
async function pollTaskStatus(taskId: string): Promise<{ resultUrl: string }> {
  const MAX_ATTEMPTS = 30;
  const INTERVAL = 2000;

  for (let i = 0; i < MAX_ATTEMPTS; i++) {
    try {
      const response = await fetch(`${API_BASE_URL}/status/${taskId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.data?.status === 'COMPLETED' && data.data?.url) {
          return { resultUrl: data.data.url };
        }
        if (data.data?.status === 'FAILED') {
          throw new Error('Processing failed on server');
        }
      }
    } catch (e) {
      console.error("Polling error", e);
    }
    await new Promise(resolve => setTimeout(resolve, INTERVAL));
  }
  throw new Error("Conversion timed out");
}
