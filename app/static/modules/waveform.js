// ============================================================================
// Waveform Visualiser — Web Audio API
// ============================================================================

(function initWaveformVisualiser() {
  var analyser = null;
  var canvasCtx = null;

  function setupAudioContext(audioEl) {
    if (analyser) return; // already connected
    try {
      var audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      var source = audioCtx.createMediaElementSource(audioEl);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      analyser.connect(audioCtx.destination);
    } catch (e) {
      // Web Audio unavailable — waveform shows idle bars only
    }
  }

  function drawFrame() {
    var canvas = document.getElementById('waveform-canvas');
    if (!canvas) return;
    requestAnimationFrame(drawFrame);

    var W = canvas.clientWidth;
    var H = canvas.clientHeight;
    if (W === 0 || H === 0) return;
    canvas.width = W;
    canvas.height = H;

    var ctx = canvasCtx || (canvasCtx = canvas.getContext('2d'));
    ctx.clearRect(0, 0, W, H);

    var style = getComputedStyle(document.documentElement);
    var accColor = style.getPropertyValue('--acc').trim() || '#8b5cf6';
    var dimColor = style.getPropertyValue('--acc-dim').trim() || 'rgba(139,92,246,0.12)';

    var BAR_COUNT = 64;
    var gap = 1;
    var barW = Math.max(1, Math.floor((W - gap * (BAR_COUNT - 1)) / BAR_COUNT));

    var freqData = null;
    if (analyser) {
      freqData = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(freqData);
    }

    for (var i = 0; i < BAR_COUNT; i++) {
      var amp = freqData
        ? freqData[Math.floor(i * freqData.length / BAR_COUNT)] / 255
        : 0.06;
      var barH = Math.max(2, amp * H * 0.85);
      var x = i * (barW + gap);
      var y = (H - barH) / 2;

      ctx.fillStyle = amp > 0.08 ? accColor : dimColor;
      ctx.beginPath();
      var r = Math.min(2, barW / 2);
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + barW - r, y);
      ctx.arcTo(x + barW, y, x + barW, y + r, r);
      ctx.lineTo(x + barW, y + barH - r);
      ctx.arcTo(x + barW, y + barH, x + barW - r, y + barH, r);
      ctx.lineTo(x + r, y + barH);
      ctx.arcTo(x, y + barH, x, y + barH - r, r);
      ctx.lineTo(x, y + r);
      ctx.arcTo(x, y, x + r, y, r);
      ctx.closePath();
      ctx.fill();
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    var audioEl = document.getElementById('audio-player');
    if (!audioEl) return;

    // Set up audio context on first user interaction (browser autoplay policy)
    audioEl.addEventListener('play', function() {
      setupAudioContext(audioEl);
    }, { once: true });

    drawFrame();
  });
})();
