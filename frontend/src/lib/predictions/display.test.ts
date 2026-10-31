import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { displayName } from "./display.ts";

describe("displayName", () => {
  it("capitalises the first letter of each word without adding accents", () => {
    assert.equal(displayName("yeremy pino"), "Yeremy Pino");
    assert.equal(displayName("estevao"), "Estevao");
  });
  it("handles hyphens and apostrophes", () => {
    assert.equal(displayName("jean-clair todibo"), "Jean-Clair Todibo");
    assert.equal(displayName("n'golo kante"), "N'Golo Kante");
  });
  it("leaves already capitalised or accented names as they are", () => {
    assert.equal(displayName("Yéremy Pino"), "Yéremy Pino");
    assert.equal(displayName("álvaro carreras"), "Álvaro Carreras");
  });
});
