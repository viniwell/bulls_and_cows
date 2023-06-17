import random
import string

import telebot

from config import BOT_TOKEN
from user import User, DEFAULT_USER_LEVEL, get_or_create_user, save_user, del_user

bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start', 'game'])
def select_level(message):
    response = 'Гра "Бики та корови"\n' + \
               'Обери рівень (кількість цифр)'
    bot.send_message(message.from_user.id, response, reply_markup=get_level_buttons())

def get_level_buttons():
    buttons = telebot.types.ReplyKeyboardMarkup(
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    buttons.add('3', '4', '5')
    return buttons


def start_game(message, level):
    digits = [s for s in string.digits]
    guessed_number = ''
    for pos in range(level):
        if pos:
            digit = random.choice(digits)
        else:
            digit = random.choice(digits[1:])
        guessed_number += digit
        digits.remove(digit)
    print(f'{guessed_number} for {message.from_user.username}')
    user=get_or_create_user(message.from_user.id)
    user.reset(guessed_number)
    bot.reply_to(message, 'Гра "Бики та корови"\n'
        f'Я загадав {level}-значне число. Спробуй відгадати, {message.from_user.first_name}!')

@bot.message_handler(commands=['help'])
def show_help(message):
    bot.reply_to(message, """
Гра "Бики та корови"

Гра, в якій потрібно за декілька спроб вгадати 4-значне число, яке загадав бот. Після кожної спроби бот повідомляя кількість вгаданих цифр, ще не на "своїх" місцях ("корови"), та повних цифрових співпадінь ("бики")
""")

@bot.message_handler(content_types=['text'])
def bot_answer(message):
    text = message.text
    user=get_or_create_user(message.from_user.id)
    if user.number:
        if len(text) == user.level and text.isnumeric() and len(text) == len(set(text)):
            bulls, cows = get_bulls_cows(text, user.number)
            user.tries += 1
            if bulls != user.level:
                response = f'Бики: {bulls} | Корови: {cows} ({user.tries} спроба)'
                save_user(message.from_user.id, user)
            else:
                response = f'Ти вгадав за {user.tries} спроб! Зіграємо ще?'
                user.reset()
                save_user(message.from_user.id, user)
                bot.send_message(message.from_user.id, response, reply_markup=get_restart_buttons())
                return
        else:
            response = f'Надішли мені {user.level}-значне число з різними цифрами!'
    else:
        if text in ('3', '4', '5'):
            start_game(message, int(text))
            return
        elif text == 'Так':
            select_level(message)
            return
        else:
            response = 'Для запуску гри набери /start'
    bot.send_message(message.from_user.id, response)

def get_restart_buttons():
    buttons = telebot.types.ReplyKeyboardMarkup(
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    buttons.add('Так', 'Ні')
    return buttons

def get_bulls_cows(text1, text2):
    bulls = cows = 0
    for i in range(min(len(text1), len(text2))):
        if text1[i] in text2:
            if text1[i] == text2[i]:
                bulls += 1
            else:
                cows += 1
    return bulls, cows

if __name__ == '__main__':
    print('Bot works!')
    bot.polling(non_stop=True)