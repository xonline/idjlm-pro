// ============================================================================
// Grand-Piano Key Preview (IDJLM Phase 3.5)
// WebAudio piano chord of detected key on click — audible verification
// MIK pattern: zero-backend, WebAudio-only piano synthesis
// ============================================================================

var _keyPreviewCtx = null;

function initKeyPreview() {
  document.body.addEventListener('click', function(e) {
    var keyEl = e.target.closest('.piano-key');
    if (keyEl) {
      var key = keyEl.getAttribute('data-key');
      if (key) playKeyChord(key);
    }
  });
}

// Map Camelot keys to root note MIDI numbers (C4 = 60)
var CAMELOT_TO_ROOT = {
  '1A': 57,  // Ab minor → Ab3
  '1B': 59,  // B major → B3
  '2A': 58,  // Eb minor → Eb3
  '2B': 48,  // F# major → Gb3 (F#3)
  '3A': 59,  // Bb minor → Bb3
  '3B': 49,  // C# major → Db4 (C#3)
  '4A': 48,  // F minor → F3
  '4B': 57,  // Ab major → Ab3
  '5A': 49,  // C minor → C4 (C3)
  '5B': 58,  // Eb major → Eb3
  '6A': 50,  // G minor → G3
  '6B': 59,  // Bb major → Bb3
  '7A': 51,  // D minor → D3
  '7B': 48,  // F major → F3
  '8A': 52,  // A minor → A3
  '8B': 49,  // C major → C4
  '9A': 53,  // E minor → E3
  '9B': 50,  // G major → G3
  '10A': 54, // B minor → B3 (F#3)
  '10B': 51, // D major → D3
  '11A': 55, // F# minor → F#3
  '11B': 52, // A major → A3
  '12A': 56, // C# minor → Db4 (C#3)
  '12B': 53, // E major → E3
};

// Chord intervals: root, major third/minor third, perfect fifth
function getChordNotes(rootMidi, mode) {
  var isA = mode === 'A'; // A = minor, B = major
  if (isA) {
    return [rootMidi, rootMidi + 3, rootMidi + 7]; // minor triad
  }
  return [rootMidi, rootMidi + 4, rootMidi + 7]; // major triad
}

function playKeyChord(camelotKey) {
  if (!camelotKey) return;

  var root = CAMELOT_TO_ROOT[camelotKey];
  if (!root) return;

  var mode = camelotKey[camelotKey.length - 1];
  var notes = getChordNotes(root, mode);

  if (!_keyPreviewCtx) {
    _keyPreviewCtx = new (window.AudioContext || window.webkitAudioContext)();
  }

  var ctx = _keyPreviewCtx;
  var now = ctx.currentTime;

  // Resume if suspended (autoplay policy)
  if (ctx.state === 'suspended') ctx.resume();

  // Add bass octave for richer sound
  notes = notes.concat(notes.map(function(n) { return n - 12; }));

  notes.forEach(function(midiNote, i) {
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();

    var freq = 440 * Math.pow(2, (midiNote - 69) / 12);
    osc.type = i < 3 ? 'triangle' : 'sine'; // upper triad = triangle, bass = sine
    osc.frequency.setValueAtTime(freq, now);

    gain.gain.setValueAtTime(0.12, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 1.5);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 1.5);
  });

  // Flash the key element if visible
  var keyEl = document.querySelector('.dock-hero-key');
  if (keyEl) {
    keyEl.style.transition = 'transform 0.1s, background 0.1s';
    keyEl.style.transform = 'scale(1.1)';
    keyEl.style.background = 'var(--acc)';
    keyEl.style.borderRadius = '6px';
    setTimeout(function() {
      keyEl.style.transform = '';
      keyEl.style.background = '';
    }, 200);
  }
}

// Piano-style visual key display (for detail dock)
function renderPianoKey(keyStr) {
  if (!keyStr) return '';
  if (!CAMELOT_TO_ROOT.hasOwnProperty(keyStr)) return '';

  var root = CAMELOT_TO_ROOT[keyStr];
  var isBlack = [1, 3, 6, 8, 10].indexOf(root % 12) !== -1;
  var noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  var noteName = noteNames[root % 12];

  var keyClass = isBlack ? 'piano-key-black' : 'piano-key-white';

  var el = document.createElement('div');
  el.className = 'piano-key ' + keyClass;
  el.setAttribute('data-key', keyStr);
  el.title = 'Play ' + noteName + ' ' + (keyStr[keyStr.length - 1] === 'A' ? 'minor' : 'major') + ' chord';

  var labelSpan = document.createElement('span');
  labelSpan.className = 'piano-key-label';
  labelSpan.textContent = noteName;
  el.appendChild(labelSpan);

  var camelotSpan = document.createElement('span');
  camelotSpan.className = 'piano-key-camelot';
  camelotSpan.textContent = keyStr;
  el.appendChild(camelotSpan);

  return el.outerHTML;
}

// --- ES module bridge ---
window.initKeyPreview = initKeyPreview;
window.playKeyChord = playKeyChord;
window.renderPianoKey = renderPianoKey;
