import React, { useState, useEffect } from "react";
import { useApp } from "../App";
import { getCrops, getRegions, getField } from "../api/client";

const MONTHS_SHORT = ["J","F","M","A","M","J","J","A","S","O","N","D"];

export default function FieldScreen() {
  const { lang, selectedRegion, setSelectedRegion, rotation, setRotation, setScreen, tr, isRTL } = useApp();

  const [regions, setRegions] = useState([]);
  const [crops, setCrops] = useState([]);
  const [fieldInfo, setFieldInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Main crops only for slot selectors
  const mainCrops = crops.filter((c) => c.role === "main");

  useEffect(() => {
    setLoading(true);
    Promise.all([getCrops(), getRegions()])
      .then(([c, r]) => { setCrops(c); setRegions(r); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  useEffect(() => {
    if (selectedRegion) {
      getField(selectedRegion.id).then(setFieldInfo).catch(() => {});
    }
  }, [selectedRegion]);

  const handleRegionSelect = (reg) => {
    setSelectedRegion(reg);
  };

  const handleRotationChange = (slotIdx, cropId) => {
    const next = [...rotation];
    next[slotIdx] = cropId;
    setRotation(next);
  };

  const cropLabel = (cropId) => {
    if (!cropId) return tr("field.noCrop");
    const c = crops.find((x) => x.crop_id === cropId);
    if (!c) return cropId;
    return lang === "fr" ? c.name_fr : lang === "ar" ? c.name_ar : c.name_en;
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-forest/60">
      <span className="animate-pulse text-sm">Loading…</span>
    </div>
  );

  if (error) return (
    <div className="rounded-xl border border-terracotta/40 bg-terracotta/10 p-6 text-terracotta text-sm">
      {error}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="font-heading text-2xl font-bold text-forest">{tr("field.title")}</h2>
      </div>

      {/* ── Region selection ──────────────────────────────────────────────── */}
      <section aria-labelledby="region-heading">
        <h3 id="region-heading" className="text-sm font-semibold text-forest/60 uppercase tracking-wide mb-3">
          {tr("field.chooseRegion")}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {regions.map((reg) => {
            const isSelected = selectedRegion?.id === reg.id;
            return (
              <button
                key={reg.id}
                onClick={() => handleRegionSelect(reg)}
                aria-pressed={isSelected}
                className={`
                  min-h-[72px] rounded-xl border-2 p-4 text-start transition-all
                  focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta
                  ${isSelected
                    ? "border-forest bg-forest text-cream"
                    : "border-dashed border-sand bg-sand/30 text-forest hover:border-forest/40 hover:bg-sand/60"
                  }
                `}
              >
                <div className="font-heading font-bold text-base">{reg.name}</div>
                <div className={`text-xs mt-0.5 ${isSelected ? "text-cream/70" : "text-forest/60"}`}>
                  {reg.climate_type}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* ── Field info & rotation (shown after region is selected) ───────── */}
      {selectedRegion && (
        <>
          {/* Field summary card — dashed border = synthetic data */}
          <section
            aria-labelledby="field-info-heading"
            className="rounded-xl border-2 border-dashed border-ochre/50 bg-sand/30 p-5"
          >
            <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
              <h3 id="field-info-heading" className="font-heading font-bold text-lg text-forest">
                {selectedRegion.name}
              </h3>
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-ochre/15 border border-dashed border-ochre/50 text-ochre text-xs font-semibold">
                <span aria-hidden>⚡</span>
                {tr("field.syntheticBadge")}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <FieldStat label={tr("field.climate")} value={selectedRegion.climate_type} />
              <FieldStat label={tr("field.elevation")} value={`${selectedRegion.elevation_m} m`} />
              <FieldStat label={tr("field.latitude")} value={selectedRegion.lat.toFixed(2) + "°"} />
              <FieldStat label={tr("field.longitude")} value={selectedRegion.lon.toFixed(2) + "°"} />
            </div>
            <p className="mt-3 text-xs text-ochre/80 italic">{tr("field.syntheticNote")}</p>
          </section>

          {/* Current 3-year rotation */}
          <section aria-labelledby="rotation-heading">
            <h3 id="rotation-heading" className="text-sm font-semibold text-forest/60 uppercase tracking-wide mb-3">
              {tr("field.currentRotation")}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {rotation.map((cropId, idx) => (
                <SlotSelector
                  key={idx}
                  slotIndex={idx}
                  value={cropId}
                  crops={mainCrops}
                  lang={lang}
                  tr={tr}
                  onChange={(id) => handleRotationChange(idx, id)}
                />
              ))}
            </div>
          </section>

          {/* Continue CTA */}
          <div className="flex justify-end">
            <button
              onClick={() => setScreen("priorities")}
              className="
                min-h-[48px] px-6 py-3 rounded-xl bg-terracotta text-cream font-semibold text-sm
                hover:bg-terracotta/90 transition-colors
                focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta focus-visible:ring-offset-2
              "
            >
              {tr("field.continueToP")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function FieldStat({ label, value }) {
  return (
    <div className="bg-cream/70 rounded-lg p-3">
      <div className="text-xs text-forest/55 mb-0.5">{label}</div>
      <div className="font-semibold text-forest text-sm">{value}</div>
    </div>
  );
}

function SlotSelector({ slotIndex, value, crops, lang, tr, onChange }) {
  const cropName = (c) =>
    lang === "fr" ? c.name_fr : lang === "ar" ? c.name_ar : c.name_en;

  return (
    <div className="rounded-xl border-2 border-solid border-sand bg-sand/20 p-4">
      <label
        htmlFor={`slot-${slotIndex}`}
        className="block text-xs font-semibold text-forest/55 uppercase tracking-wide mb-2"
      >
        {tr("field.slot")} {slotIndex + 1}
      </label>
      <select
        id={`slot-${slotIndex}`}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="
          w-full min-h-[44px] rounded-lg border border-sand bg-cream px-3 py-2 text-sm text-forest
          focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta
          appearance-none cursor-pointer
        "
      >
        <option value="" disabled>{tr("field.noCrop")}</option>
        {crops.map((c) => (
          <option key={c.crop_id} value={c.crop_id}>
            {cropName(c)}
          </option>
        ))}
      </select>
      {value && (() => {
        const crop = crops.find((c) => c.crop_id === value);
        return crop ? (
          <div className="mt-2 flex gap-2 flex-wrap">
            {crop.n_fixing && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-river/15 text-river border border-river/30">
                N-fixing
              </span>
            )}
            {crop.is_assumption && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-ochre/15 text-ochre border border-dashed border-ochre/40">
                Assumption
              </span>
            )}
          </div>
        ) : null;
      })()}
    </div>
  );
}
