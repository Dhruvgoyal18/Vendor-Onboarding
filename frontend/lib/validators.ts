import { IFSC_BANK_CODES } from "./types";

export const CIN_REGEX = /^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$/;
export const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
export const GSTIN_REGEX =
  /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
export const IFSC_REGEX = /^[A-Z]{4}0[A-Z0-9]{6}$/;
export const COMPANY_SUFFIX_RE =
  /\b(LTD|LIMITED|PVT|PRIVATE|CORP|INC|LLP|TECH|TECHNOLOGIES|SOLUTIONS|SERVICES|INDUSTRIES|ENTERPRISES|COMPANY|CO)\b/i;

export type ValidationResult = {
  status: "pass" | "fail" | "hint";
  msg: string;
} | null;

export function validateCIN(cin: string): ValidationResult {
  if (!cin) return null;
  const raw = cin.trim();
  const v = raw.toUpperCase().replace(/\s+/g, "");

  if (raw.includes(" ")) {
    if (COMPANY_SUFFIX_RE.test(raw))
      return {
        status: "fail",
        msg: "❌ This looks like a company name. CIN is your 21-character Corporate Identification Number from MCA (e.g. L85110KA1981PLC013115).",
      };
    return {
      status: "fail",
      msg: "❌ CIN has no spaces — it's 21 characters with no gaps (e.g. L85110KA1981PLC013115).",
    };
  }
  if (
    /^[A-Z]+$/i.test(raw) &&
    raw.length > 5 &&
    !raw.startsWith("L") &&
    !raw.startsWith("U")
  ) {
    return {
      status: "fail",
      msg: "❌ This looks like text. CIN starts with L or U followed by 5 digits, then state code, year, etc. Example: L85110KA1981PLC013115",
    };
  }
  if (GSTIN_REGEX.test(v))
    return {
      status: "fail",
      msg: "❌ This looks like a GSTIN number. CIN is 21 characters starting with L or U — check your MCA COI document.",
    };

  if (v.length < 21)
    return { status: "hint", msg: `CIN is 21 characters — you've entered ${v.length}` };
  return CIN_REGEX.test(v)
    ? { status: "pass", msg: "✓ Valid CIN format" }
    : {
        status: "fail",
        msg: "❌ Invalid CIN — expected: L85110KA1981PLC013115 (L/U + 5 digits + 2-letter state + 4-digit year + 3 letters + 6 digits)",
      };
}

export function validatePAN(pan: string): ValidationResult {
  if (!pan) return null;
  const raw = pan.trim();
  const v = raw.toUpperCase().replace(/\s+/g, "");

  if (raw.includes(" ")) {
    if (COMPANY_SUFFIX_RE.test(raw))
      return {
        status: "fail",
        msg: "❌ This looks like a company name. PAN is your 10-character Permanent Account Number (e.g. AAACI1681G).",
      };
    return {
      status: "fail",
      msg: "❌ PAN has no spaces — it's exactly 10 characters: 5 letters + 4 digits + 1 letter (e.g. AAACI1681G).",
    };
  }
  if (v.length === 15 && GSTIN_REGEX.test(v))
    return {
      status: "fail",
      msg: "❌ This looks like a GSTIN number. Your PAN is the 10 characters in positions 3–12 of the GSTIN.",
    };
  if (/^[A-Z]{4}0[A-Z0-9]{6}$/i.test(v))
    return {
      status: "fail",
      msg: "❌ This looks like an IFSC code. PAN is 10 characters: 5 letters + 4 digits + 1 letter (e.g. AAACI1681G).",
    };
  if (/^[A-Z\s]+$/i.test(raw) && raw.length > 5)
    return {
      status: "fail",
      msg: "❌ PAN must contain digits. It's 10 chars: [5 letters][4 digits][1 letter] — e.g. AAACI1681G.",
    };

  if (v.length < 10)
    return { status: "hint", msg: `PAN is 10 characters — you've entered ${v.length}` };
  if (!PAN_REGEX.test(v))
    return {
      status: "fail",
      msg: "❌ Invalid PAN format — expected: AAACI1681G (5 letters, 4 digits, 1 letter)",
    };
  const fourth = v[3];
  const entityMap: Record<string, string> = {
    P: "Individual",
    C: "Company",
    F: "Firm/LLP",
    H: "HUF",
  };
  const entityName = entityMap[fourth] || `Type '${fourth}'`;
  if (fourth === "P")
    return {
      status: "fail",
      msg: `❌ Individual PAN (4th char='P') — company vendors must submit a Company (C) or Firm (F) PAN, not a personal one.`,
    };
  if (["C", "F", "H"].includes(fourth))
    return { status: "pass", msg: `✓ Valid PAN — Entity type: ${entityName}` };
  return {
    status: "hint",
    msg: `PAN entity type: ${entityName} — verify this is correct for your organisation`,
  };
}

