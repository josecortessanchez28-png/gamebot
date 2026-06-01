"""
GameBot — Bot de juegos para Telegram (sin necesidad de cerebro).
Listo para desplegar en Render / PythonAnywhere.
"""

import asyncio
import http.server
import logging
import os
import random
import threading
from typing import List, Tuple, Optional

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gamebot")

TOKEN = os.environ.get("GAMEBOT_TOKEN", "8611835716:AAH3R8brdAVvM33O77In7lnYlTj43G9YJcI")

# ---------------------------------------------------------------------------
# Snake Game
# ---------------------------------------------------------------------------

VACIO = "⬛"
CABEZA = "🟩"
CUERPO = "🟢"
COMIDA = "🍎"
MURO = "🟫"


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
            estado = "🎉 ¡GANASTE! 🎉"
        elif self.game_over:
            estado = "💀 GAME OVER 💀"
        else:
            estado = "🐍 Snake"
        return f"*{estado}*\nPuntuación: `{self.puntuacion}`\n\n{self.tablero()} | Vel: {self.velocidad:.2f}s"

    @property
    def botones(self):
        if self.game_over or self.ganado:
            return [[{"text": "🔄 Jugar de nuevo", "callback_data": "snake_reset"}]]
        return [
            [{"text": "⬆️", "callback_data": "snake_up"}],
            [
                {"text": "⬅️", "callback_data": "snake_left"},
                {"text": "⬇️", "callback_data": "snake_down"},
                {"text": "➡️", "callback_data": "snake_right"},
            ],
        ]


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


async def bucle(app, chat_id):
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
        "🎮 *GameBot*\n\n"
        "Comandos disponibles:\n"
        "`/snake` — Jugar al Snake\n\n"
        "Añádeme a un grupo y usa `/snake` ahí también.",
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
    t = asyncio.create_task(bucle(context.application, chat_id))
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
        t = asyncio.create_task(bucle(context.application, chat_id))
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
# Main
# ---------------------------------------------------------------------------

def main():
    # Puerto para el servidor web (Render lo asigna en PORT)
    port = int(os.environ.get("PORT", 8080))

    # Servidor web mínimo para mantener Render activo
    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *a):
            pass  # No llenar logs

    def run_http():
        server = http.server.HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()

    t = threading.Thread(target=run_http, daemon=True)
    t.start()
    logger.info("Servidor web en puerto %d", port)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("snake", cmd_snake))
    app.add_handler(CallbackQueryHandler(snake_cb, pattern="^snake_"))
    logger.info("GameBot iniciado")
    app.run_polling()


if __name__ == "__main__":
    main()
