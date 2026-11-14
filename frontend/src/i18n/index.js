import en from "./en.json";
import fr from "./fr.json";
import ar from "./ar.json";

const translations = { en, fr, ar };

/**
 * Get a translation for a dot-separated key path.
 * Falls back to the key itself if not found.
 */
export function t(lang = "en", keyPath = "") {
  const dict = translations[lang] || translations.en;
  const parts = keyPath.split(".");
  let cur = dict;
  for (const part of parts) {
    if (cur && typeof cur === "object" && part in cur) {
      cur = cur[part];
    } else {
      return keyPath; // fallback: return raw key
    }
  }
  return cur;
}

export function getTranslation(lang, key) {
  return t(lang, key);
}

export { en, fr, ar };
