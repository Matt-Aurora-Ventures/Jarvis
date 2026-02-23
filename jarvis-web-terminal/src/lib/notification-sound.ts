/**
 * notification-sound.ts
 *
 * Browser notification sounds using the Web Audio API.
 * No external audio files required -- generates short tones programmatically.
 *
 * AudioContext is lazily created on first invocation so it does not block
 * initial page load or violate autoplay policies.
 */

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (audioCtx) return audioCtx;

  if (typeof AudioContext === 'undefined') {
    return null;
  }

  try {
    audioCtx = new AudioContext();
    return audioCtx;
  } catch {
    return null;
  }
}

/**
 * Play a short notification tone.
 *
 * @param type
 *  - `'success'`  ascending two-note chime  (440 Hz -> 660 Hz)
 *  - `'warning'`  single 880 Hz beep
 *  - `'error'`    descending two-note       (660 Hz -> 440 Hz)
 *
 * Duration: ~150 ms per note, gain 0.1 (quiet).
 */
export function playNotificationSound(
  type: 'success' | 'warning' | 'error',
): void {
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const noteDuration = 0.15; // 150 ms
  const gain = 0.1;

  const oscillator = ctx.createOscillator();
  const gainNode = ctx.createGain();

  oscillator.type = 'sine';
  oscillator.connect(gainNode);
  gainNode.connect(ctx.destination);

  gainNode.gain.setValueAtTime(gain, now);

  switch (type) {
    case 'success': {
      // Ascending: 440 Hz -> 660 Hz
      oscillator.frequency.setValueAtTime(440, now);
      oscillator.frequency.linearRampToValueAtTime(660, now + noteDuration * 2);
      gainNode.gain.linearRampToValueAtTime(0, now + noteDuration * 2 + 0.02);
      oscillator.start(now);
      oscillator.stop(now + noteDuration * 2 + 0.02);
      break;
    }
    case 'warning': {
      // Single 880 Hz beep
      oscillator.frequency.setValueAtTime(880, now);
      gainNode.gain.linearRampToValueAtTime(0, now + noteDuration + 0.02);
      oscillator.start(now);
      oscillator.stop(now + noteDuration + 0.02);
      break;
    }
    case 'error': {
      // Descending: 660 Hz -> 440 Hz
      oscillator.frequency.setValueAtTime(660, now);
      oscillator.frequency.linearRampToValueAtTime(440, now + noteDuration * 2);
      gainNode.gain.linearRampToValueAtTime(0, now + noteDuration * 2 + 0.02);
      oscillator.start(now);
      oscillator.stop(now + noteDuration * 2 + 0.02);
      break;
    }
  }
}
