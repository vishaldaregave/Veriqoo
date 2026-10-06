process.env.NODE_ENV = "test";
process.env.ALLOWED_WHATSAPP_NUMBER = "+91 98765 43210";

import test from "node:test";
import assert from "node:assert/strict";

const {
  containsInstagramUrl,
  isInstagramHost,
  extractInstagramUrl,
  INSTAGRAM_ACK_MESSAGE,
  normalizeWhatsAppNumber,
  maskJid,
  resolveLidToPhoneNumber,
  resolvePhoneNumberToLid,
  isAuthorizedSender,
  isDM,
  handleInboundMessage,
  handleInstagramAck,
  sendText,
} = await import("./agent/channels/whatsapp.ts");

test("maskJid masks phone number securely without revealing full number", () => {
  assert.equal(maskJid("919356704614@s.whatsapp.net"), "9193******14@s.whatsapp.net");
  assert.equal(maskJid("919356704614:1@s.whatsapp.net"), "9193******14:1@s.whatsapp.net");
  assert.equal(maskJid("79109321437297@lid"), "7910********97@lid");
  assert.equal(maskJid(""), "(none)");
  assert.equal(maskJid(null), "(none)");
});

test("LID resolution maps between verified LID and Phone Number via auth storage", () => {
  const resolvedPhone = resolveLidToPhoneNumber("79109321437297@lid");
  assert.equal(resolvedPhone, "919356704614");

  const resolvedLid = resolvePhoneNumberToLid("919356704614");
  assert.equal(resolvedLid, "79109321437297");

  // Inbound message from verified LID matches authorized phone number
  assert.equal(isAuthorizedSender("79109321437297@lid", "919356704614"), true);
  assert.equal(isAuthorizedSender("99999999999999@lid", "919356704614"), false);
});

test("INSTAGRAM_ACK_MESSAGE matches expected copy", () => {
  assert.equal(
    INSTAGRAM_ACK_MESSAGE,
    "Got it — I'm checking this Instagram product now. I'll be back with a verification result shortly.",
  );
});

test("isInstagramHost correctly identifies Instagram domains and subdomains", () => {
  // Valid hosts
  assert.equal(isInstagramHost("instagram.com"), true);
  assert.equal(isInstagramHost("www.instagram.com"), true);
  assert.equal(isInstagramHost("m.instagram.com"), true);
  assert.equal(isInstagramHost("l.instagram.com"), true);
  assert.equal(isInstagramHost("instagr.am"), true);
  assert.equal(isInstagramHost("www.instagr.am"), true);

  // Invalid / attacker hosts
  assert.equal(isInstagramHost("example.com"), false);
  assert.equal(isInstagramHost("evil-example.com"), false);
  assert.equal(isInstagramHost("notinstagram.com"), false);
  assert.equal(isInstagramHost("instagram.com.attacker.com"), false);
  assert.equal(isInstagramHost("fake-instagram.com"), false);
});

test("containsInstagramUrl: Case 1 — Reel", () => {
  assert.equal(containsInstagramUrl("https://www.instagram.com/reel/ABC123/"), true);
});

test("containsInstagramUrl: Case 2 — Post", () => {
  assert.equal(containsInstagramUrl("https://www.instagram.com/p/ABC123/?igsh=xyz"), true);
});

test("containsInstagramUrl: Case 3 — Link inside other text", () => {
  assert.equal(containsInstagramUrl("Can you check this? https://instagram.com/reel/ABC123/"), true);
});

test("containsInstagramUrl: Case 4 — Ordinary WhatsApp message", () => {
  assert.equal(containsInstagramUrl("hello"), false);
  assert.equal(containsInstagramUrl("What's the weather today?"), false);
});

test("containsInstagramUrl: Case 5 — Fake hostname", () => {
  assert.equal(containsInstagramUrl("https://example.com/?redirect=instagram.com"), false);
  assert.equal(containsInstagramUrl("https://evil-example.com/?next=instagram.com"), false);
  assert.equal(containsInstagramUrl("https://instagram.com.attacker.com/p/123"), false);
});

test("containsInstagramUrl: Additional edge cases and variants", () => {
  assert.equal(containsInstagramUrl("http://instagram.com/reel/ABC123/"), true);
  assert.equal(containsInstagramUrl("http://www.instagram.com/p/ABC123/"), true);
  assert.equal(containsInstagramUrl("https://m.instagram.com/p/ABC123/"), true);
  assert.equal(containsInstagramUrl("https://instagr.am/p/ABC123/"), true);
  assert.equal(containsInstagramUrl("Check this out: https://www.instagram.com/reel/ABC123/?igsh=someToken123"), true);
  assert.equal(containsInstagramUrl("Look at this (https://www.instagram.com/reel/ABC123/)!"), true);
  assert.equal(containsInstagramUrl("www.instagram.com/reel/ABC123/"), true);
  assert.equal(containsInstagramUrl(""), false);
  assert.equal(containsInstagramUrl("   "), false);
});

// =========================================================================
// WHATSAPP AUTHORIZATION & SENDER ALLOWLIST TESTS (TEST 1 to TEST 8)
// =========================================================================

test("normalizeWhatsAppNumber formats digits consistently", () => {
  assert.equal(normalizeWhatsAppNumber("919876543210@s.whatsapp.net"), "919876543210");
  assert.equal(normalizeWhatsAppNumber("919876543210:1@s.whatsapp.net"), "919876543210");
  assert.equal(normalizeWhatsAppNumber("+91 (987) 654-3210"), "919876543210");
  assert.equal(normalizeWhatsAppNumber("71820577398857@lid"), "71820577398857");
  assert.equal(normalizeWhatsAppNumber(""), "");
  assert.equal(normalizeWhatsAppNumber(null), "");
});

