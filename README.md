# Intermezzo

A mobile-friendly chess game analyzer that walks you through your games move by move with spoken commentary. Paste a PGN, tap through the board, and hear coaching insights powered by DeepSeek and Kokoro TTS.

---

## Features

- **Spoken overview** — each game opens with a 2-3 sentence intro setting the scene
- **Move-by-move commentary** — tap the board or the → button to advance; each move is narrated with coaching insight, pattern observations, and the occasional dry humor
- **Key move highlights** — blunders, brilliances, and turning points are flagged with a ★ and a special callout
- **Closing summary** — a punchy 2-sentence debrief after the final move
- **Coaching profile** — after analyzing multiple games, tap "Hear My Profile" for a cross-game pattern analysis
- **Export / Import keys** — save your API keys to a local JSON file so you don't have to re-enter them every session
- **Tone control** — choose Beginner, Club, or Advanced commentary style

---

## Setup

Intermezzo runs entirely in the browser with no backend. You need two API keys:

### 1. DeepSeek API Key
Used for chess analysis and commentary.
- Sign up at [platform.deepseek.com](https://platform.deepseek.com)
- Create an API key and copy it

### 2. OpenRouter API Key
Used for Kokoro TTS (text-to-speech). Without this, the app falls back to your device's built-in speech synthesis.
- Sign up at [openrouter.ai](https://openrouter.ai)
- Create an API key and copy it

### First Launch
1. Open the app
2. Enter your DeepSeek key, OpenRouter key, and your Chess.com username
3. Select your preferred analysis tone
4. Tap **Continue →**
5. Use **↓ Export Keys** to save your keys locally for next time

---

## How to Use

1. Go to [Chess.com](https://chess.com), open a game, and copy the PGN
2. Paste it into the text area on the home screen
3. Tap **Analyze Game**
4. When the board loads, tap anywhere on the board (or →) to hear the intro
5. Keep tapping → to step through the game move by move
6. ← steps back; tapping the board also advances

---

## Tech

- **[DeepSeek](https://platform.deepseek.com)** — `deepseek-chat` model for analysis
- **[OpenRouter](https://openrouter.ai)** — `hexgrad/kokoro-82m` for TTS
- **[chess.js](https://github.com/jhlywa/chess.js)** — PGN parsing and board state
- Pure HTML/CSS/JS — no build step, no framework, deployable anywhere static
