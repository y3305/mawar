from flask import Flask, request, jsonify, render_template
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()  # Load API Key dari file .env
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json["message"]
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Gunakan "gpt-4-turbo" jika mau lebih canggih
        messages=[{"role": "user", "content": user_message}],
        temperature=0.7,
    )
    
    bot_reply = response.choices[0].message.content
    return jsonify({"reply": bot_reply})

if __name__ == "__main__":
    app.run(debug=True)