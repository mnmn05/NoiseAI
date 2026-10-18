/**
 * 마이크 신호 → 소음(dB) / 음성대역 비율 계산 (T4)
 * 화면(DOM)과 무관한 순수 함수라서 Node 에서도 테스트할 수 있다.
 *
 *  - noise_db    : 평균 에너지(RMS)를 dBFS 로 바꾼 뒤 보정 오프셋을 더한 값 (0~140 으로 제한)
 *  - voice_ratio : 음성대역(300~3400Hz) 에너지 / 전체(20Hz~) 에너지  (0~1)
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.AudioMetrics = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const VOICE_LO = 300;
  const VOICE_HI = 3400;
  const TOTAL_LO = 20;        // 이 아래(직류·초저음)는 전체 에너지에서 제외
  const SILENCE_DBFS = -80;   // 이보다 작으면 사실상 무음 → 비율 계산 안 함

  const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

  /** 샘플(-1~1)의 평균 제곱(에너지) */
  function meanSquare(samples) {
    if (!samples || samples.length === 0) return 0;
    let s = 0;
    for (let i = 0; i < samples.length; i++) s += samples[i] * samples[i];
    return s / samples.length;
  }

  /** 평균 제곱 → dBFS  (10·log10(ms) = 20·log10(rms)) */
  function msToDbfs(ms) {
    return 10 * Math.log10(Math.max(ms, 1e-12));
  }

  /**
   * AnalyserNode.getFloatFrequencyData() 결과(dB 배열)에서
   * 음성대역 에너지와 전체 에너지를 구한다.
   */
  function bandPowers(freqDb, sampleRate, fftSize) {
    const binHz = sampleRate / fftSize;
    let band = 0, total = 0;
    for (let k = 0; k < freqDb.length; k++) {
      const f = k * binHz;
      if (f < TOTAL_LO) continue;
      const d = freqDb[k];
      if (!isFinite(d)) continue;           // -Infinity (완전한 0) 는 에너지 0
      const p = Math.pow(10, d / 10);
      total += p;
      if (f >= VOICE_LO && f <= VOICE_HI) band += p;
    }
    return { band, total };
  }

  /** 보정 오프셋: 기준 소음계 값(refDb) - 같은 순간의 dBFS */
  function calibrationOffset(refDb, measuredDbfs) {
    return refDb - measuredDbfs;
  }

  /**
   * 일정 시간(예: 3초) 동안 프레임을 모아 평균을 내는 누적기.
   *  add(timeSamples, freqDb, sampleRate, fftSize) 를 프레임마다 호출하고
   *  result(offset) 로 {noise_db, voice_ratio, dbfs, frames} 를 얻는다.
   */
  function createAccumulator() {
    let sumMs = 0, band = 0, total = 0, frames = 0;
    return {
      add(timeSamples, freqDb, sampleRate, fftSize) {
        sumMs += meanSquare(timeSamples);
        const p = bandPowers(freqDb, sampleRate, fftSize);
        band += p.band;
        total += p.total;
        frames += 1;
      },
      result(offset) {
        if (frames === 0) return null;
        const dbfs = msToDbfs(sumMs / frames);
        const silent = dbfs < SILENCE_DBFS || total <= 0;
        return {
          dbfs: Math.round(dbfs * 10) / 10,
          noise_db: Math.round(clamp(dbfs + offset, 0, 140) * 10) / 10,
          voice_ratio: silent ? null : Math.round(clamp(band / total, 0, 1) * 1000) / 1000,
          frames: frames,
        };
      },
      reset() { sumMs = 0; band = 0; total = 0; frames = 0; },
    };
  }

  return {
    VOICE_LO, VOICE_HI, TOTAL_LO, SILENCE_DBFS,
    meanSquare, msToDbfs, bandPowers, calibrationOffset, createAccumulator,
  };
});