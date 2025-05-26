import asyncio
import nest_asyncio

import openai
import base64
import requests
import os
from orm import create_table, insert_data, get_user, update_value, select_values
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

nest_asyncio.apply()


async def create_thread_and_assistant():
    global thread, assistant
    try:
        assistant = await openai_client.beta.assistants.create(
            name="нутрициолог",
            instructions="вы персональный доктор-нутрициолог.Ответь на вопрос",
            tools=[{"type": "code_interpreter"}],
            model="gpt-4-1106-preview",
        )
        thread = await openai_client.beta.threads.create()
    except Exception as e:
        print(f"Error creating thread and assistant: {e}")


async def is_valid_value(value):
    try:
        response = await openai_client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt=f"Дано сообщение пользователя: '{value}'. Требуется узнать является это осознанным текстом или это бред и несуразица. Нужно ответить только одним словом. 'True' - сообщение имеет смысл. Ну или слово cуществует. 'False' - сообщение имеет бред, текст без смысла(набор слов),одна буква несуразица,набор букв не имеющих смысла или нецензурная лексика.Ответ одно слово!!!"
        )
        res = response.to_dict()
        return res['choices'][0]['text']
    except Exception as e:
        print(f"Error validating value: {e}")


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


async def save_value(value, user_id):
    resp = bool(await is_valid_value(value))
    if resp:
        try:
            data_exists = await get_user(user_id)
            if data_exists:
                await update_value(user_id,value)
                return f'{value} является ценностью.\nЦенность обновлена!'
            else:
                await insert_data(user_id, value)
                return f'{value} является ценностью'
        except Exception as e:
            print(f'some problems: {e}')
    else:
        return f'{value} не является ценностью. Пожалуйста, повторите попытку(ведите комадну "/q") ' + str(resp)


# start command
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply(
        f"Привет, {message.from_user.full_name}!\nЯ бот-нутрициолог 🍽 \n Отправь мне фото еды и я подсчитаю калории или задай мне вопрос,\n кстати,если лень писать можешь отправить голосовое сообщение)\n \q - ответь на вопрос бота ",
        reply_markup=kb
    )


@dp.message_handler(commands=['admin'])
async def send_all_values(message: types.Message):
    result = await select_values()
    await message.reply(result)


@dp.message_handler(commands=['q'])
async def send_value(message: types.Message):
    await message.reply('Введи твою ценность(свайпни влево этот сообщение и напиши свою ценность): ')


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
    if message.reply_to_message and message.reply_to_message.from_user.is_bot:
        response = await save_value(message.text, message.from_user.id)
        await message.answer(response)

    else:
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


async def main():
    await create_table()


if __name__ == '__main__':
    asyncio.run(main())
    executor.start_polling(dp, skip_updates=True)
