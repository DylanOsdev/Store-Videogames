import { describe, expect, it } from "vitest";

import { formatCOP } from "./format";

describe("formatCOP", () => {
  it("formatea un string decimal como pesos colombianos sin decimales", () => {
    // \u00a0 es el espacio no separable que usa Intl en es-CO.
    const out = formatCOP("49900.00");
    expect(out).toContain("49.900");
    expect(out).toContain("$");
  });

  it("formatea un number", () => {
    const out = formatCOP(1500);
    expect(out).toContain("1.500");
  });

  it("redondea sin decimales", () => {
    const out = formatCOP("99999.99");
    // maximumFractionDigits: 0 => redondea a 100.000
    expect(out).toContain("100.000");
  });

  it("devuelve $0 ante un valor no numérico", () => {
    expect(formatCOP("no-es-numero")).toBe("$0");
  });

  it("trata el cero correctamente", () => {
    expect(formatCOP(0)).toContain("0");
  });
});
