import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  describeGap, describeGapShort, describeMarketDifference, describeOverlap, describePosition, describePositionShort, describePriceDifference,
  formatDifference, formatEur, grossMargin, niceCeil, parseMillions, positionInRange, rangeOverlap,
} from "./scenarios.ts";

const M = 1_000_000;

describe("formatEur", () => {
  it("uses millions with one decimal from 1 M€", () => {
    assert.equal(formatEur(14_581_331), "14,6 M€");
    assert.equal(formatEur(1_000_000), "1,0 M€");
    assert.equal(formatEur(-2 * M), "−2,0 M€");
  });
  it("rounds smaller amounts to thousands with Spanish grouping", () => {
    assert.equal(formatEur(480_250), "480.000 €");
    assert.equal(formatEur(71_360.46), "71.000 €");
    assert.equal(formatEur(5_000), "5.000 €");
  });
});

describe("formatDifference", () => {
  it("never shows a non-zero difference as zero", () => {
    assert.equal(formatDifference(300), "menos de 1.000 €");
    assert.equal(formatDifference(-300), "−menos de 1.000 €");
    assert.equal(formatDifference(0), "0 €");
    assert.equal(formatDifference(633_514.125), "634.000 €");
  });
});

describe("parseMillions", () => {
  it("reads millions with comma or dot", () => {
    assert.deepEqual(parseMillions("0,3"), { status: "ok", value: 300_000 });
    assert.deepEqual(parseMillions(" 12.5 "), { status: "ok", value: 12_500_000 });
  });
  it("separates empty from invalid", () => {
    assert.deepEqual(parseMillions(""), { status: "empty" });
    assert.equal(parseMillions("abc").status, "invalid");
    assert.equal(parseMillions("-1").status, "invalid");
  });
  it("accepts zero only when allowed", () => {
    assert.equal(parseMillions("0").status, "invalid");
    assert.deepEqual(parseMillions("0", { allowZero: true }), { status: "ok", value: 0 });
  });
  it("rounds to whole euros, so a typed limit equals the limit", () => {
    assert.deepEqual(parseMillions("16,173467"), { status: "ok", value: 16_173_467 });
    assert.equal(positionInRange((parseMillions("16,173467") as { value: number }).value, 16_173_467, 164_512_176), "inside");
  });
  it("rejects absurd amounts instead of overflowing", () => {
    assert.equal(parseMillions("1e308").status, "invalid");
    assert.equal(parseMillions("1001").status, "invalid");
    assert.equal(parseMillions("1000").status, "ok");
  });
});

describe("positionInRange and describePosition", () => {
  const low = 10 * M, high = 15 * M;
  it("treats a limit as inside", () => {
    assert.equal(positionInRange(low, low, high), "inside");
    assert.equal(positionInRange(high, low, high), "inside");
    assert.match(describePosition(low, low, high, "El precio").detail, /^Coincide con el límite inferior/);
    assert.match(describePosition(high, low, high, "El precio").detail, /^Coincide con el límite superior/);
  });
  it("describes an amount below the range", () => {
    const text = describePosition(8 * M, low, high, "El precio");
    assert.equal(text.title, "Por debajo del rango");
    assert.equal(text.main, "El precio está 2,0 M€ por debajo del límite inferior.");
    assert.equal(text.detail, "Distancia al límite superior: 7,0 M€.");
  });
  it("describes an amount above the range", () => {
    const text = describePosition(18 * M, low, high, "La oferta");
    assert.equal(text.main, "La oferta está 3,0 M€ por encima del límite superior.");
    assert.equal(text.detail, "Distancia al límite inferior: 8,0 M€.");
  });
  it("adds the inside note only inside", () => {
    const note = "Estar dentro no basta para concluir que sea conveniente.";
    assert.equal(describePosition(12 * M, low, high, "El precio", note).main, `El precio está entre los límites estimados. ${note}`);
    assert.ok(!describePosition(8 * M, low, high, "El precio", note).main.includes(note));
  });
  it("has a short form for Comparar", () => {
    assert.equal(describePositionShort(8 * M, low, high), "el precio está 2,0 M€ por debajo del límite inferior de su rango.");
    assert.equal(describePositionShort(12 * M, low, high), "el precio está entre los límites de su rango.");
  });
});

