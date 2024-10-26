# Bot ClubKdrama Original 0.5

import mysql.connector
import os
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Parámetros de configuración (usando variables de entorno para seguridad)
TOKEN = os.getenv("TELEGRAM_TOKEN")  # Debes asegurarte de definir TELEGRAM_TOKEN en el entorno
DB_URL = os.getenv("MYSQL_URL")       # Asegúrate de definir MYSQL_URL en el entorno

# Conectar a la base de datos MySQL
def conectar_db():
    try:
        # Descomponer la URL de conexión
        url = os.getenv("MYSQL_URL")
        result = urllib.parse.urlparse(url)

        connection = mysql.connector.connect(
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
            database=result.path[1:]  # Eliminar la barra inicial
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
                episode_links TEXT NOT NULL
            )
            ''')
            conn.commit()
        conn.close()

# Llamar a la función para crear la tabla al inicio
crear_tabla()

# Función de inicio /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Buscar Series"), KeyboardButton("Canal"), KeyboardButton("Chat")],
        [KeyboardButton("Ayuda")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("¡Bienvenido al bot de Club Kdrama! Elige una opción:", reply_markup=reply_markup)

# Función para buscar series
async def buscar_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Limpiar estados anteriores
    context.user_data['buscando'] = True
    context.user_data['estado'] = None

    await update.message.reply_text("¿Qué serie quieres buscar? Por favor, ingresa el nombre o palabra clave.")

# Función que recibe el término de búsqueda y consulta la base de datos
async def recibir_busqueda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('buscando'):  # Solo si está en modo de búsqueda
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
        cursor.execute("SELECT * FROM series WHERE title LIKE %s LIMIT 9", ('%' + query + '%',))
        resultados = cursor.fetchall()
        conn.close()

        if not resultados:
            await update.message.reply_text("No se encontraron resultados con los criterios de búsqueda ingresados.")
            return

        # Mostrar resultados numerados
        respuesta = "Resultados encontrados:\n"
        for idx, serie in enumerate(resultados, 1):
            respuesta += f"{idx}. {serie[1]}\n"  # Solo se muestra el título

        await update.message.reply_text(respuesta + "\nPor favor, ingresa el número correspondiente a la serie que deseas ver.")
        context.user_data['resultados'] = resultados  # Guardar resultados para usarlos más tarde
        context.user_data['estado'] = 'seleccionando'  # Cambiar estado a seleccionando
    else:
        await update.message.reply_text("Por favor, utiliza el botón 'Buscar Series' para iniciar la búsqueda.")

# Función que muestra los detalles de la serie seleccionada
async def mostrar_detalles_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('estado') == 'seleccionando':
        numero_seleccionado = update.message.text.strip()

        if not numero_seleccionado.isdigit():
            await update.message.reply_text("Por favor, ingresa un número válido.")
            return
        
        numero_seleccionado = int(numero_seleccionado)
        resultados = context.user_data.get('resultados', [])

        if 1 <= numero_seleccionado <= len(resultados):
            serie = resultados[numero_seleccionado - 1]  # Ajustar índice para acceso a la lista
            title, cover, description, episode_links = serie[1], serie[2], serie[3], serie[4].split(',')

            await update.message.reply_text(title)
            await context.bot.send_animation(chat_id=update.message.chat.id, animation=cover, caption=description)

            # Crear botones inline para los episodios en filas de 3
            inline_keyboard = []
            row = []
            for idx, link in enumerate(episode_links):
                row.append(InlineKeyboardButton(f"EP{str(idx + 1).zfill(2)}", url=link))
                if (idx + 1) % 3 == 0:  # Cada 3 botones, agregar una fila completa a inline_keyboard
                    inline_keyboard.append(row)
                    row = []  # Reiniciar fila para la siguiente
            # Agregar la última fila si contiene menos de 3 botones
            if row:
                inline_keyboard.append(row)

            await update.message.reply_text("Episodios disponibles:", reply_markup=InlineKeyboardMarkup(inline_keyboard))
            
            context.user_data['estado'] = None  # Reiniciar el estado después de mostrar detalles
        
        else:
            await update.message.reply_text("Número no válido. Por favor, ingresa un número de la lista.")
    else:
        await update.message.reply_text("No estás en modo de selección. Por favor, busca una serie primero.")

# Función para la ayuda
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Limpiar estados anteriores para evitar conflictos
    context.user_data['buscando'] = False
    context.user_data['estado'] = None

    ayuda_texto = (
        "Instrucciones de uso:\n"
        "1. Presiona el botón 'Buscar Series'.\n"
        "2. Ingresa el nombre de la serie que deseas buscar.\n"
        "3. Espera mientras se realiza la búsqueda en la base de datos.\n"
        "4. Selecciona un número de la lista de resultados para ver más detalles sobre la serie.\n"
        "5. Recibirás información sobre la serie, su portada y episodios disponibles.\n"
        "¡Disfruta del Club Kdrama!"
    )
    await update.message.reply_text(ayuda_texto)

# Función para el chat
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Limpiar estados anteriores para evitar conflictos
    context.user_data['buscando'] = False
    context.user_data['estado'] = None

    inline_keyboard = [[InlineKeyboardButton("Ir al Chat", url="https://t.me/+K-XVPDFhzkRhZDk5")]]
    await update.message.reply_text("¡Bienvenido al chat de Club Kdrama!", reply_markup=InlineKeyboardMarkup(inline_keyboard))

# Función para el canal
async def canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Limpiar estados anteriores para evitar conflictos
    context.user_data['buscando'] = False
    context.user_data['estado'] = None

    inline_keyboard = [[InlineKeyboardButton("Ir al Canal", url="https://t.me/clubkdrama")]]
    await update.message.reply_text("¡Bienvenido al canal de Club Kdrama!", reply_markup=InlineKeyboardMarkup(inline_keyboard))

# Configurar y ejecutar el bot
application = ApplicationBuilder().token(TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Regex('^Buscar Series$'), buscar_series))
application.add_handler(MessageHandler(filters.Regex('^Canal$'), canal))
application.add_handler(MessageHandler(filters.Regex('^Chat$'), chat))
application.add_handler(MessageHandler(filters.Regex('^Ayuda$'), ayuda))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\d+$'), mostrar_detalles_series))  # Procesa selección numérica de serie
application.add_handler(MessageHandler(filters.TEXT & ~filters.Regex(r'^\d+$'), recibir_busqueda))  # Procesa la búsqueda

# Ejecutar el bot
application.run_polling()