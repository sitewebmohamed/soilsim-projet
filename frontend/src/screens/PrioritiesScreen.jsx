import React from "react";
import { useApp } from "../App";

const PRIORITY_KEYS = ["water", "income", "soil", "animals"];
const WATER_LEVELS = ["low", "medium", "high"];

export default function PrioritiesScreen() {
  const { lang, weights, setWeights, availableWater, setAvailableWater, setScreen, fieldReady, tr } = useApp();

  const handleWeight = (key, val) => {
    setWeights((prev) => ({ ...prev, [key]: Number(val) }));
  };

  const priorityIcons = { water: "💧", income: "🌾", soil: "🌱", animals: "🐄" };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-heading text-2xl font-bold text-forest">{tr("priorities.title")}</h2>
        <p className="text-sm text-forest/60 mt-1">{tr("priorities.subtitle")}</p>
      </div>

      {/* ── Priority sliders ──────────────────────────────────────────────── */}
      <section aria-labelledby="priorities-heading" className="space-y-4">
        <h3 id="priorities-heading" className="sr-only">{tr("priorities.title")}</h3>
        {PRIORITY_KEYS.map((key) => (
          <PriorityCard
            key={key}
            icon={priorityIcons[key]}
            label={tr(`priorities.${key}`)}
            desc={tr(`priorities.${key}Desc`)}
            value={weights[key]}
            onChange={(v) => handleWeight(key, v)}
          />
        ))}
      </section>

      {/* ── Water budget selector ─────────────────────────────────────────── */}
      <section aria-labelledby="water-heading">
        <h3 id="water-heading" className="text-sm font-semibold text-forest/60 uppercase tracking-wide mb-3">
          {tr("priorities.waterBudget")}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {WATER_LEVELS.map((level) => (
            <button
              key={level}
              onClick={() => setAvailableWater(level)}
              aria-pressed={availableWater === level}
              className={`
                min-h-[56px] rounded-xl border-2 p-4 text-start transition-all
                focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta
                ${availableWater === level
                  ? "border-river bg-river text-cream"
                  : "border-dashed border-sand bg-sand/30 text-forest hover:border-river/40"
                }
              `}
            >
              <span className="font-semibold text-sm">{tr(`priorities.${level}`)}</span>
            </button>
          ))}
        </div>
      </section>

      {/* ── Navigation ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <button
          onClick={() => setScreen("field")}
          className="
            min-h-[48px] px-5 py-2.5 rounded-xl border-2 border-sand text-forest text-sm font-medium
            hover:bg-sand/50 transition-colors
            focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta
          "
        >
          {tr("priorities.back")}
        </button>
        <button
          onClick={() => fieldReady && setScreen("futures")}
          disabled={!fieldReady}
          className={`
            min-h-[48px] px-6 py-3 rounded-xl font-semibold text-sm transition-colors
            focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta focus-visible:ring-offset-2
            ${fieldReady
              ? "bg-terracotta text-cream hover:bg-terracotta/90"
              : "bg-sand text-forest/40 cursor-not-allowed"
            }
          `}
        >
          {tr("priorities.continueToF")}
        </button>
      </div>
    </div>
  );
}

function PriorityCard({ icon, label, desc, value, onChange }) {
  const pct = ((value - 1) / 4) * 100;

  return (
    <div className="rounded-xl border-2 border-solid border-sand bg-sand/20 p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl" aria-hidden>{icon}</span>
          <div>
            <div className="font-semibold text-sm text-forest">{label}</div>
            <div className="text-xs text-forest/55">{desc}</div>
          </div>
        </div>
        <span className="text-sm font-bold text-forest font-heading min-w-[2ch] text-end">{value}</span>
      </div>

      {/* Slider */}
      <label className="sr-only">{label}</label>
      <input
        type="range"
        min={1}
        max={5}
        step={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-valuemin={1}
        aria-valuemax={5}
        aria-valuenow={value}
        className="w-full h-2 rounded-full appearance-none cursor-pointer accent-terracotta bg-sand border-0"
        style={{ accentColor: "#C8341F" }}
      />
      <div className="flex justify-between text-xs text-forest/40 mt-1">
        <span>Low</span>
        <span>High</span>
      </div>
    </div>
  );
}
