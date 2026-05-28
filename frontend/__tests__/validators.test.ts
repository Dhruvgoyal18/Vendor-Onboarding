import {
  validateCIN,
  validatePAN,
  validateGSTIN,
  validateIFSC,
  CIN_REGEX,
  PAN_REGEX,
  GSTIN_REGEX,
  IFSC_REGEX,
} from "../lib/validators";

// ─── Regex smoke tests ────────────────────────────────────────────────────────

describe("CIN_REGEX", () => {
  test("accepts valid CIN", () => {
    expect(CIN_REGEX.test("L85110KA1981PLC013115")).toBe(true);
    expect(CIN_REGEX.test("U72200MH2010PTC204100")).toBe(true);
  });
  test("rejects wrong-length strings", () => {
    expect(CIN_REGEX.test("L85110KA1981PLC01")).toBe(false);
    expect(CIN_REGEX.test("L85110KA1981PLC0131150000")).toBe(false);
  });
});

describe("PAN_REGEX", () => {
  test("accepts valid PAN formats", () => {
    expect(PAN_REGEX.test("AAACI1681G")).toBe(true);
    expect(PAN_REGEX.test("AABCP1234D")).toBe(true);
  });
  test("rejects lowercase", () => {
    expect(PAN_REGEX.test("aaaci1681g")).toBe(false);
  });
  test("rejects short strings", () => {
    expect(PAN_REGEX.test("AAACI168")).toBe(false);
  });
});

describe("GSTIN_REGEX", () => {
  test("accepts valid GSTIN", () => {
    expect(GSTIN_REGEX.test("27AAACI1681G1ZK")).toBe(true);
    expect(GSTIN_REGEX.test("29AABCP1234D1Z5")).toBe(true);
  });
  test("rejects GSTIN with wrong Z at position 13", () => {
    expect(GSTIN_REGEX.test("27AAACI1681G1AK")).toBe(false); // 'A' instead of 'Z'
  });
});

describe("IFSC_REGEX", () => {
  test("accepts valid IFSC codes", () => {
    expect(IFSC_REGEX.test("HDFC0000007")).toBe(true);
    expect(IFSC_REGEX.test("SBIN0001234")).toBe(true);
  });
  test("rejects IFSC without 0 in position 5", () => {
    expect(IFSC_REGEX.test("HDFC1000007")).toBe(false);
  });
});

// ─── validateCIN ──────────────────────────────────────────────────────────────

describe("validateCIN", () => {
  test("returns null for empty string", () => {
    expect(validateCIN("")).toBeNull();
  });

  test("passes valid CIN", () => {
    const result = validateCIN("L85110KA1981PLC013115");
    expect(result?.status).toBe("pass");
  });

  test("detects company name in CIN field", () => {
    const result = validateCIN("Acme Technologies Ltd");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/company name/i);
  });

  test("detects GSTIN in CIN field", () => {
    const result = validateCIN("27AAACI1681G1ZK");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/GSTIN/);
  });

  test("hints on short CIN", () => {
    const result = validateCIN("L8511");
    expect(result?.status).toBe("hint");
    expect(result?.msg).toMatch(/21 characters/);
  });

  test("fails on invalid format", () => {
    const result = validateCIN("X12345AB1234XYZ123456");
    expect(result?.status).toBe("fail");
  });
});

// ─── validatePAN ──────────────────────────────────────────────────────────────

describe("validatePAN", () => {
  test("returns null for empty string", () => {
    expect(validatePAN("")).toBeNull();
  });

  test("passes valid company PAN (C entity)", () => {
    const result = validatePAN("AAACI1681G");
    expect(result?.status).toBe("pass");
    expect(result?.msg).toMatch(/Company/);
  });

  test("passes valid firm PAN (F entity)", () => {
    const result = validatePAN("AABFP2345D");
    // F entity type
    expect(result?.status).toBe("pass");
  });

  test("rejects individual PAN (P entity)", () => {
    const result = validatePAN("ABCPP1234D");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/Individual/);
  });

  test("detects GSTIN in PAN field", () => {
    const result = validatePAN("27AAACI1681G1ZK");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/GSTIN/);
  });

  test("detects IFSC in PAN field", () => {
    const result = validatePAN("HDFC0000007");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/IFSC/);
  });

  test("detects company name in PAN field (spaces)", () => {
    const result = validatePAN("Tata Consultancy Services Ltd");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/company name/i);
  });

  test("hints on short PAN", () => {
    const result = validatePAN("AAAC");
    expect(result?.status).toBe("hint");
    expect(result?.msg).toMatch(/10 characters/);
  });
});

// ─── validateGSTIN ────────────────────────────────────────────────────────────

describe("validateGSTIN", () => {
  test("returns null for empty string", () => {
    expect(validateGSTIN("", "")).toBeNull();
  });

  test("passes valid GSTIN with matching PAN", () => {
    const result = validateGSTIN("27AAACI1681G1ZK", "AAACI1681G");
    expect(result?.status).toBe("pass");
    expect(result?.msg).toMatch(/embedded PAN matches/);
  });

  test("fails when embedded PAN does not match PAN field", () => {
    const result = validateGSTIN("27AAACI1681G1ZK", "AABCP1234D");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/embedded PAN/);
  });

  test("detects PAN entered in GSTIN field", () => {
    const result = validateGSTIN("AAACI1681G", "");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/PAN number/);
  });

  test("detects IFSC in GSTIN field", () => {
    const result = validateGSTIN("HDFC0000007", "");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/IFSC/);
  });

  test("detects company name in GSTIN field", () => {
    const result = validateGSTIN("Infosys Limited", "");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/company name/i);
  });

  test("hints on short GSTIN", () => {
    const result = validateGSTIN("27AAAC", "");
    expect(result?.status).toBe("hint");
    expect(result?.msg).toMatch(/15 characters/);
  });

  test("fails on invalid GSTIN format (wrong Z position)", () => {
    const result = validateGSTIN("27AAACI1681G1AK", ""); // 'A' not 'Z'
    expect(result?.status).toBe("fail");
  });
});

// ─── validateIFSC ────────────────────────────────────────────────────────────

describe("validateIFSC", () => {
  test("returns null for empty string", () => {
    expect(validateIFSC("", "")).toBeNull();
  });

  test("passes valid IFSC with matching bank name", () => {
    const result = validateIFSC("HDFC0000007", "HDFC Bank");
    expect(result?.status).toBe("pass");
    expect(result?.msg).toMatch(/HDFC Bank/);
  });

  test("passes valid IFSC with unknown bank prefix", () => {
    const result = validateIFSC("ABCD0001234", "Some Bank");
    expect(result?.status).toBe("pass");
  });

  test("fails when IFSC prefix contradicts bank name", () => {
    const result = validateIFSC("HDFC0000007", "ICICI Bank");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/HDFC Bank/);
  });

  test("detects bank name in IFSC field", () => {
    const result = validateIFSC("HDFC Bank", "HDFC Bank");
    expect(result?.status).toBe("fail");
    expect(result?.msg).toMatch(/bank name/i);
  });

  test("hints on short IFSC", () => {
    const result = validateIFSC("HDFC", "");
    expect(result?.status).toBe("hint");
    expect(result?.msg).toMatch(/11 characters/);
  });

  test("fails on invalid IFSC (no zero in 5th position)", () => {
    const result = validateIFSC("HDFC1000007", "");
    expect(result?.status).toBe("fail");
  });
});