export function validateGSTIN(gstin: string, pan: string): ValidationResult {
  if (!gstin) return null;
  const raw = gstin.trim();
  const v = raw.toUpperCase().replace(/\s+/g, "");

  if (raw.includes(" ")) {
    if (COMPANY_SUFFIX_RE.test(raw))
      return {
        status: "fail",
        msg: "❌ This looks like a company name. GSTIN is your 15-character GST registration number from the GSTN portal (e.g. 27AAACI1681G1ZK).",
      };
    return {
      status: "fail",
      msg: "❌ GSTIN has no spaces — it's 15 characters with no gaps. Example: 27AAACI1681G1ZK",
    };
  }
  if (/^[A-Za-z\s]+$/.test(raw) && raw.length > 4)
    return {
      status: "fail",
      msg: "❌ This looks like text. GSTIN starts with a 2-digit state code, then your PAN, then 3 more characters. Example: 27AAACI1681G1ZK",
    };
  if (v.length === 10 && PAN_REGEX.test(v))
    return {
      status: "fail",
      msg: "❌ This looks like a PAN number. GSTIN is 15 characters = [2-digit state code] + [PAN] + [3 chars]. E.g. 27AAACI1681G1ZK",
    };
  if (/^[A-Z]{4}0[A-Z0-9]{6}$/i.test(v))
    return {
      status: "fail",
      msg: "❌ This looks like an IFSC code. The GSTIN field needs your 15-character GST registration number.",
    };

  if (v.length < 15)
    return { status: "hint", msg: `GSTIN is 15 characters — you've entered ${v.length}` };
  if (!GSTIN_REGEX.test(v))
    return {
      status: "fail",
      msg: "❌ Invalid GSTIN format — expected: 29AAACI1681G1ZK (2-digit state + PAN + entity + Z + checksum)",
    };

  if (pan) {
    const panNorm = pan.toUpperCase().replace(/\s/g, "");
    const embeddedPAN = v.substring(2, 12);
    if (panNorm.length === 10 && embeddedPAN !== panNorm)
      return {
        status: "fail",
        msg: `❌ GSTIN embedded PAN '${embeddedPAN}' ≠ your PAN '${panNorm}' — these must match`,
      };
    if (panNorm.length === 10)
      return { status: "pass", msg: `✓ Valid GSTIN — embedded PAN matches your PAN` };
  }
  return { status: "pass", msg: "✓ Valid GSTIN format" };
}

export function validateIFSC(ifsc: string, bankName: string): ValidationResult {
  if (!ifsc) return null;
  const raw = ifsc.trim();
  const v = raw.toUpperCase().replace(/\s+/g, "");

  if (raw.includes(" ")) {
    if (/\bbank\b/i.test(raw))
      return {
        status: "fail",
        msg: "❌ This looks like a bank name. IFSC is the 11-character branch code from your cheque book (e.g. HDFC0000007).",
      };
    return {
      status: "fail",
      msg: "❌ IFSC has no spaces — it's 11 characters: 4-letter bank code + 0 + 6-char branch (e.g. HDFC0000007).",
    };
  }
  if (/^[A-Za-z\s]+$/.test(raw) && raw.length > 4)
    return {
      status: "fail",
      msg: "❌ This looks like text. IFSC is 11 characters: [4-letter bank code][0][6-digit branch]. Example: HDFC0000007",
    };

  if (v.length < 11)
    return { status: "hint", msg: `IFSC is 11 characters — you've entered ${v.length}` };
  if (!IFSC_REGEX.test(v))
    return {
      status: "fail",
      msg: "❌ Invalid IFSC — format: [4-letter bank][0][6 chars]. Example: HDFC0000007",
    };

  const prefix = v.substring(0, 4);
  const knownBank = IFSC_BANK_CODES[prefix];
  if (knownBank) {
    const bankNorm = bankName.toLowerCase();
    const knownNorm = knownBank.toLowerCase();
    if (
      bankNorm &&
      !bankNorm.includes(knownNorm.split(" ")[0].toLowerCase())
    )
      return {
        status: "fail",
        msg: `❌ IFSC prefix '${prefix}' belongs to ${knownBank}, but you stated '${bankName}' — these must match`,
      };
    return { status: "pass", msg: `✓ IFSC valid — Bank confirmed: ${knownBank}` };
  }
  return { status: "pass", msg: `✓ Valid IFSC format` };
}
