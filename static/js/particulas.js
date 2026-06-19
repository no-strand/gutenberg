/**
 * Efeito visual de partículas usado como elemento estético em páginas do projeto.
 */

// static/particles.js
// Partículas com rampa de cores multi-stop: branco -> azul -> amarelo -> rosa
(function () {
  'use strict';

  const DEFAULTS = {
    canvasId: 'bg-canvas',
    particleCount: 80,
    maxDist: 160,
    baseSpeed: 60,
    backgroundColor: 'rgba(18,20,23,1)',
    // rampa de cores (RGB arrays). Ordem: very far (white), blue, yellow, pink (near)
    stops: [
      { t: 0.00, rgb: [230, 234, 240] }, // claro
      { t: 0.33, rgb: [47, 93, 140] }, // azul principal
      { t: 0.66, rgb: [217, 164, 65] }, // dourado
      { t: 1.00, rgb: [90, 79, 207] }  // violeta
    ],
    lineAlphaMult: 1.25,
    particleAlpha: 1.0
  };

  let canvas = null;
  let ctx = null;
  let DPR = 1;
  let WIDTH = 0;
  let HEIGHT = 0;
  let particles = [];
  let rafId = null;
  let last = 0;
  let _paused = true;
  let mouse = { x: 0, y: 0, active: false };
  let inited = false;

  class Particle {
    constructor(W, H) { this.reset(W, H); }
    reset(W, H) {
      this.x = Math.random() * (W || 100);
      this.y = Math.random() * (H || 100);
      const SPEED = DEFAULTS.baseSpeed;
      this.vx = (Math.random() - 0.5) * SPEED;
      this.vy = (Math.random() - 0.5) * SPEED;
      this.r = 1 + Math.random() * 2.6;
      this._colorCache = [255,255,255]; // rgb
    }
    update(W, H, dt) {
      this.x += this.vx * dt;
      this.y += this.vy * dt;
      if (this.x < -20 || this.x > W + 20 || this.y < -20 || this.y > H + 20) {
        this.reset(W, H);
      }
    }
    draw(ctxLocal) {
      ctxLocal.beginPath();
      ctxLocal.fillStyle = rgbaString(this._colorCache, DEFAULTS.particleAlpha);
      ctxLocal.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctxLocal.fill();
    }
  }

  // util: clamp
  /** Clamp. Usada pelo fluxo principal da aplicação. */
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  // util: linear interp
  /** Lerp. Usada pelo fluxo principal da aplicação. */
  function lerp(a, b, t) { return a + (b - a) * t; }

  // interpola entre dois arrays RGB
  /** Lerprgb. Usada pelo fluxo principal da aplicação. */
  function lerpRGB(a, b, t) {
    return [
      Math.round(lerp(a[0], b[0], t)),
      Math.round(lerp(a[1], b[1], t)),
      Math.round(lerp(a[2], b[2], t))
    ];
  }

  // dado t em [0,1], busca os dois stops entre os quais t está e interpola
  /** Colorfort. Usada pelo fluxo principal da aplicação. */
  function colorForT(t) {
    t = clamp(t, 0, 1);
    const stops = DEFAULTS.stops;
    // se t estiver abaixo do primeiro ou acima do último:
    if (t <= stops[0].t) return stops[0].rgb.slice();
    if (t >= stops[stops.length - 1].t) return stops[stops.length - 1].rgb.slice();
    // encontra intervalo
    for (let i = 0; i < stops.length - 1; i++) {
      const a = stops[i], b = stops[i + 1];
      if (t >= a.t && t <= b.t) {
        const localT = (t - a.t) / (b.t - a.t);
        return lerpRGB(a.rgb, b.rgb, localT);
      }
    }
    return stops[stops.length - 1].rgb.slice();
  }

  // rgba string builder
  /** Rgbastring. Usada pelo fluxo principal da aplicação. */
  function rgbaString(rgbArr, alpha) {
    return 'rgba(' + rgbArr[0] + ',' + rgbArr[1] + ',' + rgbArr[2] + ',' + (alpha === undefined ? 1 : alpha.toFixed(3)) + ')';
  }

  /** Safegetcanvas. Usada pelo fluxo principal da aplicação. */
  function safeGetCanvas(id) {
    try { return document.getElementById(id); } catch (e) { return null; }
  }

  /** Resizecanvas. Usada pelo fluxo principal da aplicação. */
  function resizeCanvas() {
    if (!canvas || !ctx) return;
    DPR = Math.max(1, window.devicePixelRatio || 1);
    WIDTH = window.innerWidth;
    HEIGHT = window.innerHeight;
    canvas.style.width = WIDTH + 'px';
    canvas.style.height = HEIGHT + 'px';
    canvas.width = Math.max(1, Math.floor(WIDTH * DPR));
    canvas.height = Math.max(1, Math.floor(HEIGHT * DPR));
    if (typeof ctx.setTransform === 'function') ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  /** Initparticles. Usada pelo fluxo principal da aplicação. */
  function initParticles(count) {
    particles = [];
    const n = Number.isInteger(count) ? count : DEFAULTS.particleCount;
    for (let i = 0; i < n; i++) particles.push(new Particle(WIDTH, HEIGHT));
  }

  // calcula cor da partícula baseado na proximidade do vizinho mais próximo (ou mouse)
  /** Computeparticlecolors. Usada pelo fluxo principal da aplicação. */
  function computeParticleColors() {
    const maxd2 = DEFAULTS.maxDist * DEFAULTS.maxDist;
    // para cada partícula, encontra distância mínima ao outro / mouse e cacheia cor
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      let minD2 = Infinity;
      // checar mouse também (se ativo)
      if (mouse.active) {
        const dxm = p.x - mouse.x, dym = p.y - mouse.y, d2m = dxm*dxm + dym*dym;
        if (d2m < minD2) minD2 = d2m;
      }
      for (let j = 0; j < particles.length; j++) {
        if (i === j) continue;
        const q = particles[j];
        const dx = p.x - q.x, dy = p.y - q.y;
        const d2 = dx*dx + dy*dy;
        if (d2 < minD2) minD2 = d2;
      }
      // t = 1 quando muito perto; t = 0 quando longe (além do max)
      let t = 0;
      if (minD2 !== Infinity) {
        t = clamp(1 - (minD2 / maxd2), 0, 1);
      }
      // para partículas bem longe, queremos tom muito próximo do branco stop(0).
      const rgb = colorForT(t);
      p._colorCache = rgb;
    }
  }

  /** Frame. Usada pelo fluxo principal da aplicação. */
  function frame(now) {
    try {
      rafId = requestAnimationFrame(frame);
      if (_paused) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;

      for (let p of particles) p.update(WIDTH, HEIGHT, dt);

      // fundo sólido
      ctx.fillStyle = DEFAULTS.backgroundColor;
      ctx.fillRect(0, 0, WIDTH, HEIGHT);

      const maxd2 = DEFAULTS.maxDist * DEFAULTS.maxDist;

      // pré-computa as cores das partículas (com base no vizinho mais próximo / mouse)
      computeParticleColors();

      // desenha linhas entre partículas com rampa de cor por proximidade
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 <= maxd2) {
            const t = clamp(1 - (d2 / maxd2), 0, 1); // 0 = longe, 1 = perto
            const rgb = colorForT(t);
            const alpha = Math.max(0.06, DEFAULTS.lineAlphaMult * t);
            ctx.beginPath();
            ctx.strokeStyle = rgbaString(rgb, alpha);
            ctx.lineWidth = 0.8 * (0.4 + 0.6 * t);
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      // ligação ao mouse (mesma rampa)
      if (mouse.active) {
        for (let p of particles) {
          const dx = p.x - mouse.x, dy = p.y - mouse.y, d2 = dx*dx + dy*dy;
          if (d2 <= maxd2) {
            const t = clamp(1 - (d2 / maxd2), 0, 1);
            const rgb = colorForT(t);
            const alpha = Math.max(0.06, DEFAULTS.lineAlphaMult * t);
            ctx.beginPath();
            ctx.strokeStyle = rgbaString(rgb, alpha);
            ctx.lineWidth = 0.9 * (0.4 + 0.6 * t);
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(mouse.x, mouse.y);
            ctx.stroke();
          }
        }
        // ponteiro com cor próxima do "quente" (t ~ 0.95)
        const pointerRgb = colorForT(0.95);
        ctx.beginPath();
        ctx.fillStyle = rgbaString(pointerRgb, 1);
        ctx.arc(mouse.x, mouse.y, 3, 0, Math.PI*2);
        ctx.fill();
      }

      // desenha partículas (com cor cacheada)
      for (let p of particles) p.draw(ctx);

    } catch (err) {
      console.warn('particles frame error:', err);
    }
  }

  /** Pointermovehandler. Usada pelo fluxo principal da aplicação. */
  function pointerMoveHandler(e) { mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true; }
  function pointerLeaveHandler() { mouse.active = false; }

  /** Attachlisteners. Usada pelo fluxo principal da aplicação. */
  function attachListeners() {
    window.addEventListener('resize', resizeCanvas, { passive: true });
    window.addEventListener('pointermove', pointerMoveHandler, { passive: true });
    window.addEventListener('pointerleave', pointerLeaveHandler, { passive: true });
  }

  /** Detachlisteners. Usada pelo fluxo principal da aplicação. */
  function detachListeners() {
    try {
      window.removeEventListener('resize', resizeCanvas);
      window.removeEventListener('pointermove', pointerMoveHandler);
      window.removeEventListener('pointerleave', pointerLeaveHandler);
    } catch (e) { /* noop */ }
  }

  /** Startloop. Usada pelo fluxo principal da aplicação. */
  function startLoop() {
    if (rafId) return;
    last = performance.now();
    rafId = requestAnimationFrame(frame);
  }

  /** Stoploop. Usada pelo fluxo principal da aplicação. */
  function stopLoop() {
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
  }

  /** Init. Usada pelo fluxo principal da aplicação. */
  function init(opts) {
    if (inited) return true;
    try {
      const cfg = Object.assign({}, opts || {});
      // mescla stops se fornecido
      if (cfg.stops && Array.isArray(cfg.stops)) DEFAULTS.stops = cfg.stops;
      if (typeof cfg.particleCount === 'number') DEFAULTS.particleCount = cfg.particleCount;
      if (typeof cfg.maxDist === 'number') DEFAULTS.maxDist = cfg.maxDist;
      if (typeof cfg.baseSpeed === 'number') DEFAULTS.baseSpeed = cfg.baseSpeed;
      if (typeof cfg.backgroundColor === 'string') DEFAULTS.backgroundColor = cfg.backgroundColor;
      if (typeof cfg.lineAlphaMult === 'number') DEFAULTS.lineAlphaMult = cfg.lineAlphaMult;

      const canvasId = cfg.canvasId || DEFAULTS.canvasId;
      canvas = safeGetCanvas(canvasId);
      if (!canvas) {
        console.warn('particles: canvas not found:', canvasId);
        return false;
      }
      if (typeof canvas.getContext !== 'function') {
        console.warn('particles: canvas.getContext not available');
        return false;
      }
      ctx = canvas.getContext('2d', { alpha: true });
      if (!ctx) { console.warn('particles: failed to get 2d context'); return false; }

      resizeCanvas();
      initParticles(DEFAULTS.particleCount);
      attachListeners();

      _paused = false;
      startLoop();

      try { canvas.style.pointerEvents = 'none'; } catch (e) {}
      inited = true;
      return true;
    } catch (e) {
      console.warn('particles init error:', e);
      return false;
    }
  }

  /** Setpaused. Usada pelo fluxo principal da aplicação. */
  function setPaused(v) {
    _paused = !!v;
    if (_paused) stopLoop();
    else startLoop();
  }

  /** Ispaused. Usada pelo fluxo principal da aplicação. */
  function isPaused() { return !!_paused; }

  /** Destroy. Usada pelo fluxo principal da aplicação. */
  function destroy() {
    stopLoop();
    detachListeners();
    canvas = null;
    ctx = null;
    particles = [];
    inited = false;
  }

  window.bgParticles = {
    init,
    setPaused,
    isPaused,
    destroy
  };

  // helper globals para compatibilidade com seu index.js anterior
  window.setBgAnimationPaused = function (v) { try { if (window.bgParticles && typeof window.bgParticles.setPaused === 'function') window.bgParticles.setPaused(v); } catch (e) {} };
  window.isBgAnimationPaused = function () { try { return window.bgParticles && typeof window.bgParticles.isPaused === 'function' ? window.bgParticles.isPaused() : false; } catch (e) { return false; } };

  // auto-init quando houver canvas na página
  /** Shoulddisableforcurrentpage. Usada pelo fluxo principal da aplicação. */
  function shouldDisableForCurrentPage() {
    try {
      const body = document.body;
      const isEditorPage = body?.dataset?.editorPage === 'true';
      const editorEffectsEnabled = body?.dataset?.editorEffectsEnabled !== 'false';
      return !!isEditorPage && !editorEffectsEnabled;
    } catch (e) {
      return false;
    }
  }

  /** Applydisabledstate. Usada pelo fluxo principal da aplicação. */
  function applyDisabledState() {
    try {
      const canvasEl = document.getElementById(DEFAULTS.canvasId);
      if (canvasEl) canvasEl.style.display = 'none';
      const camada = document.querySelector('.bg-camada-roxa');
      if (camada) camada.style.display = 'none';
      if (window.bgParticles && typeof window.bgParticles.destroy === 'function') window.bgParticles.destroy();
    } catch (e) {
      console.warn('particles disable error:', e);
    }
  }

  /** Tryautoinit. Usada pelo fluxo principal da aplicação. */
  function tryAutoInit() {
    try {
      if (shouldDisableForCurrentPage()) {
        applyDisabledState();
        return;
      }
      const cand = document.getElementById(DEFAULTS.canvasId);
      if (cand) {
        const ok = init();
        if (!ok) console.warn('particles: init attempted but returned false');
      }
    } catch (e) {
      console.warn('particles auto-init error:', e);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryAutoInit);
  } else {
    tryAutoInit();
  }

})();

window.addEventListener("load", () => {
  const body = document.body;
  const isEditorPage = body?.dataset?.editorPage === 'true';
  const editorEffectsEnabled = body?.dataset?.editorEffectsEnabled !== 'false';
  const canvas = document.getElementById("bg-canvas");
  const camada = document.querySelector('.bg-camada-roxa');
  if (isEditorPage && !editorEffectsEnabled) {
    if (canvas) canvas.style.display = "none";
    if (camada) camada.style.display = "none";
    return;
  }
  if (canvas) canvas.style.display = "block";
  if (camada) camada.style.display = "block";
});
