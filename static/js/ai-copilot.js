/* Wyltek Studio AI Copilot — powered by page-agent + local Ollama */

(function () {
  const OLLAMA_BASE_URL = 'http://localhost:11434/v1';
  const OLLAMA_MODEL    = 'qwen2.5:14b';

  const PAGE_CONTEXT = {
    '/':               'Generate — AI image generation. Main prompt input: #prompt. Backend selector: #backend-select. Generate button: #generate-btn.',
    '/studio/tts':     'TTS Studio — text-to-speech. Text input: #tts-text. Voice selector: #voice-select. Generate button: #tts-generate.',
    '/studio/music':   'Music Studio — AI music generation. Prompt input: #music-prompt. Generate button: #music-generate.',
    '/studio/video':   'Video Studio — AI video composition. Prompt input: #video-prompt. Generate button: #video-generate.',
    '/studio/sprites': 'Sprite Forge — game sprite editor and AI sprite generation.',
    '/studio/meme':    `Meme Forge — AI meme template generator.

Tabs: switchTab('generate'), switchTab('upload'), switchTab('template').
Always use the template tab for meme requests.

To apply a template and fill text:
  window.applyMemeTemplate('drake', { top: 'JavaScript', bot: 'Rust' })

To then generate the image:
  window.generateMemeFromCopilot()

To list all available templates with their panel slots:
  window.listMemeTemplates()

Common templates and their slots:
  drake              { top: "thing rejected", bot: "thing approved" }
  change-my-mind     { bot: "the controversial opinion" }
  distracted-bf      { top: "the distraction", bot: "what is ignored", mid: "who is distracted" }
  this-is-fine       { top: "the disaster", bot: "person's attitude" }
  expanding-brain    { top: "basic idea", mid: "mid tier", mid2: "big brain", bot: "galaxy brain" }
  woman-yelling-cat  { top: "angry person says", bot: "cat's response" }
  doge               { top: "wow text", bot: "secondary text" }
  two-buttons        { top: "option 1", bot: "option 2" }
  one-does-not-simply { top: "one does not simply...", bot: "...the hard thing" }
  galaxy-brain       { top: "the genius take", bot: "why it works (optional)" }

Always use ALL CAPS for meme text. Keep each panel to 1-2 short punchy phrases.`,
    '/files':          'Files — file manager for generated outputs.',
    '/projects':       'Projects — project manager.',
    '/settings':       'Settings — configure backends, models, and API keys.',
  };

  function getPageContext() {
    const path = window.location.pathname;
    for (const [prefix, ctx] of Object.entries(PAGE_CONTEXT)) {
      if (prefix === '/' ? path === '/' : path.startsWith(prefix)) return ctx;
    }
    return `Page: ${path}`;
  }

  function buildSystemPrompt() {
    return `You are the AI copilot for Wyltek Studio — a local AI creative suite.

Current page: ${getPageContext()}

Navigation: to go to another section, click its link in the left sidebar nav. Links are:
  Generate (/), TTS Studio (/studio/tts), Music Studio (/studio/music),
  Video Studio (/studio/video), Sprite Forge (/studio/sprites), Meme Forge (/studio/meme),
  Files (/files), Projects (/projects), Settings (/settings).

To optimize a prompt using the built-in prompt optimizer, use execute_javascript like this:
  const res = await fetch('/api/op-prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: 'USER_PROMPT', mode: 'image' })
  });
  const data = await res.json();
  return data.enhanced_prompt || JSON.stringify(data);

Mode can be "image", "video", or "sprite".

To check available backends/models:
  const res = await fetch('/api/backends'); return await res.json();

Do not navigate to external URLs. All actions stay within this app.`;
  }

  function initCopilot() {
    const PageAgent = window.PageAgent;
    if (!PageAgent) {
      console.error('[Copilot] window.PageAgent not found — page-agent.js may not have loaded');
      return;
    }

    // Dispose the demo auto-instance if it was created
    if (window.pageAgent && typeof window.pageAgent.dispose === 'function') {
      window.pageAgent.dispose();
    }

    const agent = new PageAgent({
      baseURL:    OLLAMA_BASE_URL,
      model:      OLLAMA_MODEL,
      apiKey:     'NA',
      language:   'en-US',
      maxSteps:   25,
      stepDelay:  0.4,

      instructions: { system: buildSystemPrompt() },

      // Allow JS execution so the agent can call /api/op-prompt and other local APIs
      experimentalScriptExecutionTool: true,

      // Don't let the agent accidentally click the copilot button itself
      interactiveBlacklist: [
        () => document.getElementById('ai-copilot-btn'),
      ],

      onAskUser: (question) =>
        new Promise(resolve => resolve(window.prompt(`Copilot: ${question}`) || '')),

      onAfterStep: (_agent, history) => {
        const last = history[history.length - 1];
        if (last) console.debug('[Copilot] step:', last.type || last);
      },
    });

    window.pageAgent = agent;

    // Wire trigger button
    const btn = document.getElementById('ai-copilot-btn');
    if (btn) {
      btn.addEventListener('click', () => {
        if (!agent.panel) return;
        agent.panel.isVisible() ? agent.panel.hide() : agent.panel.show();
      });
      btn.style.opacity = '1';
      btn.title = 'AI Copilot (Ollama · ' + OLLAMA_MODEL + ')';
    }
  }

  // Inject page-agent script, then init once loaded
  document.addEventListener('DOMContentLoaded', () => {
    const script = document.createElement('script');
    script.src = '/static/js/page-agent.js';
    script.onload  = initCopilot;
    script.onerror = () => console.error('[Copilot] Failed to load /static/js/page-agent.js');
    document.head.appendChild(script);
  });
})();
