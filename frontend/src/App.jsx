import React, { useState, useEffect, createContext, useContext } from "react";
import { t } from "./i18n";
import FieldScreen from "./screens/FieldScreen";
import PrioritiesScreen from "./screens/PrioritiesScreen";
import FuturesScreen from "./screens/FuturesScreen";

// ── App-wide state context ────────────────────────────────────────────────────
export const AppContext = createContext(null);
export function useApp() { return useContext(AppContext); }

const SCREENS = ["field", "priorities", "futures"];

export default function App() {
  const [lang, setLang] = useState("en");
  const [screen, setScreen] = useState("field");

  // Shared agronomic state (no calculations here — just user selections)
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [rotation, setRotation] = useState(["durum_wheat", "chickpea", "barley"]);
  const [weights, setWeights] = useState({ water: 1, income: 1, soil: 1, animals: 1 });
  const [availableWater, setAvailableWater] = useState("medium");

  const isRTL = lang === "ar";
  const tr = (key) => t(lang, key);

  // Field + priorities completed = futures unlocked
  const fieldReady = !!selectedRegion;
  const prioritiesReady = fieldReady; // priorities always have defaults

  const navItems = [
    { key: "field", label: tr("nav.field"), enabled: true },
    { key: "priorities", label: tr("nav.priorities"), enabled: true },
    { key: "futures", label: tr("nav.futures"), enabled: fieldReady && prioritiesReady },
  ];

  const appCtx = {
    lang, setLang,
    screen, setScreen,
    selectedRegion, setSelectedRegion,
    rotation, setRotation,
    weights, setWeights,
    availableWater, setAvailableWater,
    fieldReady, prioritiesReady,
    tr,
    isRTL,
  };

  return (
    <AppContext.Provider value={appCtx}>
      <div
        dir={isRTL ? "rtl" : "ltr"}
        className={`min-h-screen bg-cream text-forest flex flex-col ${isRTL ? "font-arabic" : "font-body"}`}
      >
        {/* ── Header ──────────────────────────────────────────────────────── */}
        <header className="sticky top-0 z-30 border-b border-sand bg-cream/90 backdrop-blur-sm px-4 py-3">
          <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-3">
            {/* Logo */}
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-9 h-9 rounded-full bg-forest flex items-center justify-center text-cream font-heading font-bold text-sm flex-shrink-0">
                S
              </span>
              <div className="min-w-0">
                <h1 className="font-heading text-xl font-bold text-forest leading-tight">{tr("app.title")}</h1>
                <p className="text-xs text-forest/60 leading-tight hidden sm:block truncate">{tr("app.subtitle")}</p>
              </div>
            </div>

            {/* Nav */}
            <nav className="flex items-center gap-1" role="navigation" aria-label="Main navigation">
              {navItems.map(({ key, label, enabled }) => (
                <button
                  key={key}
                  onClick={() => enabled && setScreen(key)}
                  disabled={!enabled}
                  aria-current={screen === key ? "page" : undefined}
                  className={`
                    px-3 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px]
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta
                    ${screen === key
                      ? "bg-forest text-cream"
                      : enabled
                        ? "text-forest hover:bg-sand cursor-pointer"
                        : "text-forest/30 cursor-not-allowed"
                    }
                  `}
                >
                  {label}
                </button>
              ))}
            </nav>

            {/* Language picker */}
            <div
              className="flex items-center gap-1 bg-sand/60 p-1 rounded-lg"
              role="group"
              aria-label="Language selector"
            >
              {["en", "fr", "ar"].map((l) => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  aria-pressed={lang === l}
                  className={`
                    px-2.5 py-1.5 rounded text-xs font-semibold transition-colors min-h-[36px] min-w-[36px]
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta
                    ${lang === l ? "bg-forest text-cream" : "text-forest hover:bg-sand"}
                  `}
                >
                  {l === "en" ? "EN" : l === "fr" ? "FR" : "عر"}
                </button>
              ))}
            </div>
          </div>
        </header>

        {/* ── Main content ─────────────────────────────────────────────────── */}
        <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">
          {screen === "field" && <FieldScreen />}
          {screen === "priorities" && <PrioritiesScreen />}
          {screen === "futures" && <FuturesScreen />}
        </main>

        {/* ── Disclaimer footer (AGENTS.md rule 12) ────────────────────────── */}
        <footer className="border-t border-sand bg-sand/50 px-4 py-3 text-center">
          <p className="text-xs text-forest/70 font-medium max-w-3xl mx-auto">
            ⚠ {tr("app.disclaimer")}
          </p>
        </footer>
      </div>
    </AppContext.Provider>
  );
}
