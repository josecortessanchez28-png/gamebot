"""
GameBot â€” Bot de juegos para Telegram con chat IA.
Listo para desplegar en Render / PythonAnywhere.
"""

import asyncio
import http
import json
import logging
import os
import random
import threading
from typing import Tuple

import requests
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gamebot")

TOKEN = os.environ.get("GAMEBOT_TOKEN", "8611835716:AAH3R8brdAVvM33O77In7lnYlTj43G9YJcI")
GROQ_KEY = os.environ.get("GROQ_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

# ---------------------------------------------------------------------------
# Snake Game
# ---------------------------------------------------------------------------

VACIO = "â¬›"
CABEZA = "ðŸŸ©"
CUERPO = "ðŸŸ¢"
COMIDA = "ðŸŽ"
MURO = "ðŸŸ«"


class SnakeGame:
    def __init__(self, ancho=10, alto=10):
        self.ancho = ancho
        self.alto = alto
        self.reset()

    def reset(self):
        cx, cy = self.ancho // 2, self.alto // 2
        self.serpiente = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direccion = (1, 0)
        self.comida = self._generar_comida()
        self.puntuacion = 0
        self.game_over = False
        self.ganado = False

    def _generar_comida(self):
        disponibles = [
            (x, y) for x in range(self.ancho) for y in range(self.alto)
            if (x, y) not in self.serpiente
        ]
        return random.choice(disponibles) if disponibles else None

    @property
    def velocidad(self) -> float:
        return max(0.5, 1.0 - self.puntuacion * 0.04)

    def cambiar_direccion(self, nueva: Tuple[int, int]):
        if (nueva[0] * -1, nueva[1] * -1) != self.direccion:
            self.direccion = nueva

    def mover(self):
        if self.game_over or self.ganado:
            return False
        cabeza = self.serpiente[0]
        nueva = (cabeza[0] + self.direccion[0], cabeza[1] + self.direccion[1])
        if not (0 <= nueva[0] < self.ancho and 0 <= nueva[1] < self.alto):
            self.game_over = True
            return False
        if nueva in self.serpiente:
            self.game_over = True
            return False
        self.serpiente.insert(0, nueva)
        if nueva == self.comida:
            self.puntuacion += 1
            self.comida = self._generar_comida()
            if self.comida is None:
                self.ganado = True
                return False
        else:
            self.serpiente.pop()
        return True

    def tablero(self) -> str:
        lineas = [MURO * (self.ancho + 2)]
        for y in range(self.alto):
            fila = [MURO]
            for x in range(self.ancho):
                if (x, y) == self.serpiente[0]:
                    fila.append(CABEZA)
                elif (x, y) in self.serpiente:
                    fila.append(CUERPO)
                elif self.comida and (x, y) == self.comida:
                    fila.append(COMIDA)
                else:
                    fila.append(VACIO)
            fila.append(MURO)
            lineas.append("".join(fila))
        lineas.append(MURO * (self.ancho + 2))
        return "\n".join(lineas)

    def estado_texto(self) -> str:
        if self.ganado:
            estado = "ðŸŽ‰ Â¡GANASTE! ðŸŽ‰"
        elif self.game_over:
            estado = "ðŸ’€ GAME OVER ðŸ’€"
        else:
            estado = "ðŸ Snake"
        return f"*{estado}*\nPuntuaciÃ³n: `{self.puntuacion}`\n\n{self.tablero()} | Vel: {self.velocidad:.2f}s"

    @property
    def botones(self):
        if self.game_over or self.ganado:
            return [
                [{"text": "ðŸ”„ Jugar de nuevo", "callback_data": "snake_reset"}],
                [{"text": "ðŸ—£ï¸ Decir quÃ© tal", "callback_data": "snake_gameover_opinion"}],
            ]
        return [
            [{"text": "â¬†ï¸", "callback_data": "snake_up"}],
            [
                {"text": "â¬…ï¸", "callback_data": "snake_left"},
                {"text": "â¬‡ï¸", "callback_data": "snake_down"},
                {"text": "âž¡ï¸", "callback_data": "snake_right"},
            ],
        ]


# ---------------------------------------------------------------------------
# Tic-Tac-Toe (3 en raya)
# ---------------------------------------------------------------------------

class TicTacToe:
    def __init__(self):
        self.reset()

    def reset(self):
        self.b = [" "] * 9
        self.turno = "X"
        self.ganador = None
        self.empate = False

    def libres(self):
        return [i for i, c in enumerate(self.b) if c == " "]

    def mover(self, idx):
        if self.b[idx] != " " or self.ganador or self.empate:
            return False
        self.b[idx] = self.turno
        self._check()
        self.turno = "O" if self.turno == "X" else "X"
        return True

    def _check(self):
        for a,b,c in [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]:
            if self.b[a] == self.b[b] == self.b[c] != " ":
                self.ganador = self.b[a]
                return
        if not self.libres():
            self.empate = True

    def ia(self):
        mejor, score = None, -999
        for i in self.libres():
            self.b[i] = "O"
            s = self._minimax(self.b, 0, False)
            self.b[i] = " "
            if s > score:
                score, mejor = s, i
        if mejor is not None:
            self.mover(mejor)

    def _minimax(self, b, depth, esMax):
        g = self._eval_board(b)
        if g == "O": return 10 - depth
        if g == "X": return depth - 10
        if not [i for i,c in enumerate(b) if c == " "]: return 0
        if esMax:
            best = -999
            for i, c in enumerate(b):
                if c == " ":
                    b[i] = "O"
                    best = max(best, self._minimax(b, depth+1, False))
                    b[i] = " "
            return best
        else:
            best = 999
            for i, c in enumerate(b):
                if c == " ":
                    b[i] = "X"
                    best = min(best, self._minimax(b, depth+1, True))
                    b[i] = " "
            return best

    def _eval_board(self, b):
        for a,b2,c in [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]:
            if b[a] == b[b2] == b[c] != " ":
                return b[a]
        return None

    def mostrar(self):
        t = "ðŸŽ® *3 en Raya*\n\n"
        for i in range(0, 9, 3):
            t += "|".join(f" {x} " if x != " " else "   " for x in self.b[i:i+3]) + "\n"
            if i < 6: t += "---+---+---\n"
        if self.ganador:
            t += f"\n{'ðŸŽ‰ Ganaste!' if self.ganador == 'X' else 'ðŸ˜µ Perdiste!'}"
        elif self.empate:
            t += "\nðŸ¤ Empate!"
        else:
            t += f"\nTurno de {'ti (X)' if self.turno == 'X' else 'IA (O)'}"
        return t

    def botones(self):
        if self.ganador or self.empate:
            return [[{"text": "ðŸ”„ Otra", "callback_data": "ttt_rst"}]]
        filas = []
        for i in range(0, 9, 3):
            fila = []
            for j in range(3):
                c = self.b[i+j]
                txt = {" ": "âž–", "X": "âŒ", "O": "â­•"}.get(c, c)
                fila.append({"text": txt, "callback_data": f"ttt_{i+j}"})
            filas.append(fila)
        return filas


# ---------------------------------------------------------------------------
# AI Chat con memoria y personalidad
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Eres GAMEBOT, un bot creado para divertir y entretener a los miembros del grupo.

PERSONALIDAD:
- Eres gamberro, usas lenguaje callejero y coloquial
- Saludazo siempre: "Bueno lo primero de todo, Â¿cÃ³mo estÃ¡n los mÃ¡quinas?" o "QuÃ© pasa chavales"
- Cuando alguien pregunta quÃ© hacer: "Â¿Quieres jugar a un juego?"
- DespuÃ©s de una partida: preguntas quÃ© tal les ha parecido
- Respondes con humor, eres breve y directo
- Usas espaÃ±ol de EspaÃ±a callejero

JUEGOS DISPONIBLES:
- /snake: El Snake de toda la vida, con botones para moverse
- /ttt: 3 en Raya contra la IA (aviso: la IA es dura de cojones)
- /chat <texto>: Hablar conmigo directamente

COMANDOS:
/start - MenÃº principal
/snake - Jugar al Snake
/ttt - 3 en Raya
/chat <texto> - Hablar conmigo
/help - Ayuda

INFORMACIÃ“N IMPORTANTE:
- Te llamas GameBot
- Si te preguntan sobre los juegos, los explicas con orgullo
- Pueden consultarte cualquier cosa sobre cÃ³mo jugar
- Siempre preguntas quÃ© tal les ha parecido despuÃ©s de una partida
- Invitas a jugar con "Â¿Quieres jugar a un juego?"
- Si te dicen que no saben jugar, les explicas sin reirte demasiado"""

memoria: dict = {}


def chat_ai(mensaje, chat_id):
    if chat_id not in memoria:
        memoria[chat_id] = []
    memoria[chat_id].append({"role": "user", "content": mensaje})
    history = memoria[chat_id][-20:]

    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for url, key, model in [
        ("https://api.groq.com/openai/v1/chat/completions", GROQ_KEY, "llama-3.3-70b-versatile"),
        ("https://openrouter.ai/api/v1/chat/completions", OPENROUTER_KEY, "meta-llama/llama-3.1-8b-instant:free"),
    ]:
        if not key:
            continue
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": msgs, "max_tokens": 400},
                timeout=20,
            )
            if r.ok:
                resp = r.json()["choices"][0]["message"]["content"].strip()
                memoria[chat_id].append({"role": "assistant", "content": resp})
                return resp
        except Exception as e:
            logger.warning(f"Chat error con {url.split('.')[1]}: {e}")
    return "TÃ­o, ahora mismo no puedo pensar, dame un segundÃ­n y vuelve a preguntar."


# ---------------------------------------------------------------------------
# Bot handlers
# ---------------------------------------------------------------------------

partidas: dict = {}
_tareas: dict = {}


def obtener_juego(chat_id):
    d = partidas.get(chat_id)
    return d["juego"] if d else None


def guardar_id(chat_id, msg_id):
    if chat_id in partidas:
        partidas[chat_id]["msg_id"] = msg_id


def obtener_id(chat_id):
    d = partidas.get(chat_id)
    return d["msg_id"] if d else None


def limpiar(chat_id):
    partidas.pop(chat_id, None)


async def bucle_snake(app, chat_id):
    try:
        while True:
            juego = obtener_juego(chat_id)
            if not juego or juego.game_over or juego.ganado:
                break
            await asyncio.sleep(juego.velocidad)
            juego = obtener_juego(chat_id)
            if not juego or juego.game_over or juego.ganado:
                break
            juego.mover()
            mid = obtener_id(chat_id)
            if mid:
                try:
                    await app.bot.edit_message_text(
                        chat_id=chat_id, message_id=mid,
                        text=juego.estado_texto(),
                        reply_markup=InlineKeyboardMarkup(juego.botones),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    if "Flood" in str(e):
                        await asyncio.sleep(78)
                    else:
                        logger.warning("edit error: %s", e)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("bucle error: %s", e)
    finally:
        _tareas.pop(chat_id, None)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    resp = chat_ai("Saluda y explica quien eres y que ofreces", chat_id)
    await update.message.reply_text(resp)


async def cmd_snake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in _tareas:
        _tareas[chat_id].cancel()
    limpiar(chat_id)
    juego = SnakeGame()
    partidas[chat_id] = {"juego": juego, "msg_id": 0}
    texto = juego.estado_texto()
    teclado = InlineKeyboardMarkup(juego.botones)
    msg = await update.message.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")
    guardar_id(chat_id, msg.message_id)
    t = asyncio.create_task(bucle_snake(context.application, chat_id))
    _tareas[chat_id] = t
    logger.info("Snake chat %d", chat_id)


async def snake_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = update.effective_chat.id
    data = q.data

    if data == "snake_reset":
        if chat_id in _tareas:
            _tareas[chat_id].cancel()
        limpiar(chat_id)
        juego = SnakeGame()
        partidas[chat_id] = {"juego": juego, "msg_id": 0}
        texto = juego.estado_texto()
        teclado = InlineKeyboardMarkup(juego.botones)
        await q.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")
        guardar_id(chat_id, q.message.message_id)
        t = asyncio.create_task(bucle_snake(context.application, chat_id))
        _tareas[chat_id] = t
        return

    if data == "snake_gameover_opinion":
        resp = chat_ai("el usuario me dice como le ha parecido el snake, responde brevemente", chat_id)
        await q.edit_message_text(resp)
        return

    mapa = {"snake_up": (0, -1), "snake_down": (0, 1), "snake_left": (-1, 0), "snake_right": (1, 0)}
    nd = mapa.get(data)
    if not nd:
        return
    juego = obtener_juego(chat_id)
    if juego and not juego.game_over and not juego.ganado:
        juego.cambiar_direccion(nd)


# ---------------------------------------------------------------------------
# Tic-Tac-Toe handlers
# ---------------------------------------------------------------------------

async def cmd_ttt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in _tareas:
        _tareas[chat_id].cancel()
    limpiar(chat_id)
    juego = TicTacToe()
    partidas[chat_id] = {"juego": juego, "msg_id": 0}
    texto = juego.mostrar()
    teclado = InlineKeyboardMarkup(juego.botones)
    msg = await update.message.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")
    guardar_id(chat_id, msg.message_id)
    logger.info("TTT chat %d", chat_id)


async def ttt_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = update.effective_chat.id
    data = q.data

    juego = obtener_juego(chat_id)
    if not juego:
        return

    if data == "ttt_rst":
        if chat_id in _tareas:
            _tareas[chat_id].cancel()
        limpiar(chat_id)
        juego = TicTacToe()
        partidas[chat_id] = {"juego": juego, "msg_id": 0}
        texto = juego.mostrar()
        teclado = InlineKeyboardMarkup(juego.botones)
        await q.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")
        guardar_id(chat_id, q.message.message_id)
        return

    if not data.startswith("ttt_"):
        return
    idx = int(data.split("_")[1])
    if juego.turno != "X" or juego.ganador or juego.empate:
        return
    juego.mover(idx)
    if not juego.ganador and not juego.empate:
        juego.ia()
    texto = juego.mostrar()
    teclado = InlineKeyboardMarkup(juego.botones)
    try:
        await q.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")
    except Exception as e:
        logger.warning("ttt edit error: %s", e)


# ---------------------------------------------------------------------------
# Chat handler (texto libre)
# ---------------------------------------------------------------------------

async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("Uso: `/chat <tu mensaje>`", parse_mode="Markdown")
        return
    await update.message.reply_text("Pensando...")
    resp = chat_ai(texto, chat_id)
    await update.message.reply_text(resp)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto = update.message.text.strip()
    if texto.startswith("/"):
        return
    await update.message.reply_text("Pensando...")
    resp = chat_ai(texto, chat_id)
    await update.message.reply_text(resp)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import http.server
    import json as _json
    import threading

    port = int(os.environ.get("PORT", 8080))
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://gamebot-dd6p.onrender.com")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("snake", cmd_snake))
    app.add_handler(CommandHandler("ttt", cmd_ttt))
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CallbackQueryHandler(snake_cb, pattern="^snake_"))
    app.add_handler(CallbackQueryHandler(ttt_cb, pattern="^ttt_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.start())
    loop.run_until_complete(app.updater.start_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="telegram-webhook",
    ))
    loop.run_until_complete(app.bot.set_webhook(url=f"{url}/telegram-webhook"))
    logger.info("Webhook %s/telegram-webhook", url)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
