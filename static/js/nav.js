/* Shared sidebar navigation — include on every page */

(function() {
  const NAV_ITEMS = [
    { section: 'Create' },
    { href: '/',           icon: '&#9998;',  label: 'Generate',    id: 'generate' },
    { href: '/studio/tts', icon: '&#9835;',  label: 'TTS Studio',  id: 'tts' },
    { href: '/studio/music', icon: '&#127925;', label: 'Music Studio', id: 'music' },
    { href: '/studio/video', icon: '&#127909;', label: 'Video Studio', id: 'video' },
    { href: '/studio/meme',    icon: '&#128514;', label: 'Meme Forge',   id: 'meme' },
    { href: '/studio/frames',  icon: '&#127916;', label: 'Frame Cutter', id: 'frames' },
    { href: '/studio/remix',       icon: '&#127912;', label: 'Style Remix',  id: 'remix' },
    { href: '/studio/image-edit',  icon: '&#9986;', label: 'Image Edit', id: 'image-edit' },
    { href: '/studio/mesh-edit',   icon: '&#129683;', label: 'Mesh Edit', id: 'mesh-edit' },
    { href: '/studio/video-tools', icon: '&#127902;', label: 'Video Tools', id: 'video-tools' },
    { href: '/studio/audio', icon: '&#127911;', label: 'Audio Tools', id: 'audio' },
    { href: '/studio/beats', icon: '&#127928;', label: 'Beat Builder', id: 'beats' },
    { href: '/studio/worldgen', icon: '&#127757;', label: 'Worldgen', id: 'worldgen' },
    { href: '/studio/infographic', icon: '&#128202;', label: 'Infographic', id: 'infographic' },
    { section: 'Manage' },
    { href: '/files',      icon: '&#128194;', label: 'Files',      id: 'files' },
    { section: 'Produce' },
    { href: '/projects',   icon: '&#127916;', label: 'Projects',   id: 'projects' },
    { section: 'System' },
    { href: '/settings',   icon: '&#9881;',  label: 'Settings',    id: 'settings' },
  ];

  // Determine active page from current path
  const path = window.location.pathname;
  let activeId = 'generate';
  if (path.startsWith('/studio/remix')) activeId = 'remix';
  else if (path.startsWith('/studio/meme')) activeId = 'meme';
  else if (path.startsWith('/studio/frames')) activeId = 'frames';
  else if (path.startsWith('/studio/image-edit') || path.startsWith('/studio/image-tools')) activeId = 'image-edit';
  else if (path.startsWith('/studio/mesh-edit')) activeId = 'mesh-edit';
  else if (path.startsWith('/studio/video-tools')) activeId = 'video-tools';
  else if (path.startsWith('/studio/video')) activeId = 'video';
  else if (path.startsWith('/studio/music')) activeId = 'music';
  else if (path.startsWith('/studio/beats')) activeId = 'beats';
  else if (path.startsWith('/studio/audio')) activeId = 'audio';
  else if (path.startsWith('/studio/infographic')) activeId = 'infographic';
  else if (path.startsWith('/studio/tts')) activeId = 'tts';
  else if (path.startsWith('/studio/worldgen')) activeId = 'worldgen';
  else if (path.startsWith('/projects')) activeId = 'projects';
  else if (path.startsWith('/files')) activeId = 'files';
  else if (path.startsWith('/settings')) activeId = 'settings';

  // Build sidebar HTML
  const sidebar = document.createElement('nav');
  sidebar.className = 'sidebar-nav';
  sidebar.id = 'sidebar-nav';

  // Restore collapsed state
  if (localStorage.getItem('ws-nav-collapsed') === '1') {
    sidebar.classList.add('collapsed');
  }

  let linksHtml = '';
  NAV_ITEMS.forEach(item => {
    if (item.section) {
      linksHtml += `<div class="nav-section">${item.section}</div>`;
    } else {
      const active = item.id === activeId ? ' active' : '';
      linksHtml += `<a href="${item.href}" class="nav-link${active}">
        <span class="nav-icon">${item.icon}</span>
        <span class="nav-label">${item.label}</span>
      </a>`;
    }
  });

  sidebar.innerHTML = `
    <div class="sidebar-brand">
      <div class="brand-icon">W</div>
      <span class="brand-text">Wyltek Studio</span>
    </div>
    <div class="sidebar-links">${linksHtml}</div>
    <div class="sidebar-footer">
      <button id="ai-copilot-btn" class="nav-link ai-copilot-btn" style="opacity:0.4" title="Loading AI Copilot...">
        <span class="nav-icon">&#10024;</span>
        <span class="nav-label">AI Copilot</span>
      </button>
      <button class="sidebar-toggle" onclick="window._toggleNav()">
        <span class="toggle-icon">&#9664;</span>
        <span class="toggle-label">Collapse</span>
      </button>
    </div>
  `;

  // Mobile header
  const mobileHeader = document.createElement('div');
  mobileHeader.className = 'mobile-header';
  mobileHeader.innerHTML = `
    <button class="hamburger" onclick="window._openMobileNav()">&#9776;</button>
    <span class="mobile-title">Wyltek Studio</span>
  `;

  // Mobile overlay
  const overlay = document.createElement('div');
  overlay.className = 'sidebar-overlay';
  overlay.id = 'sidebar-overlay';
  overlay.onclick = () => window._closeMobileNav();

  // Wrap existing body content
  document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    const children = Array.from(body.childNodes);

    // Create app shell
    const shell = document.createElement('div');
    shell.className = 'app-shell';

    const pageContent = document.createElement('div');
    pageContent.className = 'page-content';
    pageContent.appendChild(mobileHeader);

    // Move all existing body children into page-content
    children.forEach(child => pageContent.appendChild(child));

    shell.appendChild(sidebar);
    shell.appendChild(pageContent);
    body.appendChild(overlay);
    body.appendChild(shell);

    // Load AI copilot (page-agent + Ollama)
    const copilot = document.createElement('script');
    copilot.src = '/static/js/ai-copilot.js';
    document.head.appendChild(copilot);

    // Load health widget (floating top-right pill: status dots + Reset)
    const health = document.createElement('script');
    health.src = '/static/js/health-widget.js';
    document.head.appendChild(health);
  });

  // Toggle collapsed
  window._toggleNav = function() {
    const nav = document.getElementById('sidebar-nav');
    nav.classList.toggle('collapsed');
    localStorage.setItem('ws-nav-collapsed', nav.classList.contains('collapsed') ? '1' : '0');
  };

  // Mobile open/close
  window._openMobileNav = function() {
    document.getElementById('sidebar-nav').classList.add('mobile-open');
    document.getElementById('sidebar-overlay').classList.add('active');
  };
  window._closeMobileNav = function() {
    document.getElementById('sidebar-nav').classList.remove('mobile-open');
    document.getElementById('sidebar-overlay').classList.remove('active');
  };
})();
