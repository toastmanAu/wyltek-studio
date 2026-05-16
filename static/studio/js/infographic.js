// Infographic page entry — thin dispatcher between Catalog (default) and
// Freeform tabs. Each tab is a module under ./infographic/ that owns its
// own DOM panel inside the page.

import { initFreeformMode } from './infographic/freeform-mode.js';
import { initCatalogMode } from './infographic/catalog-mode.js';

const STORAGE_KEY = 'infographic.activeTab';
const VALID_TABS = ['catalog', 'freeform'];

function getInitialTab() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return VALID_TABS.includes(stored) ? stored : 'catalog';
}

function setActiveTab(name) {
  if (!VALID_TABS.includes(name)) return;
  localStorage.setItem(STORAGE_KEY, name);
  for (const tab of VALID_TABS) {
    const btn = document.getElementById(`tab-${tab}`);
    const panel = document.getElementById(`panel-${tab}`);
    if (btn) {
      btn.setAttribute('aria-selected', String(tab === name));
      btn.classList.toggle('active', tab === name);
    }
    if (panel) {
      panel.hidden = tab !== name;
    }
  }
  if (name === 'catalog') initCatalogMode();
  if (name === 'freeform') initFreeformMode();
}

function wireTabButtons() {
  for (const tab of VALID_TABS) {
    const btn = document.getElementById(`tab-${tab}`);
    if (btn) btn.addEventListener('click', () => setActiveTab(tab));
  }
}

// Boot
wireTabButtons();
setActiveTab(getInitialTab());
