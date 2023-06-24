import random
import string
from itertools import product

import telebot

from config import BOT_TOKEN
from user import User, DEFAULT_USER_LEVEL, get_or_create_user, save_user, del_user

GAME_MODES = ('Бот', 'Юзер', 'Дуель')

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['mode'])
def select_mode(message):
    user = get_or_create_user(message.from_user.id)
    user.mode = ''
    user.reset()
    response = 'Гра "Бики та корови"\n' + \
               'Обери режим гри (хто загадує число)'
    bot.send_message(message.from_user.id, response, 
                    reply_markup=get_buttons(*GAME_MODES))

@bot.message_handler(commands=['level'])
def select_level(message):
    user = get_or_create_user(message.from_user.id)
    user.level = None
    user.reset()
    save_user(message.from_user.id, user)
    response = 'Гра "Бики та корови"\n' + \
               'Обери рівень (кількість цифр)'
    bot.send_message(message.from_user.id, response, reply_markup=get_buttons('3', '4', '5'))

@bot.message_handler(commands=['start', 'game'])
def start_game(message, level=None):
    response = 'Гра "Бики та корови"\n'
    user = get_or_create_user(message.from_user.id)
    if not user.mode:
        select_mode(message)
        return
    if level:
        user.level = level
    if user.mode in ('bot', 'duel'):
        digits = [s for s in string.digits]
        guessed_number = ''
        for pos in range(user.level):
            if pos:
                digit = random.choice(digits)
            else:
                digit = random.choice(digits[1:])
            guessed_number += digit
            digits.remove(digit)
        print(f'{guessed_number} for {message.from_user.username}')
        user.reset(guessed_number)
        save_user(message.from_user.id, user)
        if user.mode == 'bot':
            response += f'Я загадав {user.level}-значне число. Спробуй відгадати, {message.from_user.first_name}!'
        else:
            response += (f'Я загадав {user.level}-значне число. Ти також загадай.\n' +
                f'Хто відгадає першим, {message.from_user.first_name}? Твій хід')
        bot.reply_to(message, response)
    elif user.mode == 'user':
        response += f'Загадай {user.level}-значне число. Я спробую його відгадати, а ти надсилай мені кількість биків та корів!'
        bot.reply_to(message, response)
        bot_answer_with_guess(message, user)

@bot.message_handler(commands=['help'])
def show_help(message):
    bot.reply_to(message, """
Гра "Бики та корови"

Гра, в якій потрібно за декілька спроб вгадати 4-значне число, яке загадав бот. Після кожної спроби бот повідомляє кількість вгаданих цифр, ще не на "своїх" місцях ("корови"), та повних цифрових співпадінь ("бики")
""")

@bot.message_handler(content_types=['text'])
def bot_answer(message):
    user = get_or_create_user(message.from_user.id)
    if user.number and (user.mode == 'bot' or (user.mode == 'duel' and user.next_turn)):
        bot_answer_to_user_guess(message, user)
    elif user.level and user.mode == 'user':
        bot_answer_with_guess(message, user)
    elif user.mode == 'duel' and not user.next_turn:
        if bot_has_won(message, user):
            return
        response = ''
        for number, bulls, cows in user.user_history:
            response += f'{number} | {bulls} | {cows} \n'
        response += f'Твій хід ({user.tries + 1} спроба)'
        bot.send_message(message.from_user.id, response)
        user.next_turn = True
        save_user(message.from_user.id, user)
    else:
        bot_answer_not_in_game(message, user)

def bot_answer_not_in_game(message, user):
    text = message.text
    if text in ('3', '4', '5'):
        start_game(message, int(text))
        return
    elif text == 'Так':
        start_game(message, user.level)
        return
    elif not user.mode and text in GAME_MODES:
        if text == 'Бот':
            user.mode = 'bot'
        elif text == 'Юзер':
            user.mode = 'user'
        elif text == 'Дуель':
            user.mode = 'duel'
        save_user(message.from_user.id, user)
        start_game(message, user.level)
        return
    else:
        response = 'Для запуску гри набери /start'
    bot.send_message(message.from_user.id, response)

def bot_answer_to_user_guess(message, user):
    text = message.text
    if len(text) == user.level and text.isnumeric() and len(text) == len(set(text)):
        bulls, cows = get_bulls_cows(text, user.number)
        history = list(user.user_history)
        history.append((text, bulls, cows))
        user.user_history = tuple(history)
        user.tries += 1
        user.next_turn = False
        if bulls != user.level:
            response = f'Бики: {bulls} | Корови: {cows} ({user.tries} спроба)'
            save_user(message.from_user.id, user)
            bot.send_message(message.from_user.id, response)
            if user.mode == 'duel':
                bot_answer_with_guess(message, user)
        else:
            response = f'Ти вгадав за {user.tries} спроб! Зіграємо ще?'
            user.reset()
            save_user(message.from_user.id, user)
            bot.send_message(message.from_user.id, response, 
                            reply_markup=get_buttons('Так', 'Ні'))
    else:
        response = f'Надішли мені {user.level}-значне число з різними цифрами!'
        bot.send_message(message.from_user.id, response)

def bot_answer_with_guess(message, user):
    if user.mode == 'user' and bot_has_won(message, user):
        return
    history = list(user.history)
    all_variants = [''.join(x) for x in product(string.digits, repeat=user.level)
                    if len(x) == len(set(x)) and x[0] != '0']
    while all_variants:
        guess = random.choice(all_variants)
        all_variants.remove(guess)
        if is_compatible(guess, history):
            break
    else:
        response = 'На жаль, у твоїх відповідях була помилка, в мене більше немає варіантів :-('
        stop_game_with_response(message, user, response)
        return
    history.append((guess, None, None))
    if user.mode == 'user':
        user.tries += 1
    user.history = tuple(history)
    save_user(message.from_user.id, user)
    keys = []
    for bulls in range(user.level + 1):
        for cows in range(user.level + 1 - bulls):
            if bulls != 4:
                keys.append(f'{bulls}-{cows}')
            else:
                keys.append(f'{bulls}-{cows} - Бот вгадав!')
    response = f'Мій варіант {guess} ({user.tries} спроба)\n' + \
                'Скільки биків та корів я вгадав ?'
    bot.send_message(message.from_user.id, response, reply_markup=get_buttons(*keys))

def bot_has_won(message, user):
    history = list(user.history)
    if history:
        history[-1] = (history[-1][0], *[int(x) for x in message.text.split('-')[:2]])
        if history[-1][1] == user.level:
            response = f'Я вгадав за {user.tries} спроб :-)'
            stop_game_with_response(message, user, response)
            return True
        user.history = tuple(history)
        save_user(message.from_user.id, user)
    return False

def stop_game_with_response(message, user, response):
    user.reset()
    save_user(message.from_user.id, user)
    bot.send_message(message.from_user.id, response + '\nНадішли /start для нової гри')

def is_compatible(guess, history):
    return all(get_bulls_cows(guess, previous_guess) == (bulls, cows) 
                for previous_guess, bulls, cows in history)

def get_buttons(*args):
    buttons = telebot.types.ReplyKeyboardMarkup(
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    buttons.add(*args)
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