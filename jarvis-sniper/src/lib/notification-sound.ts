/**
 * Browser notification sounds via Web Audio API.
 * No external files needed — generates tones programmatically.
 */

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    try {
      audioCtx = new AudioContext();
    } catch {
      return null;
    }
  }
  // Resume if suspended (browser autoplay policy)
  if (audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

function playTone(frequency: number, duration: number, type: OscillatorType = 'sine', volume = 0.15) {
  const ctx = getAudioContext();
  if (!ctx) return;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = type;
  osc.frequency.setValueAtTime(frequency, ctx.currentTime);

  gain.gain.setValueAtTime(volume, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start(ctx.currentTime);
  osc.stop(ctx.currentTime + duration);
}

/** Rising two-tone chime — snipe executed successfully */
export function playSniped() {
  playTone(523, 0.15, 'sine', 0.12);  // C5
  setTimeout(() => playTone(784, 0.25, 'sine', 0.12), 120);  // G5
}

/** Triumphant ascending arpeggio — take profit hit */
export function playTpHit() {
  playTone(523, 0.12, 'sine', 0.1);   // C5
  setTimeout(() => playTone(659, 0.12, 'sine', 0.1), 100);  // E5
  setTimeout(() => playTone(784, 0.12, 'sine', 0.1), 200);  // G5
  setTimeout(() => playTone(1047, 0.3, 'sine', 0.12), 300); // C6
}

/** Low warning tone — stop loss hit */
export function playSlHit() {
  playTone(294, 0.2, 'square', 0.08);  // D4
  setTimeout(() => playTone(220, 0.35, 'square', 0.08), 180);  // A3
}

/** Alert pulse — exit pending (needs user action) */
export function playExitPending() {
  playTone(440, 0.1, 'triangle', 0.1);  // A4
  setTimeout(() => playTone(440, 0.1, 'triangle', 0.1), 200);
  setTimeout(() => playTone(440, 0.1, 'triangle', 0.1), 400);
}

/** Error buzz */
export function playError() {
  playTone(200, 0.15, 'sawtooth', 0.06);
  setTimeout(() => playTone(180, 0.2, 'sawtooth', 0.06), 150);
}

/** Play sound based on execution event type */
export function playNotificationSound(type: string) {
  switch (type) {
    case 'snipe':
      playSniped();
      break;
    case 'tp_exit':
      playTpHit();
      break;
    case 'sl_exit':
      playSlHit();
      break;
    case 'exit_pending':
      playExitPending();
      break;
    case 'error':
      playError();
      break;
  }
}
