import json
import time
import schedule
import requests
import telebot
import datetime
import pytz
import logging
import ssl
from aiohttp import web
from threading import Thread
from telebot import types

logging.basicConfig(filename= "Log.log", filemode= 'a+', format= "%(asctime)s - %(process)s - %(message)s", level=logging.INFO)

base_str = "https://api.monobank.ua/"
ukr_tz = pytz.timezone("Europe/Kiev") ##Change if needed
last_update = [] ##Stores last update -- in future might be replaced with database to make currency graphs

class CCY:

    ##Currency class - stores it's ISO name and code

    def __init__(self, name, code):
        self.name = name
        self.code = code

    def get_name(self):
        return self.name
    def get_code(self):
        return self.code
    def get_string(self):
        #returns both name and code as a string in human readable format
        return "Name: {}\nCode: {}".format(self.name, self.code)

class CCYCheck:

    #class for checking currency. Used instead of tupple or {}

    def __init__(self, code, chat_id, price, over):
        self.code = code
        self.chat = chat_id
        self.price = price
        self.over = over

#loading currencies to a list

ccy_file = open('ccy.csv', 'r')
ccy_list = []
for x in ccy_file:
    x = x.replace('\n', '')
    tmp = x.split(',')
    ccy_list.append(CCY(tmp[0], tmp[1]))

Token = "TOKEN FROM BOT FATHER" ##Replace
ccy_channel = -1001 #Replace with your channel ID (To find one send message and forward it to Forward info bot)

WEBHOOK_HOST = "" #Your server IP
WEBHOOK_PORT = 80 #Port to host bot either 80, 88, 8443 or 443. Limited by Telegram.
WEBHOOK_LISTEN = '' #Your server IP once again
WEBHOOK_SSL_CERT = './webhook_cert.pem' #Path to cert's
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'

WEBHOOK_URL_BASE = "https://{}:{}".format(WEBHOOK_HOST, WEBHOOK_PORT) #Stuff for webhook
WEBHOOK_URL_PATH = "/{}/".format(Token)

bot = telebot.TeleBot(Token, parse_mode="HTML", skip_pending=True) #creating bot with default parse mode and skiping updates

app = web.Application()
app.shutdown()
app.cleanup()

#Running bot

async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)

app.router.add_post('/{token}/', handle)

#Handling requests

def getCCYName(code):
    #returns name by currency code
    code = str(code)
    for x in ccy_list:
        if x.code == code:
            return x.name
        else:
            continue
    logging.error("Wait how? getCCYName {}".format(code))

def getCCYCode(name):
    #returns code by currency name
    for x in ccy_list:
        if x.name == name:
            return x.code
    return None

def get_ccys():
    #function sending updates to channel (if present)
    global last_update
    req = requests.get(base_str + "bank/currency")
    if (req.status_code == 429):
        logging.info("Wait, code 429")
        time.sleep(5)
        get_ccys()
    json_resp = json.loads(req.text)
    if last_update == json_resp:
        return
    try:
        json_resp['errorDescription']
        return
    except:
        None
    last_update = json_resp
    update_time = datetime.datetime.now(tz = ukr_tz)
    otp = ""
    for x in json_resp:
        try:
            x["rateBuy"]
        except KeyError:
            continue
        except Exception as E:
            logging.error("Line 64 get_ccys\n" + str(E))
            bot.send_message(253742276, E)
        if x["currencyCodeA"] == 840:
            update_time = datetime.datetime.fromtimestamp(x["date"], tz = ukr_tz)
        otp += "1 {} стоит {} {} (купить {})\n".format(getCCYName(x["currencyCodeA"]), x["rateBuy"], getCCYName(x["currencyCodeB"]), x["rateSell"])
    time_diff = datetime.datetime.now(tz = ukr_tz).replace(microsecond= 0, second= 0) - update_time.replace(microsecond= 0, second= 0)
    time_diff = str(time_diff)[:-3]
    otp += "\nТекущее время: {}\nВремя обновления курса доллара: {} (Разница: {})\nПредоставлено <a href = 'https://t.me/monocurrency'>Mono Currency</a>".format(
        datetime.datetime.now(tz = ukr_tz).strftime("%d.%m.%y %H:%M"),
        update_time.strftime("%d.%m.%y %H:%M"),
        time_diff
        )
    bot.send_message(ccy_channel, otp, True)

