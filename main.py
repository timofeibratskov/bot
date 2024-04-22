import openai
from pathlib import Path
import base64
import requests
from io import BytesIO
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ContentType, File, Message,Voice,ReplyKeyboardMarkup,InlineKeyboardMarkup,InlineKeyboardButton
from config import OPENAI_TOKEN, BOT_TOKEN
from gtts import gTTS
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_TOKEN)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
api_key = OPENAI_TOKEN

kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add('дай совет, что бы ты предложил поесть?')


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

#start command
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply(
        f"Привет, {message.from_user.full_name}!\nЯ бот-нутрициолог 🍽 \n Отправь мне фото еды и я подсчитаю калории или задай мне вопрос,\n кстати,если лень писать можешь отправить голосовое сообщение) ",
        reply_markup=kb
    )
#handler for photo
@dp.message_handler(content_types=['photo', 'document'])
async def handle_photo_message(message: types.Message):
    await message.photo[-1].download('photo.jpg')
    image_path = 'photo.jpg'
    base64_image = encode_image(image_path)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4-turbo",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "сколько итоговая сумма бжу и калорий в еде на фото?"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    await message.reply(response.json()['choices'][0]['message']['content'])
#handler for answers
@dp.message_handler()
async def get_answer(message: types.Message):
    response = await process_question(message.text)
    await message.reply(response)
#handler for voice
@dp.message_handler(content_types=['voice'])
async def handle_voice(message: types.Message):
    try:
        # Получаем информацию о голосовом сообщении
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        destination = f'/mnt/data/{file_id}.ogg'
        # Скачиваем голосовое сообщение
        await bot.download_file(file_path,destination)

        audio_file = open(destination, "rb")
        translation = client.audio.translations.create(
            model="whisper-1",
            file=audio_file
        )
        text_from_audio = translation.text
        response_in_text = await process_question(text_from_audio)
        tts = gTTS(response_in_text,lang='ru')
        audio_f = '/mnt/data/temp_audioanswer.ogg'
        tts.save(audio_f)
        with open(audio_f,'rb') as f:
            await bot.send_voice(message.from_user.id,f)
    except Exception as e:
        await message.reply("Произошла ошибка при обработке вашего голосового сообщения.")
        print(e)




async def process_question(question):
    # Create an assistant
    assistant = client.beta.assistants.create(
        name="нутрициолог",
        instructions="вы персональный доктор-нутрициолог.Ответь на вопрос",
        tools=[{"type": "code_interpreter"}],
        model="gpt-4-1106-preview",
    )

    # Create a thread
    thread = client.beta.threads.create()

    # Create a user message in the thread
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question,
    )

    # Run the thread and poll for completion
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Пожалуйста отвечай на вопрос коротко и не абстрактно. Ответ должен быть на русском!",
    )

    if run.status == "completed":
        # Get the list of messages in the thread
        messages = client.beta.threads.messages.list(thread_id=thread.id)

        # Extract and return the assistant's response
        response = ""
        for message in messages:
            if message.role == "assistant" and message.content[0].type == "text":
                response += message.content[0].text.value + " "

        # Delete the assistant
        client.beta.assistants.delete(assistant.id)

        return response.strip()

    return None

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)