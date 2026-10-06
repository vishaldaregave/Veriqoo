# Instagram Ad & Product Verification Agent

An automated due-diligence and consumer protection tool that verifies Instagram ads, reels, posts, and e-commerce stores to detect clickbait, scam tactics, and deceptive claims.

---

## 🚀 Fast Terminal CLI (No WhatsApp Needed)

You can verify any Instagram ad or reel directly from your terminal:

```powershell
# Interactive Continuous Console (keeps running, prompts for links until you stop):
npm run verify

# Or directly:
node verify-cli.mjs

# Optional: automatically open the generated HTML dossier in your default browser:
npm run verify -- --open
```

You can also pass a link directly as a one-shot argument:
```powershell
npm run verify -- "<INSTAGRAM_URL>" "[OPTIONAL_CAPTION_OR_STORE_URL]"
```

### Examples

**1. Verify a simple Instagram link:**
```powershell
npm run verify -- "https://www.instagram.com/reel/C8XYZ123/"
```

**2. Verify with caption copy & store link:**
```powershell
npm run verify -- "https://www.instagram.com/reel/C8XYZ123/" "Crazy 85% off flash sale on Smartwatch! Ending tonight at https://dailydeals.shop"
```

**3. With full debug & timing logs:**
```powershell
npm run verify -- --verbose "https://www.instagram.com/p/ABC999/"
```

The terminal will print:
* 🛡️ **Safety Score (0–100%)**
* 🎣 **Clickbait Risk Index (LOW / MODERATE / HIGH / AGGRESSIVE)**
* 🔎 **Multi-Source Evidence Check**
* 📢 **Flagged Clickbait & Urgency Triggers**
* 💡 **Clear Consumer Buying Recommendation**
* 📄 **File Path to the generated interactive HTML Dossier Report**

---

## 📱 WhatsApp Bot Mode

To run as an interactive WhatsApp assistant:

1. Copy `.env.example` to `.env` and configure your phone number:
   ```env
   ALLOWED_WHATSAPP_NUMBER=919876543210
   PORT=2000
   ```
2. Start the dev server:
   ```powershell
   npm run dev
   ```
3. Scan the terminal QR code via **WhatsApp → Linked Devices**.
4. Send any Instagram post/reel link from your phone to receive the instant verification verdict and HTML dossier attachment!

---

## 🧪 Running Automated Tests

Run the full 64-test suite:
```powershell
npm test
```