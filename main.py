# Bot ClubKdrama Original 0.5
import mysql.connector
import os
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Parámetros de configuración
TOKEN = os.getenv("TELEGRAM_TOKEN")  
DB_URL = os.getenv("MYSQL_URL")       

# Conectar a la base de datos MySQL
def conectar_db():
    try:
        url = os.getenv("MYSQL_URL")
        result = urllib.parse.urlparse(url)
        connection = mysql.connector.connect(
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
            database=result.path[1:]
        )
        return connection
    except mysql.connector.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# Crear la tabla si no existe
def crear_tabla():
    conn = conectar_db()
    if conn:
        with conn.cursor() as cursor:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS series (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                image_url VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                episode_links TEXT NOT NULL,
                estado VARCHAR(50) DEFAULT 'finalizado'
            )
            ''')
            conn.commit()
        conn.close()

crear_tabla()

# Función de inicio /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Buscar Series"), KeyboardButton("En Emisión")],
        [KeyboardButton("Canal"), KeyboardButton("Chat"), KeyboardButton("Ayuda")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("¡Bienvenido al bot de Club Kdrama! Elige una opción:", reply_markup=reply_markup)

# Función para buscar series
async def buscar_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buscando'] = True
    context.user_data['estado'] = 'buscando_series'

    await update.message.reply_text("¿Qué serie quieres buscar? Por favor, ingresa el nombre o palabra clave.")

# Función que muestra series en emisión
async def series_en_emision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = conectar_db()
    if conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, title FROM series WHERE estado = 'emisión' ORDER BY title")
            series = cursor.fetchall()
        conn.close()

        if not series:
            await update.message.reply_text("No hay series en emisión en este momento.")
            return

        # Mostrar lista de series en emisión numeradas
        respuesta = "Series en emisión:\n"
        for idx, serie in enumerate(series, 1):
            respuesta += f"{idx}. {serie[1]}\n"
        
        await update.message.reply_text(respuesta + "\nPor favor, ingresa el número de la serie que deseas ver.")
        context.user_data['resultados'] = series
        context.user_data['estado'] = 'seleccionando_en_emision'
    else:
        await update.message.reply_text("No se pudo conectar a la base de datos. Intenta nuevamente más tarde.")

# Función que recibe el término de búsqueda y consulta la base de datos
async def recibir_busqueda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('buscando') and context.user_data.get('estado') == 'buscando_series':
        query = update.message.text.strip()

        if len(query) < 4:
            await update.message.reply_text("Por favor, ingresa al menos 4 caracteres para buscar.")
            return

        await update.message.reply_text("Buscando en la base de datos, por favor espera...")

        conn = conectar_db()
        if conn is None:
            await update.message.reply_text("No se pudo conectar a la base de datos. Intenta nuevamente más tarde.")
            return

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM series WHERE title LIKE %s ORDER BY title LIMIT 9", ('%' + query + '%',))
        resultados = cursor.fetchall()
        conn.close()

        if not resultados:
            await update.message.reply_text("No se encontraron resultados con los criterios de búsqueda ingresados.")
            return

        respuesta = "Resultados encontrados:\n"
        for idx, serie in enumerate(resultados, 1):
            respuesta += f"{idx}. {serie[1]}\n"

        await update.message.reply_text(respuesta + "\nPor favor, ingresa el número correspondiente a la serie que deseas ver.")
        context.user_data['resultados'] = resultados
        context.user_data['estado'] = 'seleccionando'
    else:
        await update.message.reply_text("Por favor, utiliza el botón 'Buscar Series' para iniciar la búsqueda.")

# Función que muestra los detalles de la serie seleccionada
async def mostrar_detalles_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    estado = context.user_data.get('estado')
    if estado in ['seleccionando', 'seleccionando_en_emision']:
        numero_seleccionado = update.message.text.strip()

        if not numero_seleccionado.isdigit():
            await update.message.reply_text("Por favor, ingresa un número válido.")
            return

        numero_seleccionado = int(numero_seleccionado)
        resultados = context.user_data.get('resultados', [])

        if 1 <= numero_seleccionado <= len(resultados):
            serie = resultados[numero_seleccionado - 1]
            title, cover, description, episode_links = serie[1], serie[2], serie[3], serie[4].split(',')

            await update.message.reply_text(title)
            await context.bot.send_animation(chat_id=update.message.chat.id, animation=cover, caption=description)

            # Crear botones inline para los episodios en filas de 3
            inline_keyboard = []
            row = []
            for idx, link in enumerate(episode_links):
                row.append(InlineKeyboardButton(f"EP{str(idx + 1).zfill(2)}", url=link))
                if (idx + 1) % 3 == 0:
                    inline_keyboard.append(row)
                    row = []
            if row:
                inline_keyboard.append(row)

            await update.message.reply_text("Episodios disponibles:", reply_markup=InlineKeyboardMarkup(inline_keyboard))

            context.user_data['estado'] = None
        else:
            await update.message.reply_text("Número no válido. Por favor, ingresa un número de la lista.")
    else:
        await update.message.reply_text("No estás en modo de selección. Por favor, busca una serie primero.")

# Handlers para los comandos del bot
application = ApplicationBuilder().token(TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Regex('^Buscar Series$'), buscar_series))
application.add_handler(MessageHandler(filters.Regex('^En Emisión$'), series_en_emision))
application.add_handler(MessageHandler(filters.Regex('^Canal$'), canal))
application.add_handler(MessageHandler(filters.Regex('^Chat$'), chat))
application.add_handler(MessageHandler(filters.Regex('^Ayuda$'), ayuda))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\d+$'), mostrar_detalles_series))
application.add_handler(MessageHandler(filters.TEXT & ~filters.Regex(r'^\d+$'), recibir_busqueda))

application.run_polling()
