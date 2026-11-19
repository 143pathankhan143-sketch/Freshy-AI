import express from 'express';
import { fileURLToPath, pathToFileURL } from 'node:url';

export function createApp({ key = process.env.GEMINI_API_KEY, model = process.env.GEMINI_MODEL || 'gemini-2.5-flash', request = fetch } = {}) {
  const app = express();
  app.disable('x-powered-by');
  app.use(express.static(fileURLToPath(new URL('./public/', import.meta.url))));
  app.post('/api/chat', express.json({ limit: '512kb' }), async (req, res) => {
    const turns = req.body?.messages;
    if (!Array.isArray(turns) || turns.length % 2 !== 1 || turns.length > 21 ||
        !turns.every((m, i) => m?.role === (i % 2 ? 'assistant' : 'user') &&
          typeof m.content === 'string' && m.content.trim() && m.content.length <= (i % 2 ? 12000 : 4000))) {
      return res.status(400).json({ error: 'Invalid chat history or message length.' });
    }
    if (!key?.trim()) return res.status(503).json({ error: 'Gemini is not configured. Set GEMINI_API_KEY on the server, then restart Freshy.' });
    try {
      const upstream = await request(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`, {
        method: 'POST', signal: AbortSignal.timeout(45000),
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: 'You are Freshy, a helpful text chatbot. Match the user’s language, including Hindi, Hinglish and English. You cannot take external actions.' }] },
          contents: turns.map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] })),
          generationConfig: { maxOutputTokens: 2048 },
        }),
      });
      if (upstream.status === 429) return res.status(429).json({ error: 'Gemini quota or rate limit reached. Please try later.' });
      if (!upstream.ok) throw new Error('provider');
      const data = await upstream.json();
      const reply = data.candidates?.[0]?.content?.parts?.filter(p => !p.thought).map(p => p.text || '').join('').trim();
      if (!reply || reply.length > 12000) throw new Error('invalid reply');
      return res.json({ reply });
    } catch {
      return res.status(502).json({ error: 'No reply from Gemini. Check the server connection and model settings, then retry.' });
    }
  });
  app.use((err, req, res, next) => res.status(err.status || 500).json({ error: 'Unable to process this request.' }));
  return app;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  createApp().listen(process.env.PORT || 3000, process.env.HOST || '127.0.0.1');
}
