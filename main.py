import openai
import base64
import os
import requests
from keyboard import kb
from aiogram import Bot, Dispatcher, executor, types

from config import OPENAI_TOKEN, BOT_TOKEN
from gtts import gTTS


# Initialize OpenAI client
openai_client = openai.AsyncOpenAI(api_key=OPENAI_TOKEN)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
api_key = OPENAI_TOKEN

# Create a thread and assistant
thread = None
assistant = None


async def create_thread_and_assistant():
    global thread, assistant
    assistant = await openai_client.beta.assistants.create(
        name="нутрициолог",
        instructions="вы персональный доктор-нутрициолог.Ответь на вопрос",
        tools=[{"type": "code_interpreter"}],
        model="gpt-4-1106-preview",
    )
    thread = await openai_client.beta.threads.create()


async def process_question(question):
    global thread, assistant
    if not thread or not assistant:
        await create_thread_and_assistant()

    # Create a user message in the thread
    message = await openai_client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question,
    )

    # Run the thread and poll for completion
    run = await openai_client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Пожалуйста отвечай на вопрос коротко и не абстрактно. Ответ должен быть на русском!",
    )

    if run.status == "completed":
        # Get the list of messages in the thread
        messages = await openai_client.beta.threads.messages.list(thread_id=thread.id)

        # Extract and return the assistant's response
        response = messages.data[0].content[0].text.value

        return response

    return None


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


# start command
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply(
        f"Привет, {message.from_user.full_name}!\nЯ бот-нутрициолог 🍽 \n Отправь мне фото еды и я подсчитаю калории или задай мне вопрос,\n кстати,если лень писать можешь отправить голосовое сообщение) ",
        reply_markup=kb
    )


# handler for photo
@dp.message_handler(content_types=['photo', 'document'])
async def handle_photo_message(message: types.Message):
    try:
        # Скачиваем фото
        await message.photo[-1].download(destination_file='photo.jpg')
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
    except Exception as e:
        await message.reply("Произошла ошибка при обработке фото.")
        print(e)
    finally:
        os.remove(image_path)


# handler for answers
@dp.message_handler()
async def get_answer(message: types.Message):
    try:
        response = await process_question(message.text)
        await message.reply(response)
    except Exception as e:
        await message.reply("Произошла ошибка при обработке вашего запроса.")
        print(e)


# handler for voice
@dp.message_handler(content_types=['voice'])
async def handle_voice(message: types.Message):
    try:
        # Получаем информацию о голосовом сообщении
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        destination = f'{file_id}.ogg'
        # Скачиваем голосовое сообщение
        await bot.download_file(file_path, destination)

        audio_file = open(destination, "rb")
        translation = await openai_client.audio.translations.create(
            model="whisper-1",
            file=audio_file
        )
        audio_file.close()
        text_from_audio = translation.text
        response_in_text = await process_question(text_from_audio)
        tts = gTTS(response_in_text, lang='ru')
        audio_f = 'temp_audioanswer.ogg'
        tts.save(audio_f)
        with open(audio_f, 'rb') as f:
            await bot.send_voice(message.from_user.id, f)
            f.close()
            os.remove(destination)
            os.remove(audio_f)
    except Exception as e:
        await message.reply("Произошла ошибка при обработке вашего голосового сообщения.")
        print(e)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
