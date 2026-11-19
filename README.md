# Freshy AI · Text Chat

The first standalone milestone lives in `chatbot/`. Ask Freshy questions in Hindi, Hinglish or English and follow up in the same conversation. This is a text generator, not a desktop agent. The original research and versioned source archive are unchanged.

## Run locally

1. Install Node.js 22.9+ and open a terminal in `chatbot/`.
2. Run `npm ci`.
3. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` locally. Optionally set `GEMINI_MODEL` to a supported Gemini model available to your account. Never commit your key.
4. Run `npm start`, then open **http://127.0.0.1:3000**. The server needs outbound access to `generativelanguage.googleapis.com` for real replies.
5. Try “Photosynthesis kya hai?” followed by “Ab isi ko do lines mein samjhao.”

The browser keeps the conversation in tab memory. Each request sends the latest ten completed exchanges plus the new message through the backend to Gemini. New chat or refresh clears the tab; this does not control provider-side retention. The app does not store chats or give the model tools, filesystem access, or voice features.

`npm test` runs offline HTTP tests with a simulated provider. No key is required. `HOST` and `PORT` override the default local listener. Use this as a single-user app; add authentication and usage limits before exposing a key-backed server publicly.
