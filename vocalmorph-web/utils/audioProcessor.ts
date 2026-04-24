
import { ProcessingParams } from '../types';

/**
 * Maps a natural language style prompt to DSP parameters.
 * This simulates the "Text Encoder -> Style Vector" part of the deep learning model.
 */
export const mapPromptToParams = (prompt: string, intensity: number): ProcessingParams => {
  const p = prompt.toLowerCase();
  
  // Default parameters (Neutral)
  const params: ProcessingParams = {
    pitchShift: 0, // semitones
    speed: 1.0,
    distortion: 0,
    reverb: 0,
    lowPass: 20000,
    highPass: 0,
    formantShift: 0
  };

  // 1. PITCH / GENDER MAPPING
  if (p.includes('female') || p.includes('girl') || p.includes('woman') || p.includes('high') || p.includes('anime') || p.includes('cute')) {
    params.pitchShift = 3.5 * intensity; // Shift up
    params.formantShift = 0.2 * intensity;
  } else if (p.includes('male') || p.includes('boy') || p.includes('man') || p.includes('deep') || p.includes('low') || p.includes('baritone')) {
    params.pitchShift = -4.0 * intensity; // Shift down
    params.formantShift = -0.15 * intensity;
  }

  // 2. TIMBRE / EQ MAPPING
  if (p.includes('radio') || p.includes('telephone') || p.includes('old') || p.includes('lofi') || p.includes('vintage')) {
    params.highPass = 500 + (500 * intensity);
    params.lowPass = 3000 - (1000 * intensity);
    params.distortion = 0.4 * intensity;
  } else if (p.includes('clear') || p.includes('bright') || p.includes('pop')) {
    params.highPass = 200 * intensity;
    params.pitchShift += 1 * intensity;
  } else if (p.includes('dark') || p.includes('warm') || p.includes('jazz')) {
    params.lowPass = 4000 - (1000 * intensity);
    params.pitchShift -= 1 * intensity;
  }

  // 3. EFFECT MAPPING
  if (p.includes('reverb') || p.includes('echo') || p.includes('hall') || p.includes('space') || p.includes('ethereal') || p.includes('dream')) {
    params.reverb = 0.6 * intensity;
  }
  
  if (p.includes('rock') || p.includes('metal') || p.includes('power') || p.includes('aggressive') || p.includes('distortion')) {
    params.distortion = 0.8 * intensity;
  }
  
  if (p.includes('slow') || p.includes('lazy') || p.includes('sad')) {
    params.speed = 1.0 - (0.15 * intensity);
  } else if (p.includes('fast') || p.includes('rap') || p.includes('energetic')) {
    params.speed = 1.0 + (0.1 * intensity);
  }

  return params;
};

/**
 * Core DSP Engine: Applies effects to audio buffer using OfflineAudioContext.
 */
export const processAudioStyle = async (
  originalUrl: string, 
  prompt: string, 
  intensity: number
): Promise<string> => {
  // 1. Load Audio
  const response = await fetch(originalUrl);
  const arrayBuffer = await response.arrayBuffer();
  
  // 2. Decode Audio
  const tempCtx = new AudioContext();
  const audioBuffer = await tempCtx.decodeAudioData(arrayBuffer);
  
  // 3. Map Prompt to Parameters
  const params = mapPromptToParams(prompt, intensity);
  
  // 4. Setup Offline Context for Rendering
  // Note: Pitch shifting via playbackRate changes duration. 
  // If we slow down, we need more time.
  const newLength = Math.ceil(audioBuffer.length / params.speed) + (params.reverb > 0 ? 44100 * 3 : 0); // Add tail for reverb
  const offlineCtx = new OfflineAudioContext(
    audioBuffer.numberOfChannels,
    newLength,
    audioBuffer.sampleRate
  );

  // 5. Create Nodes
  const source = offlineCtx.createBufferSource();
  source.buffer = audioBuffer;
  
  // Effect Chain
  let currentNode: AudioNode = source;

  // -- Pitch / Speed (Basic resampling) --
  // Note: True formant shifting is complex, we use detune/playbackRate for approximation
  source.detune.value = params.pitchShift * 100; 
  source.playbackRate.value = params.speed;

  // -- Filter (EQ) --
  if (params.highPass > 0) {
    const hp = offlineCtx.createBiquadFilter();
    hp.type = 'highpass';
    hp.frequency.value = params.highPass;
    currentNode.connect(hp);
    currentNode = hp;
  }
  
  if (params.lowPass < 20000) {
    const lp = offlineCtx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = params.lowPass;
    currentNode.connect(lp);
    currentNode = lp;
  }

  // -- Distortion --
  if (params.distortion > 0) {
    const dist = offlineCtx.createWaveShaper();
    dist.curve = makeDistortionCurve(params.distortion * 50); // Scale up
    dist.oversample = '4x';
    currentNode.connect(dist);
    currentNode = dist;
  }

  // -- Reverb (Convolution) --
  if (params.reverb > 0) {
    const convolver = offlineCtx.createConvolver();
    // Generate simple impulse response
    convolver.buffer = impulseResponse(1.5, 1.5, false, offlineCtx);
    
    // Create Wet/Dry Mix
    const dryGain = offlineCtx.createGain();
    const wetGain = offlineCtx.createGain();
    dryGain.gain.value = 1 - (params.reverb * 0.5);
    wetGain.gain.value = params.reverb;
    
    // Branch
    currentNode.connect(dryGain);
    currentNode.connect(convolver);
    convolver.connect(wetGain);
    
    // Merge
    const merger = offlineCtx.createGain();
    dryGain.connect(merger);
    wetGain.connect(merger);
    currentNode = merger;
  }

  // Connect to Output
  currentNode.connect(offlineCtx.destination);

  // 6. Render
  source.start();
  const renderedBuffer = await offlineCtx.startRendering();

  // 7. Convert to Wav Blob URL
  const wavBlob = bufferToWave(renderedBuffer, renderedBuffer.length);
  return URL.createObjectURL(wavBlob);
};

