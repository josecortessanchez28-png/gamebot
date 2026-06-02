"""
GameBot â€” Bot de juegos para Telegram con chat IA.
Listo para desplegar en Render / PythonAnywhere.
"""

import asyncio
import http.server
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
            return [[{"text": "ðŸ”„ Jugar de nuevo", "callback_data": "snake_reset"}]]
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

V = "â¬œ"
JUGADOR = "âŒ"
IA = "â­•"


class TicTacToe:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tablero = [V] * 9
        self.turno = JUGADOR
        self.ganador = None
        self.empate = False

    def movimientos_disponibles(self):
        return [i for i, c in enumerate(self.tablero) if c == V]

    def hacer_movimiento(self, idx):
        if self.tablero[idx] != V or self.ganador or self.empate:
            return False
        self.tablero[idx] = self.turno
        self._check_ganador()
        self.turno = IA if self.turno == JUGADOR else JUGADOR
        return True

    def _check_ganador(self):
        lineas = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6],
        ]
        for l in lineas:
            if self.tablero[l[0]] == self.tablero[l[1]] == self.tablero[l[2]] != V:
                self.ganador = self.tablero[l[0]]
                return
        if not self.movimientos_disponibles():
            self.empate = True

    def ia_mover(self):
        disp = self.movimientos_disponibles()
        if not disp:
            return
        mejor = self._minimax(self.tablero, IA)
        self.hacer_movimiento(mejor["pos"])

    def _minimax(self, board, jugador, depth=0):
        disp = [i for i, c in enumerate(board) if c == V]
        gan = self._eval(board)

        if gan == IA:
            return {"pos": None, "score": 10 - depth}
        if gan == JUGADOR:
            return {"pos": None, "score": depth - 10}
        if not disp:
            return {"pos": None, "score": 0}

        moves = []
        for i in disp:
            board[i] = jugador
            s = self._minimax(board, JUGADOR if jugador == IA else IA, depth + 1)["score"]
            board[i] = V
            moves.append({"pos": i, "score": s})

        mejor = max if jugador == IA else min
        return mejor(moves, key=lambda x: x["score"])

    def _eval(self, board):
        lineas = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6],
        ]
        for l in lineas:
            if board[l[0]] == board[l[1]] == board[l[2]] != V:
                return board[l[0]]
        return None

    def mostrar(self) -> str:
        texto = "ðŸŽ® *3 en Raya*\n\n"
        for i in range(0, 9, 3):
            texto += "".join(self.tablero[i:i+3]) + "\n"
        if self.ganador:
            texto += f"\n{'ðŸŽ‰ Ganaste!' if self.ganador == JUGADOR else 'ðŸ˜µ Perdiste!'}"
        elif self.empate:
            texto += "\nðŸ¤ Empate!"
        else:
            texto += f"\nTurno de {'ti' if self.turno == JUGADOR else 'la IA'}"
        return texto

    @property
    def botones(self):
        if self.ganador or self.empate:
            return [[{"text": "ðŸ”„ Otra partida", "callback_data": "ttt_reset"}]]
        filas = []
        for i in range(0, 9, 3):
            fila = []
            for j in range(3):
                idx = i + j
                txt = self.tablero[idx]
                if txt == V:
                    txt = "â¬œ"
                fila.append({"text": txt, "callback_data": f"ttt_{idx}"})
            filas.append(fila)
        return filas


# ---------------------------------------------------------------------------
# AI Chat
# ---------------------------------------------------------------------------

def chat_ai(mensaje):
    system = "Eres GameBot, un asistente divertido y jueguero. Responde en espanol, breve y con humor."
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": mensaje},
    ]
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
                json={"model": model, "messages": msgs, "max_tokens": 300},
                timeout=20,
            )
            if r.ok:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Chat error con {url.split('.')[1]}: {e}")
    return "ðŸ¤– No puedo pensar ahora, intentalo mas tarde."


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
    await update.message.reply_text(
        "ðŸŽ® *GameBot*\n\n"
        "Comandos:\n"
        "`/snake` â€” Jugar al Snake ðŸ\n"
        "`/ttt` â€” 3 en Raya âŒâ­•\n"
        "`/chat <texto>` â€” Hablar con IA ðŸ¤–\n"
        "O simplemente escribe algo y te respondo.",
        parse_mode="Markdown",
    )


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

    if data == "ttt_reset":
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
    if juego.turno != JUGADOR or juego.ganador or juego.empate:
        return
    juego.hacer_movimiento(idx)
    if not juego.ganador and not juego.empate:
        juego.ia_mover()
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
    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("Uso: `/chat <tu mensaje>`", parse_mode="Markdown")
        return
    await update.message.reply_text("Pensando...")
    resp = chat_ai(texto)
    await update.message.reply_text(resp)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto.startswith("/"):
        return
    await update.message.reply_text("Pensando...")
    resp = chat_ai(texto)
    await update.message.reply_text(resp)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    port = int(os.environ.get("PORT", 8080))

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *a):
            pass

    def run_http():
        server = http.server.HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()

    t = threading.Thread(target=run_http, daemon=True)
    t.start()
    logger.info("Servidor web en puerto %d", port)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("snake", cmd_snake))
    app.add_handler(CommandHandler("ttt", cmd_ttt))
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CallbackQueryHandler(snake_cb, pattern="^snake_"))
    app.add_handler(CallbackQueryHandler(ttt_cb, pattern="^ttt_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("GameBot iniciado")
    app.run_polling()


if __name__ == "__main__":
    main()
