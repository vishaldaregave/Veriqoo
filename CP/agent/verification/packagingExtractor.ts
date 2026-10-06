import type {
  PackagingInfo,
  ExtractedFact,
} from "./types.ts";

/**
 * Parses OCR output from packaging/label images into structured product evidence.
 */
export function extractPackagingInfo(ocrText: string, imageSource = "product_image"): PackagingInfo {
  const lines = (ocrText || "")
    .split(/[\r\n]+/)
    .map((l) => l.trim())
    .filter(Boolean);

  const facts: ExtractedFact[] = [];
  const claims: string[] = [];
  const websites: string[] = [];
  const contact_information: string[] = [];

  const product = {
    name: null as string | null,
    brand: null as string | null,
    category: null as string | null,
    price: null as string | null,
    mrp: null as string | null,
  };

  const manufacturer = {
    name: null as string | null,
    address: null as string | null,
    contact: null as string | null,
  };

  const regulatory = {
    license_numbers: [] as string[],
    certifications: [] as string[],
  };

  const dates = {
    manufactured: null as string | null,
    expiry: null as string | null,
    best_before: null as string | null,
  };

  if (!ocrText || ocrText.trim().length === 0) {
    return { product, manufacturer, regulatory, dates, claims, websites, contact_information, facts };
  }

  // 1. MRP & Price extraction
  const mrpRegex = /(?:MRP|M\.R\.P\.?)\s*[:\-]?\s*(?:Rs\.?|₹|\$|USD)?\s*([\d,]+(?:\.\d{1,2})?)/i;
  const mrpMatch = ocrText.match(mrpRegex);
  if (mrpMatch) {
    product.mrp = mrpMatch[0].trim();
    facts.push({
      fact: `Packaging indicates ${product.mrp}`,
      source: imageSource,
      method: "OCR",
    });
  }

  const priceRegex = /(?:[$€£₹]|Rs\.?|USD|INR|EUR)\s*([\d,]+(?:\.\d{1,2})?)/i;
  const priceMatch = ocrText.match(priceRegex);
  if (priceMatch) {
    product.price = priceMatch[0].trim();
    facts.push({
      fact: `Price on packaging detected as ${product.price}`,
      source: imageSource,
      method: "OCR",
    });
  }

  // 2. Regulatory & License Numbers
  const fssaiRegex = /(?:FSSAI|Lic\.?\s*(?:No\.?)?)\s*[:\-]?\s*(\d{10,14})/i;
  const fssaiMatch = ocrText.match(fssaiRegex);
  if (fssaiMatch) {
    const fssaiNum = `FSSAI Lic: ${fssaiMatch[1]}`;
    regulatory.license_numbers.push(fssaiNum);
    facts.push({ fact: fssaiNum, source: imageSource, method: "OCR" });
  }

  const isoRegex = /\bISO\s*\d{4,5}(?::\d{4})?\b/gi;
  let isoMatch;
  while ((isoMatch = isoRegex.exec(ocrText)) !== null) {
    regulatory.certifications.push(isoMatch[0].toUpperCase());
    facts.push({ fact: `Certification: ${isoMatch[0]}`, source: imageSource, method: "OCR" });
  }

  const certKeywords = [
    /\bGMP\s*Certified\b/i,
    /\bFDA\s*(?:Approved|Registered|Compliant)\b/i,
    /\b100%\s*(?:Organic|Natural|Pure)\b/i,
    /\bClinically\s*Tested\b/i,
    /\bDermatologically\s*Tested\b/i,
    /\bCruelty\s*Free\b/i,
    /\bLab\s*Tested\b/i,
    /\bSugar\s*Free\b/i,
  ];

  for (const cert of certKeywords) {
    const match = ocrText.match(cert);
    if (match) {
      claims.push(match[0].trim());
      regulatory.certifications.push(match[0].trim());
      facts.push({ fact: `Packaging claim: ${match[0]}`, source: imageSource, method: "OCR" });
    }
  }

  // 3. Manufacturer Information
  const mfgMatch = ocrText.match(/(?:Mfg\.?\s*by|Mfd\.?\s*by|Manufactured\s*by|Marketed\s*by|Packed\s*by)\s*[:\-]?\s*([A-Za-z0-9\s.,&'-]{3,50})/i);
  if (mfgMatch) {
    manufacturer.name = mfgMatch[1].split(/[\r\n]+/)[0].trim();
    facts.push({ fact: `Manufacturer identified: ${manufacturer.name}`, source: imageSource, method: "OCR" });
  }

  // 4. Dates: MFG, EXP, Best Before
  const mfgDateMatch = ocrText.match(/(?:MFG|Mfg|Date of Mfg|Mfd)\s*[:\-]?\s*([0-9]{1,2}[\/.-][0-9]{2,4}|[A-Za-z]{3,9}\s*[0-9]{2,4})/i);
  if (mfgDateMatch) {
    dates.manufactured = mfgDateMatch[1].trim();
    facts.push({ fact: `MFG Date: ${dates.manufactured}`, source: imageSource, method: "OCR" });
  }

  const expDateMatch = ocrText.match(/(?:EXP|Exp|Expiry Date|Use by)\s*[:\-]?\s*([0-9]{1,2}[\/.-][0-9]{2,4}|[A-Za-z]{3,9}\s*[0-9]{2,4})/i);
  if (expDateMatch) {
    dates.expiry = expDateMatch[1].trim();
    facts.push({ fact: `Expiry Date: ${dates.expiry}`, source: imageSource, method: "OCR" });
  }

  const bestBeforeMatch = ocrText.match(/(?:Best Before|Best by)\s*[:\-]?\s*([0-9]{1,2}\s*(?:Months|Days|Years)|[0-9]{1,2}[\/.-][0-9]{2,4})/i);
  if (bestBeforeMatch) {
    dates.best_before = bestBeforeMatch[1].trim();
  }

  // 5. Websites & Contact Printed on Packaging
  const webRegex = /\b(?:www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|[a-zA-Z0-9.-]+\.(?:com|org|in|net|co|io))\b/gi;
  let webMatch;
  while ((webMatch = webRegex.exec(ocrText)) !== null) {
    if (!websites.includes(webMatch[0].toLowerCase())) {
      websites.push(webMatch[0].toLowerCase());
    }
  }

  const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi;
  let emailMatch;
  while ((emailMatch = emailRegex.exec(ocrText)) !== null) {
    if (!contact_information.includes(emailMatch[0])) {
      contact_information.push(emailMatch[0]);
    }
  }

  const phoneRegex = /(?:call|care|support|tel)?\s*[:\-]?\s*(\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4})\b/gi;
  let phoneMatch;
  while ((phoneMatch = phoneRegex.exec(ocrText)) !== null) {
    if (phoneMatch[1].replace(/\D/g, "").length >= 8 && !contact_information.includes(phoneMatch[1].trim())) {
      contact_information.push(phoneMatch[1].trim());
    }
  }

  // 6. Deduce Brand and Product Name
  if (lines.length > 0) {
    // Usually top lines contain the Brand and Product title
    const topCandidates = lines.slice(0, 3);
    for (const candidate of topCandidates) {
      if (candidate.length >= 3 && candidate.length <= 40 && !candidate.toLowerCase().includes("mfg") && !candidate.toLowerCase().includes("mrp")) {
        if (!product.brand) {
          product.brand = candidate;
          facts.push({ fact: `Brand on packaging: ${product.brand}`, source: imageSource, method: "OCR" });
        } else if (!product.name) {
          product.name = candidate;
          facts.push({ fact: `Product title on packaging: ${product.name}`, source: imageSource, method: "OCR" });
        }
      }
    }
  }

  return {
    product,
    manufacturer,
    regulatory,
    dates,
    claims: Array.from(new Set(claims)),
    websites,
    contact_information,
    facts,
  };
}