describe("describeMarketDifference", () => {
  it("compares in words, without sign", () => {
    assert.equal(describeMarketDifference(5 * M, 800_000, "El precio"), "El precio es 4,2 M€ superior al valor de mercado.");
    assert.equal(describeMarketDifference(500_000, 800_000, "La oferta"), "La oferta es 300.000 € inferior al valor de mercado.");
    assert.equal(describeMarketDifference(800_000, 800_000, "El precio"), "El precio coincide con el valor de mercado.");
  });
});

describe("describeGap", () => {
  it("states that the Gap uses the central estimate (market value below the range)", () => {
    const text = describeGap(4_598_700, 633_514.125, 13_781_331);
    assert.equal(text.main, "La estimación central de xValue está 4,6 M€ por encima del valor de mercado.");
    assert.equal(text.limits, "Con los límites del rango, la diferencia va de 634.000 € a 13,8 M€ por encima del valor de mercado.");
  });
  it("handles a market value above the range", () => {
    const text = describeGap(-20 * M, -25 * M, -5 * M);
    assert.equal(text.main, "La estimación central de xValue está 20,0 M€ por debajo del valor de mercado.");
    assert.equal(text.limits, "Con los límites del rango, la diferencia va de 5,0 M€ a 25,0 M€ por debajo del valor de mercado.");
  });
  it("does not give one direction to the whole range when the market value is inside", () => {
    assert.equal(describeGap(2 * M, -3 * M, 6 * M).limits, "El valor de mercado queda dentro del rango: está 3,0 M€ sobre el límite inferior y 6,0 M€ bajo el superior.");
  });
  it("omits the limits when the source lacks them", () => {
    assert.equal(describeGap(1 * M, null, null).limits, null);
  });
  it("has a short form for compact panels", () => {
    assert.equal(describeGapShort(16_278_080), "16,3 M€ por encima del valor de mercado");
    assert.equal(describeGapShort(-14_889_124), "14,9 M€ por debajo del valor de mercado");
    assert.equal(describeGapShort(0), "Igual al valor de mercado");
  });
});

describe("grossMargin", () => {
  it("keeps the sign of a negative margin", () => {
    const margin = grossMargin(4 * M, 6 * M);
    assert.equal(margin.formatted, "−2,0 M€");
    assert.equal(margin.note, "La oferta es inferior al importe pagado.");
  });
  it("accepts zero paid", () => {
    assert.equal(grossMargin(12 * M, 0).note, "Sin importe de traspaso pagado, el margen bruto coincide con la oferta.");
    assert.equal(grossMargin(12 * M, 0).formatted, "12,0 M€");
  });
});

describe("rangeOverlap and describeOverlap", () => {
  it("never concludes equivalence from shared amounts", () => {
    const overlap = rangeOverlap(10 * M, 15 * M, 7 * M, 11 * M);
    assert.deepEqual(overlap, { kind: "shared", low: 10 * M, high: 11 * M });
    assert.match(describeOverlap(overlap, "A", "B"), /no implica que los jugadores tengan el mismo valor/);
  });
  it("distinguishes ranges that only touch", () => {
    const overlap = rangeOverlap(10 * M, 15 * M, 15 * M, 20 * M);
    assert.deepEqual(overlap, { kind: "touch", at: 15 * M });
    assert.equal(describeOverlap(overlap, "A", "B"), "Los rangos coinciden únicamente en 15,0 M€.");
  });
  it("names the higher range when they do not overlap", () => {
    assert.equal(describeOverlap(rangeOverlap(20 * M, 30 * M, 1 * M, 5 * M), "A", "B"), "El rango de A queda completamente por encima del de B.");
    assert.equal(describeOverlap(rangeOverlap(1 * M, 5 * M, 20 * M, 30 * M), "A", "B"), "El rango de B queda completamente por encima del de A.");
  });
});

describe("describePriceDifference", () => {
  it("depends only on the entered prices", () => {
    assert.equal(describePriceDifference("A", 8 * M, "B", 6 * M), "Con los precios introducidos, fichar a B supondría 2,0 M€ menos en importe de traspaso que fichar a A.");
    assert.equal(describePriceDifference("A", 6 * M, "B", 8 * M), "Con los precios introducidos, fichar a A supondría 2,0 M€ menos en importe de traspaso que fichar a B.");
    assert.equal(describePriceDifference("A", 6 * M, "B", 6 * M), "Ambos precios de traspaso coinciden.");
  });
});

describe("niceCeil", () => {
  it("rounds axis ends up to readable steps", () => {
    assert.equal(niceCeil(14.6 * M), 15 * M);
    assert.equal(niceCeil(33.3 * M), 40 * M);
    assert.equal(niceCeil(0), 1);
  });
});
