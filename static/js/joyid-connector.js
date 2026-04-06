/**
 * joyid-connector.js
 * Lightweight JoyID connector for wyltekindustries.com
 *
 * Uses @joyid/common internals directly:
 * - Chrome/Chromium + mobile: popup flow (native passkey relay works)
 * - Brave / Firefox / other: full redirect flow via authWithRedirect()
 *   Result comes back as ?_data_=<encoded> on the redirectURL page.
 *
 * Usage:
 *   import { joyidConnect, joyidHandleCallback, isJoyIDCallback } from '/js/joyid-connector.js';
 *
 *   // Connect:
 *   const { address, pubkey } = await joyidConnect({ redirectURL, network, joyidAppURL });
 *
 *   // On callback page (or same page on redirect return):
 *   if (isJoyIDCallback()) {
 *     const result = joyidHandleCallback();  // parse result from URL
 *   }
 */

const JOYID_APP_URL = 'https://testnet.joyid.dev';
const JOYID_REDIRECT_KEY = 'joyid-redirect';
const JOYID_PENDING_KEY  = 'joyid_pending';
const COMMON_ESM = 'https://esm.sh/@joyid/common@0.2.1';

let _common = null;
async function loadCommon() {
  if (_common) return _common;
  _common = await import(COMMON_ESM);
  return _common;
}

function supportsPasskeyRelay() {
  const ua = navigator.userAgent;
  const isMobile = /Mobi|Android|iPhone|iPad/i.test(ua);
  if (isMobile) return true;
  if (/Firefox/.test(ua)) return false;
  if (/Edg\//.test(ua)) return false;
  if (typeof navigator.brave !== 'undefined') return false;
  if (!!(window.chrome) && /Chrome/.test(ua)) return true;
  return false;
}

// Firefox doesn't support CTAP2 hybrid (cross-device QR) well — redirect flow
// hits a dead end. Better to tell them than leave them stuck.
export function isFirefoxDesktop() {
  const ua = navigator.userAgent;
  return /Firefox/.test(ua) && !/Mobi|Android/i.test(ua);
}

/**
 * Check if this page load is a JoyID redirect callback.
 */
export function isJoyIDCallback() {
  return new URL(window.location.href).searchParams.has(JOYID_REDIRECT_KEY);
}

/**
 * Parse the JoyID redirect result from the current URL.
 * Call this on the redirectURL page when isJoyIDCallback() returns true.
 * Returns { address, pubkey, keyType, alg, ... } or throws on error.
 */
export async function joyidHandleCallback() {
  const common = await loadCommon();
  // authCallback parses ?_data_= from current URL
  const result = common.authCallback();
  return result;
}

/**
 * Connect to JoyID wallet.
 * Returns AuthResponseData: { address, pubkey, keyType, alg, ... }
 *
 * @param {object} opts
 * @param {string} opts.redirectURL - URL to return to after redirect auth
 * @param {string} [opts.network]   - 'mainnet' | 'testnet'
 * @param {string} [opts.joyidAppURL] - Override JoyID app URL
 */
export async function joyidConnect(opts = {}) {
  const {
    redirectURL = window.location.href,
    network     = 'mainnet',
    joyidAppURL = JOYID_APP_URL,
  } = opts;

  const common = await loadCommon();

  // Init config
  if (common.initConfig) {
    common.initConfig({ joyidAppURL, network });
  }

  const request = { redirectURL, network, joyidAppURL };

  if (supportsPasskeyRelay()) {
    // Popup flow — relay works in this browser
    const result = await Promise.race([
      common.authWithPopup(request),
      new Promise((_, rej) =>
        setTimeout(() => rej(new Error('JoyID connect timed out — try again or use a different browser')), 60000)
      ),
    ]);
    return result;
  } else {
    // Redirect flow — navigates away, returns via redirectURL
    // Store pending state so the return page knows to complete sign-in
    sessionStorage.setItem(JOYID_PENDING_KEY, JSON.stringify({ returnTo: window.location.href }));
    common.authWithRedirect(request);
    // Never resolves — page navigates away
    return new Promise(() => {});
  }
}

/**
 * Get pending redirect state (set before navigating away).
 */
export function getJoyIDPending() {
  const raw = sessionStorage.getItem(JOYID_PENDING_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

/**
 * Clear pending redirect state.
 */
export function clearJoyIDPending() {
  sessionStorage.removeItem(JOYID_PENDING_KEY);
}