#run it on start
get_ccys()

def getPtop():
    #return top ccys for personal messages
    global last_update
    otp = ""
    try:
        update_time = datetime.datetime.now(tz = ukr_tz)
        for x in last_update:
            try:
                x["rateBuy"]
            except KeyError:
                continue
            except Exception as E:
                logging.error("Line 64 get_ccys\n" + str(E))
                bot.send_message(253742276, E)
            if x["currencyCodeA"] == 840:
                update_time = datetime.datetime.fromtimestamp(x["date"], tz = ukr_tz)
            otp += "1 {} стоит {} {} (купить {})\n".format(getCCYName(x["currencyCodeA"]), x["rateBuy"], getCCYName(x["currencyCodeB"]), x["rateSell"])
        time_diff = datetime.datetime.now(tz = ukr_tz).replace(microsecond= 0, second= 0) - update_time.replace(microsecond= 0, second= 0)
        time_diff = str(time_diff)[:-3]
        otp += "\nТекущее время: {}\nВремя обновления курса доллара: {} (Разница: {})\nПредоставлено <a href = 'https://t.me/monocurrency'>Mono Currency</a>".format(
            datetime.datetime.now(tz = ukr_tz).strftime("%d.%m.%y %H:%M"),
            update_time.strftime("%d.%m.%y %H:%M"),
            time_diff
            )
        return otp
    except Exception as E:
        print(E)


@bot.message_handler(commands=['start'])
def startMsg(message):
    #sending menu only to private chats
    if message.chat.type != "private":
        bot.send_message(message.chat.id, 'Используйте меня в личных сообщениях.')
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Сводка по топ валютам', callback_data = 'ptop'))
        markup.add(types.InlineKeyboardButton('Цена конкретной валюты', callback_data = 'pc'))
        markup.add(types.InlineKeyboardButton('Получить уведомление о курсе', callback_data = 'reg'))
        text = 'Чем могу помочь?'
        bot.send_message(message.chat.id, text, reply_markup=markup)

def getPriceCode(code):
    #returns price by ccy code
    for x in last_update:
        if x["currencyCodeA"] == int(code) and x["currencyCodeB"] == 980:
            try:
                return x["rateBuy"]
            except:
                return x["rateCross"]
    

def getPc(message):
    #get particular currecny's price
    global last_update
    search_code = 0
    search_price = 0
    message.text = message.text.upper()
    for x in ccy_list:
        if x.name.replace("\n", '') == message.text:
            search_code = int(x.code)
            break
    if search_code == 0:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('В главное меню', callback_data='main'))
        bot.send_message(message.chat.id, 'Не могу найти такую валюту.', reply_markup=markup)
        return
    for x in last_update:
        if x["currencyCodeA"] == search_code and x["currencyCodeB"] == 980:
            try:
                search_price = x["rateBuy"]
            except:
                search_price = x["rateCross"]
                logging.error("No rateBuy, getPc\n"+str(x))
    text = "1 {} стоит {} UAH".format(message.text, search_price)
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('В главное меню', callback_data='main'))
    bot.send_message(message.chat.id, text, reply_markup=markup)

def checkPrice(Obj):

    #checking price for PM's
    price = getPriceCode(Obj.code)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('В главное меню', 'main'))
    if Obj.over == 'less':
        if price < Obj.price:
            bot.send_message(Obj.chat, "{} стоит {}, что ниже {}!\nОстанавливаю поиск".format(getCCYName(Obj.code), price, Obj.price), reply_markup=markup)
            schedule.clear("{}{}".format(Obj.code, Obj.chat))
    else:
        if price > Obj.price:
            bot.send_message(Obj.chat, "{} стоит {}, что больше {}!\nОстанавливаю поиск".format(getCCYName(Obj.code), price, Obj.price), reply_markup=markup)
            schedule.clear("{}{}".format(Obj.code, Obj.chat))

