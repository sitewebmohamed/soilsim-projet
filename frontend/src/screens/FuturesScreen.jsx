import React, { useState, useEffect } from "react";
import { useApp } from "../App";
import { getPlans, getCrops } from "../api/client";

const LABEL_COLORS = {
  current: { ring: "border-sand", badge: "bg-sand text-forest", header: "bg-sand/40" },
  recommended: { ring: "border-forest", badge: "bg-forest text-cream", header: "bg-forest/10" },
  alternative: { ring: "border-river", badge: "bg-river text-cream", header: "bg-river/10" },
};

const SCORE_COLORS = {
  water: "bg-river",
  soil: "bg-forest",
  resilience: "bg-ochre",
  income: "bg-terracotta",
  animals: "bg-ochre/80",
  pest_break: "bg-forest/60",
};

const RIBBON_COLORS = {
  bare: "bg-sand border-dashed border border-sand/80",
  growing: "bg-forest/70",
  heat: "bg-ochre",
  frost: "bg-river/60",
  water: "bg-terracotta/70",
};

const CONFIDENCE_STYLES = {
  low: "border-dashed border-ochre/50 bg-ochre/10 text-ochre",
  medium: "border-dashed border-river/50 bg-river/10 text-river",
  high: "border border-forest/30 bg-forest/10 text-forest",
};

export default function FuturesScreen() {
  const { lang, selectedRegion, rotation, weights, availableWater, fieldReady, prioritiesReady, setScreen, tr, isRTL } = useApp();

  const [plans, setPlans] = useState([]);
  const [crops, setCrops] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const ready = fieldReady && prioritiesReady;

  useEffect(() => {
    if (!ready) return;
    setLoading(true);
    setError(null);
    Promise.all([
      getPlans(selectedRegion.id, rotation, weights, availableWater),
      getCrops(),
    ])
      .then(([plansData, cropsData]) => {
        setPlans(plansData);
        const dict = {};
        cropsData.forEach((c) => (dict[c.crop_id] = c));
        setCrops(dict);
        setLoading(false);
      })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [selectedRegion, rotation, weights, availableWater, ready]);

  if (!ready) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
        <span className="text-4xl" aria-hidden>🌾</span>
        <p className="text-forest/60 text-sm max-w-xs">{tr("futures.notReady")}</p>
        <button
          onClick={() => setScreen("field")}
          className="min-h-[48px] px-5 py-2 rounded-xl bg-terracotta text-cream text-sm font-semibold hover:bg-terracotta/90 transition-colors"
        >
          {tr("nav.field")}
        </button>
      </div>
    );
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-forest/60">
      <span className="animate-pulse text-sm">Calculating plans…</span>
    </div>
  );

  if (error) return (
    <div className="rounded-xl border border-terracotta/40 bg-terracotta/10 p-6 text-terracotta text-sm">{error}</div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-heading text-2xl font-bold text-forest">{tr("futures.title")}</h2>
        <p className="text-sm text-forest/60 mt-1">{tr("futures.subtitle")}</p>
      </div>

      <div className="space-y-6">
        {plans.map((plan) => (
          <PlanCard key={plan.plan_id} plan={plan} crops={crops} tr={tr} lang={lang} />
        ))}
      </div>

      <div className="pt-2">
        <button
          onClick={() => setScreen("priorities")}
          className="
            min-h-[48px] px-5 py-2.5 rounded-xl border-2 border-sand text-forest text-sm font-medium
            hover:bg-sand/50 transition-colors
            focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta
          "
        >
          {tr("futures.back")}
        </button>
      </div>
    </div>
  );
}

