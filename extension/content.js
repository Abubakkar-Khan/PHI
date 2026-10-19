// Counts how many different Shorts were viewed in this tab (a "scroll" signal).
// Reads only the URL path. Nothing is stored or sent anywhere but the background script.
(() => {
  let last = "";
  let count = 0;
  function check() {
    const m = location.pathname.match(/^\/shorts\/([^/?#]+)/);
    if (m && m[1] !== last) {
      last = m[1];
      count += 1;
      chrome.runtime.sendMessage({ type: "swipes", count }).catch(() => {});
    } else if (!m) {
      last = "";
    }
  }
  setInterval(check, 800);
  check();
})();