def getReg(message):

    #First step on registering checkPrice (Asking CCY's name)
    msg = bot.send_message(message.chat.id, 'Укажите название валюты курс которой вы хотите отслеживать.\nUSD, EUR...')
    bot.register_next_step_handler(msg, getReg2)

def getReg2(message):

    #Second step on registering checkPrice (Asking wether CCY should be above or below threshold)
    markup = types.InlineKeyboardMarkup()
    ccyCode = getCCYCode(message.text.upper())
    if ccyCode == None:
        markup.add(types.InlineKeyboardButton('В главное меню', callback_data='main'))
        bot.send_message(message.chat.id, 'Такой валюты я не знаю.', reply_markup=markup)
        return
    ccyPrice = getPriceCode(ccyCode)
    if ccyPrice != 0:
        markup.add(types.InlineKeyboardButton('Выше', callback_data='more;{}'.format(ccyCode)))
        markup.add(types.InlineKeyboardButton('Ниже', callback_data='less;{}'.format(ccyCode)))
        bot.send_message(message.chat.id,'Текущий курс этой валюты - {} UAH\nВас интересует курс ниже какого-то значения, или - выше?'.format(ccyPrice), reply_markup=markup)
    else:
        markup.add(types.InlineKeyboardButton('В главное меню', callback_data='main'))
        bot.send_message(message.chat.id, 'Данную валюту нельзя купить в Monobank')

def getReg3(message, price, ccy):

    #Third step on registering checkPrice (Asking CCY's prie)
    ccyPrice = 0
    price = price.replace(',', '.')
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('В главное меню', callback_data='main'))
    try:
        ccyPrice = float(message.text)
    except:
        msg = bot.send_message(message.chat.id, 'Я думаю что это не число. Попробуйте ещё раз, или перейдите в главное меню', reply_markup=markup)
        bot.register_next_step_handler(msg, getReg3, price, ccy)
        return
    checkObj = CCYCheck(int(ccy), message.chat.id, ccyPrice, price) 
    schedule.every(2).minutes.do(checkPrice, checkObj).tag("{}{}".format(ccy, message.chat.id))
    bot.send_message(message.chat.id, 'Установил проверку по этой валюте. Каждые 2 минуты может прийти уведомление. А может и не прийти🙃', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callHandle(call):

    message = call.message
    chat = call.message.chat.id
    data = call.data

    markup = types.InlineKeyboardMarkup()

    if data == 'main':
        #To main menu
        bot.answer_callback_query(call.id, '')
        startMsg(message)
    elif data == 'ptop':
        #to top ccys
        bot.answer_callback_query(call.id, 'Ок.')
        text = getPtop()
        markup.add(types.InlineKeyboardButton('В главное меню', callback_data='main'))
        bot.send_message(chat, text, reply_markup=markup)
    elif data == 'pc':
        #to particular
        bot.answer_callback_query(call.id, 'Ок.')
        msg = bot.send_message(chat, 'Укажите название валюты в стандарте ИСО (USD, EUR...)')
        bot.register_next_step_handler(msg, getPc)
    elif data == 'reg':
        #to reg
        bot.answer_callback_query(call.id, 'Ок.')
        getReg(message)
    elif data.split(';')[0] == 'more' or data.split(';')[0] == 'less':
        #for reg
        bot.answer_callback_query(call.id, '')
        msg = bot.send_message(chat, 'Укажите пороговое значение (25.3, 37.1 ...)')
        bot.register_next_step_handler(msg, getReg3, data.split(';')[0], data.split(';')[1])
        
        

class MThread(Thread):

    def __init__(self, name):
        Thread.__init__(self)
        self.name = name
    def run(self):
        #scheduling channel update every 5 minutes
        schedule.every(5).minutes.do(get_ccys)
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as E:
                bot.send_message(253742276, str(E))

sThread = MThread('Schedule Thread')
sThread.start()

bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH, certificate=open(WEBHOOK_SSL_CERT, 'r'))

context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)
web.run_app(
    app,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    ssl_context=context,
)