// --- Helpers ---

function makeDistortionCurve(amount: number) {
  const k = typeof amount === 'number' ? amount : 50;
  const n_samples = 44100;
  const curve = new Float32Array(n_samples);
  const deg = Math.PI / 180;
  
  for (let i = 0; i < n_samples; ++i) {
    const x = (i * 2) / n_samples - 1;
    curve[i] = (3 + k) * x * 20 * deg / (Math.PI + k * Math.abs(x));
  }
  return curve;
}

function impulseResponse(duration: number, decay: number, reverse: boolean, ctx: BaseAudioContext) {
  const sampleRate = ctx.sampleRate;
  const length = sampleRate * duration;
  const impulse = ctx.createBuffer(2, length, sampleRate);
  const left = impulse.getChannelData(0);
  const right = impulse.getChannelData(1);

  for (let i = 0; i < length; i++) {
    let n = reverse ? length - i : i;
    left[i] = (Math.random() * 2 - 1) * Math.pow(1 - n / length, decay);
    right[i] = (Math.random() * 2 - 1) * Math.pow(1 - n / length, decay);
  }
  return impulse;
}

// Simple WAV encoder
function bufferToWave(abuffer: AudioBuffer, len: number) {
  const numOfChan = abuffer.numberOfChannels;
  const length = len * numOfChan * 2 + 44;
  const buffer = new ArrayBuffer(length);
  const view = new DataView(buffer);
  const channels = [];
  let i;
  let sample;
  let offset = 0;
  let pos = 0;

  // write WAVE header
  setUint32(0x46464952); // "RIFF"
  setUint32(length - 8); // file length - 8
  setUint32(0x45564157); // "WAVE"

  setUint32(0x20746d66); // "fmt " chunk
  setUint32(16); // length = 16
  setUint16(1); // PCM (uncompressed)
  setUint16(numOfChan);
  setUint32(abuffer.sampleRate);
  setUint32(abuffer.sampleRate * 2 * numOfChan); // avg. bytes/sec
  setUint16(numOfChan * 2); // block-align
  setUint16(16); // 16-bit (hardcoded in this loop)

  setUint32(0x61746164); // "data" - chunk
  setUint32(length - pos - 4); // chunk length

  // write interleaved data
  for (i = 0; i < abuffer.numberOfChannels; i++)
    channels.push(abuffer.getChannelData(i));

  while (pos < len) {
    for (i = 0; i < numOfChan; i++) {
      // interleave channels
      sample = Math.max(-1, Math.min(1, channels[i][pos])); // clamp
      sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0; // scale to 16-bit signed int
      view.setInt16(44 + offset, sample, true);
      offset += 2;
    }
    pos++;
  }

  return new Blob([buffer], { type: "audio/wav" });

  function setUint16(data: number) {
    view.setUint16(pos, data, true);
    pos += 2;
  }

  function setUint32(data: number) {
    view.setUint32(pos, data, true);
    pos += 4;
  }
}