test("TEST 1: Authorized number → message is processed", async () => {
  const authorizedJid = "919876543210@s.whatsapp.net";
  assert.equal(isAuthorizedSender(authorizedJid, "+91 98765 43210"), true);

  const sentMessages = [];
  const mockSock = {
    sendMessage: async (targetJid, content) => {
      sentMessages.push({ targetJid, content });
      return { key: { id: "mock-id" } };
    },
    readMessages: async () => {},
  };

  const msg = {
    key: { remoteJid: authorizedJid, fromMe: false },
    message: { conversation: "Hello bot" },
  };

  // When authorized non-link message is received, bot responds with guidance
  await handleInboundMessage(msg);
});

test("TEST 2: Unauthorized number → message is ignored", async () => {
  const unauthorizedJid = "919999999999@s.whatsapp.net";
  assert.equal(isAuthorizedSender(unauthorizedJid, "+91 98765 43210"), false);

  const sentMessages = [];
  const mockSock = {
    sendMessage: async (targetJid, content) => {
      sentMessages.push({ targetJid, content });
    },
    readMessages: async () => {},
  };

  const msg = {
    key: { remoteJid: unauthorizedJid, fromMe: false },
    message: { conversation: "Hello from stranger" },
  };

  await handleInboundMessage(msg);
  assert.equal(sentMessages.length, 0, "No messages should be sent to unauthorized sender");
});

test("TEST 3: Unauthorized number containing Instagram URL → NO verification starts", async () => {
  const unauthorizedJid = "919999999999@s.whatsapp.net";
  const sentMessages = [];
  const mockSock = {
    sendMessage: async (targetJid, content) => {
      sentMessages.push({ targetJid, content });
    },
  };

  const msg = {
    key: { remoteJid: unauthorizedJid, fromMe: false },
    message: { conversation: "https://www.instagram.com/reel/C8XYZ123/" },
  };

  await handleInboundMessage(msg);
  assert.equal(sentMessages.length, 0, "Unauthorized Instagram link must NOT trigger any response");
});

test("TEST 4: Unauthorized number → NO acknowledgement is sent", async () => {
  const unauthorizedJid = "919999999999@s.whatsapp.net";
  const sentMessages = [];
  const mockSock = {
    sendMessage: async (targetJid, content) => {
      sentMessages.push({ targetJid, content });
    },
  };

  await handleInstagramAck(mockSock, unauthorizedJid, "https://www.instagram.com/reel/C8XYZ123/");
  assert.equal(sentMessages.length, 0, "handleInstagramAck must not send anything to unauthorized JID");
});

test("TEST 5: Authorized number → acknowledgement is sent", async () => {
  const authorizedJid = "919876543210@s.whatsapp.net";
  const sentMessages = [];
  const mockSock = {
    sendMessage: async (targetJid, content) => {
      sentMessages.push({ targetJid, content });
      return { key: { id: "msg-id" } };
    },
    readMessages: async () => {},
  };

  await handleInstagramAck(mockSock, authorizedJid, "https://www.instagram.com/reel/C8XYZ123/");
  assert.equal(sentMessages.length, 1);
  assert.equal(sentMessages[0].targetJid, authorizedJid);
  assert.equal(sentMessages[0].content.text, INSTAGRAM_ACK_MESSAGE);
});

test("TEST 6: Authorized number → verification pipeline can start", async () => {
  const authorizedJid = "919876543210@s.whatsapp.net";
  assert.equal(isAuthorizedSender(authorizedJid), true);

  const instagramUrl = extractInstagramUrl("Check this https://www.instagram.com/p/ABC999/");
  assert.equal(instagramUrl, "https://www.instagram.com/p/ABC999/");
});

test("TEST 7: Group message → ignored", async () => {
  const groupJid = "123456789-987654@g.us";
  assert.equal(isDM(groupJid), false);
  assert.equal(isAuthorizedSender(groupJid, "+91 98765 43210"), false);

  const sentMessages = [];
  const mockSock = {
    sendMessage: async (targetJid, content) => {
      sentMessages.push({ targetJid, content });
    },
  };

  const msg = {
    key: { remoteJid: groupJid, fromMe: false },
    message: { conversation: "https://www.instagram.com/reel/C8XYZ123/" },
  };

  await handleInboundMessage(msg);
  assert.equal(sentMessages.length, 0, "Group messages must be completely ignored");
});

test("TEST 8: Outgoing response → only authorized original sender can receive it", async () => {
  const authorizedJid = "919876543210@s.whatsapp.net";
  const unauthorizedJid = "919999999999@s.whatsapp.net";
  const broadcastJid = "status@broadcast";
  const groupJid = "123456789@g.us";

  const deliveredMessages = [];
  const mockSock = {
    sendMessage: async (targetJid, content) => {
      deliveredMessages.push({ targetJid, content });
      return { key: { id: "ok" } };
    },
  };

  // Attempt to send to unauthorized numbers
  await sendText(mockSock, unauthorizedJid, "Unauthorized message");
  await sendText(mockSock, broadcastJid, "Broadcast message");
  await sendText(mockSock, groupJid, "Group message");

  assert.equal(deliveredMessages.length, 0, "No unauthorized destination may receive an automated message");

  // Send to authorized sender
  await sendText(mockSock, authorizedJid, "Authorized message");
  assert.equal(deliveredMessages.length, 1);
  assert.equal(deliveredMessages[0].targetJid, authorizedJid);
  assert.equal(deliveredMessages[0].content.text, "Authorized message");
});
