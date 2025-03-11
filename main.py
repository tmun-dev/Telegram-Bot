from typing import Final
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import aiohttp
from bson.binary import Binary
import re
TOKEN: Final  = ""
BOT_USERNAME: Final = '@ChatFeedSalesBot'

client = MongoClient("",server_api = ServerApi('1'))

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

databases = client.list_database_names()

print("Databases:", databases)
db = client["ChatFeedSalesBot"]
messages_collection = db["products"]
settings_collection = db["settings"]




def is_valid_chat(chat_id):
    """Check if the chat is authorized"""
    # all_documents = list(settings_collection.find({}))

    # # Print results
    # for doc in all_documents:
    #     print(doc)

    
    setting = settings_collection.find_one({"_id": "allowed_chat"})
    # print(setting["chat_id"])
    # print(chat_id)
    return setting["chat_id"] == chat_id


async def download_and_store_image(file_id, context):
    """Download image from Telegram and store in MongoDB as binary"""
    bot = context.bot
    file = await bot.get_file(file_id)

    # Download file using aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(file.file_path) as resp:
            if resp.status == 200:
                image_data = await resp.read()  # Get image as bytes
                

                return Binary(image_data)
async def download_and_store_thumbnail(file_id, context):
    """Download and store high-res video thumbnail in MongoDB"""
    bot = context.bot
    file = await bot.get_file(file_id)

    async with aiohttp.ClientSession() as session:
        async with session.get(file.file_path) as resp:
            if resp.status == 200:
                thumbnail_data = await resp.read()  # Get image as bytes

                # Store thumbnail in MongoDB
                return Binary(thumbnail_data)

def watch_info(text):
    headers = ["Brand", "Model",  "Size", "Year", "Condition", "Description", "Price"]
    lower_headers = {h.lower(): h for h in headers}  # Map lowercase header to original header

    # Use regex to extract key-value pairs (case-insensitive)
    pattern = rf"({'|'.join(map(re.escape, lower_headers.keys()))}):\s*(.+)"
    matches = re.findall(pattern, text.lower())  # Lowercase text for matching

    # Convert found matches back to original-case headers and store values
    data = {lower_headers[k]: v for k, v in matches}

    # Ensure all headers exist, filling missing ones with an empty string
    data = {key: data.get(key, "") for key in headers}
    return (data)
async def handle_message(update: Update, context: CallbackContext):
    """Save messages to MongoDB"""
    message = update.message
    chat_id = message.chat_id
  
   
    # Restrict bot usage to one group
    if not is_valid_chat(chat_id):
        print("Not Valid Chat")
        return  


    if message.reply_to_message:
        replied_message_id = message.reply_to_message.message_id
        chat_id = message.chat.id
        text = ''
        if message.text:
            text = message.text
        elif message.caption:
            text = message.caption
        else:
            text = ''
        # If the reply is "sold", delete the corresponding message from MongoDB
        if "sold" in text.lower():
            result = messages_collection.delete_one({"message_id": replied_message_id, "chat_id": chat_id})
            
            if result.deleted_count > 0:
                await message.reply_text("✅ Entry deleted from the database.")
            else:
                await message.reply_text("⚠️ No matching entry found.")
    else:
        image_binary = ""
        # Handle images

        if message.photo:
            file_id = message.photo[-1].file_id  # Get highest resolution
            image_binary = await download_and_store_image(file_id, context)
            # message_data["image_url"] = await download_image(file_id,context)
        elif message.video and message.video.thumbnail:
            file_id = message.video.thumbnail.file_id  # Get video thumbnail
            image_binary = await download_and_store_thumbnail(file_id, context)
        watch_data = watch_info(message.caption)
        finalpricestring = watch_data["Price"].replace("$", "")
        message_data = {
            "message_id": message.message_id,
            "chat_id": chat_id,
            "brand": watch_data["Brand"],
            "model":  watch_data["Model"],
            "size": watch_data["Size"],
            "year": watch_data["Year"],
            "condition": watch_data["Condition"],
            "description": watch_data["Description"],
            "price":float(finalpricestring),
            "user_id": message.from_user.id,
            "image": image_binary,
            "imageType": "image/jpeg" ,
            "isFeatured": False,
            "timestamp": message.date.isoformat(),

        }

        messages_collection.insert_one(message_data)  # Store in MongoDB

async def download_image(file_id,context):
    """Download and store image (Modify this to store in a CDN or S3)"""
    bot = context.bot
    new_file = await bot.get_file(file_id)
    file_path = f"images/{file_id}.jpg"  # Local storage
    await new_file.download_to_drive(file_path)
    return file_path  # Return stored image path


if __name__ == '__main__':
    # updater = Updater(TOKEN)
    # print('Starting Bot...')
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.run_polling()

    print('Polling...')
    