function PlanCard({ plan, crops, tr, lang }) {
  const { plan_id, label, feasible, slots, scores, ribbons, underground, confidence } = plan;
  const style = LABEL_COLORS[label] || LABEL_COLORS.alternative;

  const labelKey = `futures.${label}`;
  const monthsArr = tr("months");

  const cropName = (id) => {
    if (!id || !crops[id]) return id;
    return lang === "fr" ? crops[id].name_fr : lang === "ar" ? crops[id].name_ar : crops[id].name_en;
  };

  return (
    <article
      aria-label={`${tr(labelKey)} plan`}
      className={`rounded-2xl border-2 ${style.ring} overflow-hidden`}
    >
      {/* Plan header */}
      <div className={`${style.header} px-5 py-4 flex flex-wrap items-center justify-between gap-3`}>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-bold px-3 py-1 rounded-full ${style.badge}`}>
            {tr(labelKey)}
          </span>
          {!feasible && (
            <span className="text-xs px-2 py-0.5 rounded-full border border-dashed border-ochre/60 bg-ochre/15 text-ochre">
              ⚠ {tr("futures.feasibleNo")}
            </span>
          )}
        </div>
        <TotalScoreBadge total={scores.total} />
      </div>

      <div className="p-5 space-y-5">
        {/* Slots (Year 1/2/3) */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {slots.map((slot, i) => (
            <SlotTag key={i} index={i} slot={slot} cropName={cropName} tr={tr} />
          ))}
        </div>

        {/* Score breakdown */}
        <ScoreBreakdown parts={scores.parts} tr={tr} />

        {/* Ribbon - Year 1 */}
        <div>
          <h4 className="text-xs font-semibold text-forest/55 uppercase tracking-wide mb-2">
            {tr("futures.yearRibbon")}
          </h4>
          <RibbonRow ribbon={ribbons[0]} months={monthsArr} tr={tr} />
        </div>

        {/* Underground / soil profile */}
        <UndergroundPanel ug={underground} tr={tr} />

        {/* Confidence badge */}
        <ConfidenceBadge confidence={confidence} tr={tr} />
      </div>
    </article>
  );
}

function TotalScoreBadge({ total }) {
  const color = total >= 75 ? "text-forest" : total >= 50 ? "text-ochre" : "text-terracotta";
  return (
    <div className="flex items-baseline gap-1">
      <span className={`font-heading text-3xl font-bold ${color}`}>{total}</span>
      <span className="text-xs text-forest/40">/ 100</span>
    </div>
  );
}

function SlotTag({ index, slot, cropName, tr }) {
  return (
    <div className="rounded-lg border-2 border-solid border-sand bg-sand/20 p-3">
      <div className="text-xs font-semibold text-forest/50 uppercase tracking-wide mb-1">
        {tr("futures.slot")} {index + 1}
      </div>
      <div className="text-sm font-semibold text-forest">{cropName(slot.main_id)}</div>
      {slot.cover_id && (
        <div className="text-xs text-river mt-0.5">+ {cropName(slot.cover_id)}</div>
      )}
    </div>
  );
}

function ScoreBreakdown({ parts, tr }) {
  const scoreKeys = ["water", "soil", "income", "animals", "resilience", "pest_break"];
  return (
    <div>
      <h4 className="text-xs font-semibold text-forest/55 uppercase tracking-wide mb-2 sr-only">Scores</h4>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {scoreKeys.map((key) => {
          const val = parts[key];
          const labelKey = key === "pest_break" ? "futures.pestBreak" : `futures.${key}`;
          const barColor = SCORE_COLORS[key] || "bg-forest";
          return (
            <div key={key} className="rounded-lg bg-cream/60 p-2.5">
              <div className="flex justify-between items-baseline mb-1">
                <span className="text-xs text-forest/55">{tr(labelKey)}</span>
                <span className="text-xs font-bold text-forest">{val}</span>
              </div>
              <div className="h-1.5 rounded-full bg-sand overflow-hidden">
                <div
                  className={`h-full rounded-full ${barColor} transition-all`}
                  style={{ width: `${val}%` }}
                  role="meter"
                  aria-label={`${tr(labelKey)}: ${val} out of 100`}
                  aria-valuenow={val}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RibbonRow({ ribbon, months, tr }) {
  if (!ribbon || !Array.isArray(ribbon)) return null;
  const ribbonTr = tr("ribbon");
  const monthsArr = Array.isArray(months) ? months : Object.values(months);

  return (
    <div className="flex gap-0.5" role="list" aria-label={tr("futures.yearRibbon")}>
      {ribbon.map((entry, i) => {
        const flags = entry.flags || [];
        let color = entry.state === "bare" ? RIBBON_COLORS.bare : RIBBON_COLORS.growing;
        let title = entry.state === "bare" ? ribbonTr?.bare || "Bare" : ribbonTr?.growing || "Growing";

        if (entry.state === "growing") {
          if (flags.includes("heat")) { color = RIBBON_COLORS.heat; title = ribbonTr?.heat || "Heat"; }
          else if (flags.includes("frost")) { color = RIBBON_COLORS.frost; title = ribbonTr?.frost || "Frost"; }
          else if (flags.includes("water")) { color = RIBBON_COLORS.water; title = ribbonTr?.water || "Water"; }
        }

        return (
          <div
            key={i}
            role="listitem"
            title={`${monthsArr[i] || i + 1}: ${title}`}
            aria-label={`${monthsArr[i] || i + 1}: ${title}`}
            className={`flex-1 h-8 rounded-sm ${color} flex items-end justify-center pb-0.5`}
          >
            <span className="text-[9px] text-cream/80 font-mono leading-none">{(monthsArr[i] || "").slice(0, 1)}</span>
          </div>
        );
      })}
    </div>
  );
}

function UndergroundPanel({ ug, tr }) {
  if (!ug) return null;
  return (
    <div className="rounded-xl border-2 border-dashed border-sand bg-sand/20 p-4">
      <h4 className="text-xs font-semibold text-forest/55 uppercase tracking-wide mb-3">
        {tr("futures.underground")}
      </h4>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <UGStat label={tr("futures.rootDepth")} value={`${ug.root_depth_cm} cm`} />
        <UGStat label={tr("futures.organicMatter")} value={`${(ug.organic_matter * 100).toFixed(0)}%`} note="illustrative" />
        <UGStat label={tr("futures.moisture")} value={`${(ug.moisture * 100).toFixed(0)}%`} />
        <UGStat label={tr("futures.coverFraction")} value={`${(ug.cover * 100).toFixed(0)}%`} />
        <UGStat
          label={tr("futures.nFix")}
          value={ug.n_fixing ? tr("futures.yes") : tr("futures.no")}
          accent={ug.n_fixing ? "text-river" : "text-forest"}
        />
      </div>
    </div>
  );
}

function UGStat({ label, value, note, accent = "text-forest" }) {
  return (
    <div className="bg-cream/70 rounded-lg p-2.5">
      <div className="text-xs text-forest/50 mb-0.5">{label}</div>
      <div className={`text-sm font-semibold ${accent}`}>{value}</div>
      {note && <div className="text-[10px] italic text-forest/40">{note}</div>}
    </div>
  );
}

function ConfidenceBadge({ confidence, tr }) {
  if (!confidence) return null;
  const { level, reasons } = confidence;
  const style = CONFIDENCE_STYLES[level] || CONFIDENCE_STYLES.low;
  const levelKey = `confidence.${level}`;

  return (
    <div className={`rounded-lg border-2 p-3 ${style}`}>
      <div className="text-xs font-bold uppercase tracking-wide mb-1">{tr("futures.confidence")}: {tr(levelKey)}</div>
      {reasons && reasons.length > 0 && (
        <ul className="text-xs space-y-0.5 mt-1">
          {reasons.map((r, i) => (
            <li key={i} className="opacity-80">· {r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
