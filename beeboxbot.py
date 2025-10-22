import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from main import run_app
TELEGRAM_TOKEN = "8329686058:AAFEims2bp5R9S8sVjbNx0JIwvhbrGcAEjI"  

def goi_agent(text: str) -> str:
    
    
    
    
    result_state = run_app(text)
    final_response = result_state.get("final_response")
    if final_response:
        return f"status={final_response.status} | message={final_response.message}"
    else:
        return "ngu vcl"
    
    
     
     
     
     

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Gửi tin nhắn để test!')

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    reply = goi_agent(msg)
    await update.message.reply_text(reply)





def main():
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()

if __name__ == '__main__':
    main()