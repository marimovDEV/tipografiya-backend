import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command as BotCommand
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from asgiref.sync import sync_to_async
from api.models import Client

# Configure logging
logging.basicConfig(level=logging.INFO)

class Command(BaseCommand):
    help = 'Runs the Telegram Bot'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Telegram Bot...'))
        asyncio.run(self.main())

    async def main(self):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token or token == 'YOUR_BOT_TOKEN_HERE':
            print("Error: TELEGRAM_BOT_TOKEN is not set in environment or settings.")
            return

        bot = Bot(token=token)
        dp = Dispatcher()
        
        # Setup handlers
        @dp.message(BotCommand("start"))
        async def cmd_start(message: types.Message):
            kb = [
                [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
            ]
            keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
            await message.answer(
                "Assalomu alaykum! PrintERP botiga xush kelibsiz.\n"
                "Iltimos, telefon raqamingizni yuboring (tugmani bosing):", 
                reply_markup=keyboard
            )

        @dp.message(F.contact)
        async def handle_contact(message: types.Message):
            contact = message.contact
            phone = contact.phone_number
            # Normalize phone (remove + if exists)
            if phone.startswith('+'):
                phone = phone[1:]
                
            # Attempt to find client by phone
            # Try exact match, or match with +
            client = await sync_to_async(self.find_client_by_phone)(phone)
            
            if client:
                client.telegram_id = str(message.from_user.id)
                await sync_to_async(client.save)()
                await message.answer(f"✅ Rahmat! Siz muvaffaqiyatli ro'yxatdan o'tdingiz.\nClient: {client.full_name}\nEndi buyurtma holati o'zgarganda sizga xabar keladi.", reply_markup=types.ReplyKeyboardRemove())
            else:
                await message.answer(f"❌ Kechirasiz, bu raqam ({phone}) tizimda topilmadi. Menejerga murojaat qiling.", reply_markup=types.ReplyKeyboardRemove())

        # Start polling
        await dp.start_polling(bot)

    def find_client_by_phone(self, phone):
        # Normalization logic: removing spaces, dashes etc
        # Simple exact search for now, assuming DB matches
        # Try finding with or without plus
        c = Client.objects.filter(phone__icontains=phone).first()
        if not c:
            # Try adding +
            c = Client.objects.filter(phone__icontains=f"+{phone}").first()
        return c
